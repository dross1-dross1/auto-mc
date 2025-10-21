from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict

import websockets


WS_URL = "ws://127.0.0.1:8765"
PLAYER_ID = "tester"


async def send_json(ws, obj: Dict[str, Any]) -> None:
    await ws.send(json.dumps(obj, separators=(",", ":")))


async def recv_json(ws, timeout: float = 2.0) -> Dict[str, Any]:
    msg = await asyncio.wait_for(ws.recv(), timeout=timeout)
    return json.loads(msg)


async def recv_until_type(ws, type_name: str, timeout: float = 3.0) -> Dict[str, Any]:
    end = asyncio.get_event_loop().time() + timeout
    while True:
        remaining = end - asyncio.get_event_loop().time()
        if remaining <= 0:
            raise TimeoutError(f"timed out waiting for {type_name}")
        try:
            obj = await recv_json(ws, timeout=remaining)
        except asyncio.TimeoutError as exc:
            raise TimeoutError(f"timed out waiting for {type_name}") from exc
        if obj.get("type") == type_name:
            return obj


async def main() -> int:
    passed = 0
    total = 9

    async with websockets.connect(WS_URL) as ws:
        # 1) Handshake
        await send_json(ws, {
            "type": "handshake",
            "seq": 1,
            "player_id": PLAYER_ID,
            "client_version": "test/0.1",
            "capabilities": {"test": True},
        })
        print("[ok] handshake sent")
        passed += 1

        # 2) Telemetry update -> persisted to data/state.json
        telemetry = {
            "pos": [0, 64, 0],
            "dim": "minecraft:overworld",
            "yaw": 0.0,
            "pitch": 0.0,
            "health": 20,
            "hunger": 20,
            "saturation": 5,
            "air": 300,
            "effects": [],
            "inventory": [],
            "equipment": {},
            "looking_at": None,
            "hotbar_slot": 0,
            "xp_level": 0,
            "time": 6000,
            "biome": "minecraft:plains",
        }
        await send_json(ws, {
            "type": "telemetry_update",
            "player_id": PLAYER_ID,
            "ts": "2025-10-18T12:34:56Z",
            "state": telemetry,
        })
        await asyncio.sleep(0.2)
        state_file = Path("data/state.json")
        assert state_file.exists(), "state file not created"
        data = json.loads(state_file.read_text(encoding="utf-8"))
        assert PLAYER_ID in data.get("telemetry", {}), "telemetry not saved for player"
        print("[ok] telemetry persisted")
        passed += 1

        # 3) state_request -> state_response with selector
        await send_json(ws, {
            "type": "state_request",
            "request_id": "req-state-1",
            "player_id": PLAYER_ID,
            "selector": ["inventory", "equipment"],
        })
        resp = await recv_until_type(ws, "state_response")
        assert resp.get("player_id") == PLAYER_ID, "state_response player mismatch"
        assert isinstance(resp.get("state"), dict), "state_response state missing"
        print("[ok] state_request/response")
        passed += 1

        # 4) !echo -> chat_send
        await send_json(ws, {
            "type": "command",
            "request_id": "req-echo-1",
            "text": "!echo hello world",
            "player_id": PLAYER_ID,
        })
        echo = await recv_until_type(ws, "chat_send")
        assert echo.get("text") == "hello world", "echo text mismatch"
        print("[ok] echo")
        passed += 1

        # 4b) !help -> chat_send
        await send_json(ws, {
            "type": "command",
            "request_id": "req-help-1",
            "text": "!help",
            "player_id": PLAYER_ID,
        })
        helpmsg = await recv_until_type(ws, "chat_send")
        assert "Available commands" in helpmsg.get("text", ""), "help text missing"
        print("[ok] help")
        passed += 1

        # 5) !multicast -> chat_send fan-out (single target)
        await send_json(ws, {
            "type": "command",
            "request_id": "req-mcast-1",
            "text": "!multicast tester !echo hello",
            "player_id": PLAYER_ID,
        })
        mcast = await recv_until_type(ws, "chat_send")
        assert mcast.get("text") == "hello", "multicast payload mismatch"
        print("[ok] multicast")
        passed += 1

        # 6) !get -> plan then action_request
        await send_json(ws, {
            "type": "command",
            "request_id": "req-craft-1",
            "text": "!get iron pickaxe 1",
            "player_id": PLAYER_ID,
        })
        plan = await recv_until_type(ws, "plan")
        assert isinstance(plan.get("steps"), list) and plan["steps"], "empty plan"
        # Expect at least one action_request emitted soon after
        action = await recv_until_type(ws, "action_request")
        assert action.get("action_id"), "missing action_id"
        print("[ok] craft plan + first action_request")
        passed += 1

        # 7) ping -> pong
        await send_json(ws, {"type": "ping"})
        pong = await recv_until_type(ws, "pong")
        assert pong.get("type") == "pong", "did not receive pong"
        print("[ok] ping/pong")
        passed += 1

        # 8) invalid JSON should not close connection
        await ws.send("{ this is not json }")
        # Send another ping to verify connection still alive
        await send_json(ws, {"type": "ping"})
        pong2 = await recv_until_type(ws, "pong")
        assert pong2.get("type") == "pong", "connection closed after invalid json"
        print("[ok] invalid JSON tolerated")
        passed += 1

    print(f"PASSED {passed}/{total}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
