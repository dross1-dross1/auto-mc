from __future__ import annotations

"""Typed schema definitions for backend–client messages.

Purpose: Provide precise TypedDicts for message contracts to aid static checks
and keep the protocol explicit.

"""

from typing import Any, Dict, List, Literal, Optional, Tuple, TypedDict


MessageType = Literal[
    "handshake",
    "command",
    "plan",
    "action_request",
    "progress_update",
    "telemetry_update",
    "state_request",
    "state_response",
    "inventory_snapshot",
    "inventory_diff",
    "chat_send",
    "chat_event",
    "cancel",
]


class Vec3(TypedDict):
    x: float
    y: float
    z: float


class Handshake(TypedDict, total=False):
    type: Literal["handshake"]
    seq: int
    player_uuid: str
    password: str
    client_version: Optional[str]
    capabilities: Optional[Dict[str, Any]]


class Command(TypedDict):
    type: Literal["command"]
    request_id: str
    text: str
    player_uuid: str


class PlanStep(TypedDict, total=False):
    op: str
    item: Optional[str]
    count: Optional[int]
    recipe: Optional[str]
    pos: Optional[Tuple[int, int, int]]


class Plan(TypedDict):
    type: Literal["plan"]
    plan_id: str
    request_id: str
    steps: List[PlanStep]


class ActionRequest(TypedDict, total=False):
    type: Literal["action_request"]
    action_id: str
    mode: Literal["chat_bridge", "mod_native"]
    chat_text: Optional[str]
    op: Optional[str]
    pos: Optional[Tuple[int, int, int]]
    tolerance: Optional[float]
    recipe: Optional[str]
    count: Optional[int]


class ProgressUpdate(TypedDict, total=False):
    type: Literal["progress_update"]
    action_id: str
    status: Literal["ok", "fail", "skipped", "cancelled"]
    note: Optional[str]
    eta_ms: Optional[int]


class TelemetryState(TypedDict, total=False):
    pos: Tuple[float, float, float]
    dim: str
    yaw: float
    pitch: float
    health: int
    hunger: int
    saturation: float
    air: int
    effects: List[str]
    inventory: List[Dict[str, Any]]
    equipment: Dict[str, Any]
    looking_at: Optional[Dict[str, Any]]
    hotbar_slot: int
    xp_level: int
    time: int
    biome: str


class TelemetryUpdate(TypedDict):
    type: Literal["telemetry_update"]
    player_uuid: str
    ts: str
    state: TelemetryState


class StateRequest(TypedDict):
    type: Literal["state_request"]
    request_id: str
    player_uuid: str
    selector: List[str]


class StateResponse(TypedDict):
    type: Literal["state_response"]
    request_id: str
    player_uuid: str
    state: Dict[str, Any]


class ChatSend(TypedDict):
    type: Literal["chat_send"]
    request_id: str
    player_uuid: str
    text: str


class ChatEvent(TypedDict):
    type: Literal["chat_event"]
    player_uuid: str
    text: str
    ts: str


class ContainerSlot(TypedDict, total=False):
    slot: int
    id: str
    count: int
    nbt: Optional[Dict[str, Any]]


class InventoryContainer(TypedDict):
    dim: str
    pos: Tuple[int, int, int]
    container_type: str
    version: int
    hash: str
    ts_iso: str
    slots: List[ContainerSlot]


class InventorySnapshot(TypedDict):
    type: Literal["inventory_snapshot"]
    player_uuid: str
    container: InventoryContainer


class InventoryDiff(TypedDict, total=False):
    type: Literal["inventory_diff"]
    player_uuid: str
    container_key: Dict[str, Any]
    from_version: int
    to_version: int
    adds: List[ContainerSlot]
    removes: List[ContainerSlot]
    moves: List[Dict[str, Any]]


class Cancel(TypedDict):
    type: Literal["cancel"]
    request_id: str
