"""
game/service.py — オーケストレーション層
Protocol を基点としたプログラミング。IScene / IPlayer / IDialogBridge を保持し、
ゲームの高レベル操作メソッドを外部に提供する。
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from .protocol import (
    IScene, IPlayer, IDialogBridge,
    DialogEvent, DialogResponse, PlayerState, SceneState,
)


@dataclass
class GameService:
    """
    ゲームサービス：IScene + IPlayer + オプションの IDialogBridge を組み合わせる。
    app.py は GameService のみと対話する。
    """
    scene: IScene
    player: IPlayer
    dialog_bridge: Optional[IDialogBridge] = None

    def move(self, dx: int, dy: int, day: str) -> PlayerState:
        """
        機能：プレイヤーを指定方向へ移動させ、更新後の位置を返す。
        入力：dx（列方向移動量）、dy（行方向移動量）、day（現在の日）
        出力：PlayerState（x: 新列, y: 新行）
        """
        self.player.try_move(dx, dy, self.scene, day)
        return self.player.state

    def get_scene(self, day: str) -> SceneState:
        """
        機能：指定日のシーン状態（NPC 位置一覧等）を返す。
        入力：day（日付文字列、例: "Day 1"）
        出力：SceneState（day, active_speaker, npcs リスト）
        """
        return self.scene.get_scene_state(day)

    def has_dialog(self) -> bool:
        """
        機能：対話ブリッジが設定されているかどうかを確認する。
        入力：なし
        出力：bool（True なら対話システム有効）
        """
        return self.dialog_bridge is not None

    async def start_dialog(self, session_id: str, start_day: str) -> dict:
        """
        機能：対話セッションを開始し、NPC 初期情報を返す。ブリッジ未設定時はダミー値を返す。
        入力：session_id（セッション識別子）、start_day（開始日）
        出力：session_id, day, state, speaker, opening_line, character を含む dict
        """
        if not self.dialog_bridge:
            return {
                "session_id": session_id, "day": start_day,
                "state": "—", "speaker": "—", "opening_line": "",
                "character": {"name": "", "role": "", "emoji": "🎮", "color": "#888"},
            }
        return await self.dialog_bridge.on_start(session_id, start_day)

    async def send_message(self, event: DialogEvent) -> DialogResponse:
        """
        機能：ユーザーメッセージを対話ブリッジへ転送し、NPC 返答を返す。ブリッジ未設定時は無効メッセージを返す。
        入力：event（session_id と user_message を持つ DialogEvent）
        出力：DialogResponse（npc_reply, advance_event 等）
        """
        if not self.dialog_bridge:
            return DialogResponse(npc_reply="（対話システム未有効）", advance_event="")
        return await self.dialog_bridge.on_user_message(event)


def create_game(dialog_bridge: Optional[IDialogBridge] = None) -> GameService:
    """
    機能：具体的な実装を依存注入し、GameService を生成して返すファクトリ関数。
    入力：dialog_bridge（IDialogBridge 実装、None の場合は移動のみのモード）
    出力：GameService インスタンス
    """
    from .impl import RoomScene, Player
    return GameService(
        scene=RoomScene(),
        player=Player(),
        dialog_bridge=dialog_bridge,
    )
