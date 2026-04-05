"""game/__init__.py — re-export only，不含任何逻辑"""
from .protocol import (
    IScene, IPlayer, IDialogBridge,
    PlayerState, SceneState, NPCState,
    DialogEvent, DialogResponse,
)
from .service import GameService, create_game

__all__ = [
    "create_game", "GameService",
    "IScene", "IPlayer", "IDialogBridge",
    "PlayerState", "SceneState", "NPCState",
    "DialogEvent", "DialogResponse",
]
