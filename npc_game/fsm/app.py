"""
fsm/app.py — 独立対話サーバー（ゲーム画面なし）

FSM 駆動の NPC 対話のみを提供し、フロントエンドは対話ボックスのみを表示する。

起動方法（プロジェクトルートから）：
    uvicorn fsm.app:app --reload --port 8002

アクセス：http://127.0.0.1:8002
"""
from __future__ import annotations
import os, uuid, pathlib
import anthropic
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()

from fsm import create_fsm

_client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
_scenario_path = str(pathlib.Path(__file__).parent / "multi_npc_scenario_zh.json")
_fsm_svc = create_fsm(
    anthropic_client=_client,
    scenario_path=_scenario_path,
    use_rule_judge=False,   # True にするとトークン消費なしでローカルテスト可能
)

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class StartReq(BaseModel):
    start_day: str = "Day 1"

class ChatReq(BaseModel):
    session_id: str
    user_message: str


@app.post("/start")
def start(req: StartReq):
    """
    機能：新しいセッションを作成し、最初の NPC の開幕台詞を返す。
    入力：StartReq（start_day: 開始日）
    出力：session_id, day, state, speaker, opening_line, character を含む dict
    """
    sid = str(uuid.uuid4())
    return _fsm_svc.start_session(sid, req.start_day)


@app.post("/chat")
def chat(req: ChatReq):
    """
    機能：ユーザーメッセージを処理し、NPC 返答と FSM 進行結果を返す。
    入力：ChatReq（session_id, user_message: ユーザー入力テキスト）
    出力：npc_reply, advance_event, および次ステップ情報（advance 時）
    """
    try:
        return _fsm_svc.handle_message(req.session_id, req.user_message)
    except anthropic.APIStatusError as e:
        status = 503 if e.status_code == 529 else 502
        raise HTTPException(status_code=status, detail=f"AI サービスが一時的に利用不可（{e.status_code}）、しばらく後で再試行してください")


_static_dir = pathlib.Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=str(_static_dir), html=True), name="static")
