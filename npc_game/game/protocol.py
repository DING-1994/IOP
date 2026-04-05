"""
game/protocol.py — 接口定义层
所有数据类 + Protocol，不含任何实现逻辑
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


# ── 数据类 ───────────────────────────────────────────────

@dataclass
class PlayerState:
    x: int
    y: int

@dataclass
class NPCState:
    name: str
    col: int
    row: int
    color: str
    emoji: str

@dataclass
class SceneState:
    day: str
    active_speaker: str
    npcs: list[NPCState]

@dataclass
class DialogEvent:
    session_id: str
    user_message: str

@dataclass
class DialogResponse:
    npc_reply: str
    advance_event: str = ""
    next_day: str = ""
    next_state: str = ""
    next_speaker: str = ""
    next_opening_line: str = ""
    next_character: dict = field(default_factory=dict)


# ── Protocols ─────────────────────────────────────────────

@runtime_checkable
class IScene(Protocol):
    def get_scene_state(self, day: str) -> SceneState: ...
    def is_blocked(self, col: int, row: int, day: str) -> bool: ...

@runtime_checkable
class IPlayer(Protocol):
    @property
    def state(self) -> PlayerState: ...
    def try_move(self, dx: int, dy: int, scene: IScene, day: str) -> bool: ...

@runtime_checkable
class IDialogBridge(Protocol):
    """game 与外部对话系统的唯一耦合点，不注入时游戏独立运行"""
    async def on_start(self, session_id: str, start_day: str) -> dict: ...
    async def on_user_message(self, event: DialogEvent) -> DialogResponse: ...
