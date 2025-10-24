from __future__ import annotations

"""Action dispatcher for streaming planner steps to the mod.

Purpose: Convert planner steps into concrete action_request messages and send
them to the client at a paced interval. Uses chat-bridge for world acquisition
and mod-native for crafting/smelting.

Engineering notes: Keep JSON lean (minified); preserve ordering; avoid waiting inline for progress; centralize mapping logic.

"""

import asyncio
import json
import logging
import uuid
from typing import Any, Callable, Dict, List, Optional

from websockets.server import WebSocketServerProtocol
from .config import load_settings
from .data_files import load_acquisition_map


logger = logging.getLogger("automc.dispatcher")


class Dispatcher:
    def __init__(
        self,
        websocket: WebSocketServerProtocol,
        *,
        player_id: Optional[str] = None,
        state_service: Optional[object] = None,
        on_action_send: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    ) -> None:
        self.websocket = websocket
        self.settings = load_settings()
        self.player_id = player_id
        self.state_service = state_service
        self._on_action_send = on_action_send

    async def run_linear(self, steps: List[Dict[str, Any]]) -> None:
        # Ensure we respect the client's chat-bridge rate limit; never send
        # chat commands faster than allowed or they will be dropped client-side.
        try:
            chat_rate = int(self.settings.chat_bridge_rate_limit_per_sec)
        except Exception:
            chat_rate = 0
        min_chat_interval_s = 0.0 if chat_rate <= 0 else (1.0 / float(chat_rate))
        # Pace actions conservatively: always add configured spacing on top of the
        # client's chat-bridge minimum interval to avoid sent=false due to jitter.
        action_spacing_s = max(int(self.settings.default_action_spacing_ms) / 1000.0, 0.0)
        spacing = min_chat_interval_s + action_spacing_s
        last_chat_text: str = ""
        for step in steps:
            action_id = str(uuid.uuid4())
            # Inventory-aware skip: if we already have enough of the target, skip acquire/craft/smelt
            if self._should_skip_step_due_to_inventory(step):
                continue
            # For ensure-context placeholders, send chat-based settings and navigate to target with ETA probe
            if step.get("op") == "acquire" and str(step.get("item")) in {"crafting_table_nearby", "furnace_nearby"}:
                # 1) Ensure auto-open via chat command
                set_msg = {
                    "type": "action_request",
                    "action_id": str(uuid.uuid4()),
                    "mode": "chat_bridge",
                    "op": "chat",
                    "chat_text": "#set rightClickContainerOnArrival true",
                }
                await self.websocket.send(json.dumps(set_msg, separators=(",", ":")))
                if spacing > 0:
                    await asyncio.sleep(spacing)
                # 2) Navigate and probe ETA
                target = "crafting_table" if str(step.get("item")) == "crafting_table_nearby" else "furnace"
                goto_msg = {
                    "type": "action_request",
                    "action_id": str(uuid.uuid4()),
                    "mode": "chat_bridge",
                    "op": "acquire",
                    "chat_text": f"#goto {target}",
                }
                await self.websocket.send(json.dumps(goto_msg, separators=(",", ":")))
                if spacing > 0:
                    await asyncio.sleep(spacing)
                # Ask client to surface #eta result
                eta_cmd = {
                    "type": "action_request",
                    "action_id": str(uuid.uuid4()),
                    "mode": "chat_bridge",
                    "op": "chat",
                    "chat_text": "#eta",
                }
                await self.websocket.send(json.dumps(eta_cmd, separators=(",", ":")))
                # This step is fully handled; do not emit another action for it
                continue
            msg = self._to_action_request(step, action_id)
            # Notify server about the action-id -> step mapping for bookkeeping
            if self._on_action_send is not None:
                try:
                    self._on_action_send(action_id, step)
                except Exception:
                    pass
            # Drop consecutive duplicate chat_bridge text commands to reduce spam
            if msg.get("mode") == "chat_bridge":
                chat_text = str(msg.get("chat_text", ""))
                if chat_text and chat_text == last_chat_text:
                    continue
                last_chat_text = chat_text
            await self.websocket.send(json.dumps(msg, separators=(",", ":")))
            # If we started a world-acquire (#mine), poll inventory and stop when satisfied
            if msg.get("mode") == "chat_bridge" and str(msg.get("chat_text", "")).startswith("#mine "):
                target_item = str(step.get("item", ""))
                need = int(step.get("count", 0)) if isinstance(step.get("count"), int) else 0
                if target_item and need > 0:
                    reached = await self._wait_until_inventory_has(target_item, need)
                    if reached:
                        stop = {
                            "type": "action_request",
                            "action_id": str(uuid.uuid4()),
                            "mode": "chat_bridge",
                            "op": "chat",
                            "chat_text": "#stop",
                        }
                        await self.websocket.send(json.dumps(stop, separators=(",", ":")))
            # We do not wait synchronously for progress; the mod should reply
            if spacing > 0:
                await asyncio.sleep(spacing)
            else:
                await asyncio.sleep(0)  # yield control

    def _to_action_request(self, step: Dict[str, Any], action_id: str) -> Dict[str, Any]:
        op = step.get("op")
        if op == "acquire":
            item = str(step.get("item", "")).lower()
            # Context placeholders -> chat-bridge Baritone navigation (auto-open enabled per-step)
            if item == "crafting_table_nearby":
                return {
                    "type": "action_request",
                    "action_id": action_id,
                    "mode": "chat_bridge",
                    "op": op,
                    "chat_text": "#goto crafting_table",
                    **{k: v for k, v in step.items() if k not in {"op"}},
                }
            if item == "furnace_nearby":
                return {
                    "type": "action_request",
                    "action_id": action_id,
                    "mode": "chat_bridge",
                    "op": op,
                    "chat_text": "#goto furnace",
                    **{k: v for k, v in step.items() if k not in {"op"}},
                }
            # For mineable targets, only emit one mining command at a time.
            # The planner may request multiple different acquires; spacing in run_linear reduces overlap.
            chat_text = self._acquire_to_chat(step)
            return {
                "type": "action_request",
                "action_id": action_id,
                "mode": "chat_bridge",
                "op": op,
                "chat_text": chat_text,
                **{k: v for k, v in step.items() if k not in {"op"}},
            }
        if op in {"craft", "smelt"}:
            return {
                "type": "action_request",
                "action_id": action_id,
                "mode": "mod_native",
                "op": op,
                **{k: v for k, v in step.items() if k != "op"},
            }
        # Fallback to chat bridge noop
        return {
            "type": "action_request",
            "action_id": action_id,
            "mode": "chat_bridge",
            "chat_text": "#stop",
        }

    def _acquire_to_chat(self, step: Dict[str, Any]) -> str:
        """Map acquire step to a Baritone chat command.

        Baritone does not support a count argument for #mine; it will mine until stopped.
        We therefore emit only the target and manage stopping via separate logic.
        """
        item: str = str(step.get("item", "")).lower()
        try:
            item_to_target = load_acquisition_map()
        except Exception:
            item_to_target = {}
        if item in item_to_target:
            return f"#mine {item_to_target[item]}"
        if item.startswith("minecraft:"):
            return f"#mine {item.split(':', 1)[1]}"
        if item:
            return f"#mine {item}"
        pos = step.get("pos")
        if isinstance(pos, (list, tuple)) and len(pos) == 3:
            x, y, z = pos
            return f"#mine {x} {y} {z}"
        return "#stop"

    async def _wait_until_inventory_has(self, item_id: str, count: int) -> bool:
        """Poll latest telemetry inventory until count met (no timeout)."""
        if not self.player_id or not self.state_service or count <= 0:
            await asyncio.sleep(0)
            return False
        poll_ms = int(self.settings.acquire_poll_interval_ms)
        while True:
            try:
                player_state = self.state_service.get_player_state(self.player_id)  # type: ignore[attr-defined]
                if player_state and isinstance(player_state.get("state", {}).get("inventory"), list):
                    total = 0
                    for slot in player_state["state"]["inventory"]:
                        if str(slot.get("id")) == item_id:
                            total += int(slot.get("count", 0))
                    if total >= count:
                        return True
            except Exception:
                pass
            await asyncio.sleep(poll_ms / 1000.0)

    def _should_skip_step_due_to_inventory(self, step: Dict[str, Any]) -> bool:
        if not self.player_id or not self.state_service:
            return False
        try:
            player_state = self.state_service.get_player_state(self.player_id)  # type: ignore[attr-defined]
        except Exception:
            return False
        if not player_state:
            return False
        state = player_state.get("state", {})
        inv = state.get("inventory", [])
        if not isinstance(inv, list):
            return False
        # Build counts by id
        counts: Dict[str, int] = {}
        for slot in inv:
            try:
                iid = str(slot.get("id"))
                c = int(slot.get("count", 0))
                if iid:
                    counts[iid] = counts.get(iid, 0) + c
            except Exception:
                continue
        op = step.get("op")
        need = int(step.get("count", 1))
        if op == "acquire":
            target = str(step.get("item", ""))
            # Already have the target itself
            if bool(target) and counts.get(target, 0) >= need:
                return True
            # If target is a log type, accept any log variants
            if target.startswith("minecraft:") and target.endswith("_log"):
                log_count = sum(v for k, v in counts.items() if k.startswith("minecraft:") and k.endswith("_log"))
                return log_count >= need
            return False
        if op in {"craft", "smelt"}:
            # Do not skip craft/smelt steps based on current inventory; the planner already
            # prunes using inventory. Skipping here can break prerequisite conversions
            # (e.g., logs→planks before crafting tables).
            return False
        return False
