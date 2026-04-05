"""
fsm/protocol.py — 接口定义层
所有数据类 + Protocol，不含任何实现逻辑
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


# ── 数据类 ───────────────────────────────────────────────

@dataclass
class Step:
    day: str
    state: str
    speaker: str
    content: str
    mbti_focus: str = ""

@dataclass
class Character:
    name: str
    role: str
    personality: str
    few_shots: list[str]
    emoji: str = "🙂"
    color: str = "#888"

@dataclass
class AdvanceResult:
    event: str              # "next_state" | "next_day" | "game_complete"
    next_step: Step | None = None
    next_character: Character | None = None

@dataclass
class JudgeResult:
    answered: bool
    reason: str


# ── Protocols ─────────────────────────────────────────────

@runtime_checkable
class IScenario(Protocol):
    def get_step(self, day: str, index: int) -> Step | None: ...
    def get_character(self, name: str) -> Character: ...
    def days(self) -> list[str]: ...

@runtime_checkable
class IFSM(Protocol):
    @property
    def current_step(self) -> Step | None: ...
    @property
    def turn_history(self) -> list[dict]: ...
    def add_turn(self, role: str, content: str) -> None: ...
    def advance(self) -> AdvanceResult: ...
    def dump(self) -> dict: ...

@runtime_checkable
class IJudge(Protocol):
    def judge(self, step: Step, user_message: str) -> JudgeResult: ...

@runtime_checkable
class IStore(Protocol):
    def get(self, session_id: str) -> dict | None: ...
    def save(self, session_id: str, data: dict) -> None: ...
    def new_id(self) -> str: ...
