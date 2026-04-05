"""fsm/__init__.py — re-export only，不含任何逻辑"""
from .protocol import (
    IFSM, IJudge, IStore, IScenario,
    Step, Character, AdvanceResult, JudgeResult,
)
from .service import FSMService, create_fsm

__all__ = [
    "create_fsm", "FSMService",
    "IFSM", "IJudge", "IStore", "IScenario",
    "Step", "Character", "AdvanceResult", "JudgeResult",
]
