"""
bridge.py — game.IDialogBridge を実装し、game パッケージと fsm パッケージを接続する。
プロジェクト内で唯一、両パッケージを同時に知るファイル。
"""
from __future__ import annotations
from game.protocol import IDialogBridge, DialogEvent, DialogResponse
from fsm.service import FSMService


class FSMDialogBridge:
    """FSMService の機能を game.IDialogBridge として適応させるアダプター。"""

    def __init__(self, fsm_service: FSMService):
        """
        機能：FSMService を受け取り、IDialogBridge として初期化する。
        入力：fsm_service（FSMService インスタンス）
        出力：なし
        """
        self._svc = fsm_service

    async def on_start(self, session_id: str, start_day: str) -> dict:
        """
        機能：新しいセッションを開始し、最初の NPC 情報と開幕台詞を返す。
        入力：session_id（セッション識別子）、start_day（開始日文字列）
        出力：session_id, day, state, speaker, opening_line, character を含む dict
        """
        return self._svc.start_session(session_id, start_day)

    async def on_user_message(self, event: DialogEvent) -> DialogResponse:
        """
        機能：ユーザーメッセージを FSMService に転送し、NPC 返答と進行結果を返す。
        入力：event（session_id と user_message を持つ DialogEvent）
        出力：DialogResponse（npc_reply, advance_event, 次ステップ情報）
        """
        result = self._svc.handle_message(event.session_id, event.user_message)
        return DialogResponse(**result)
