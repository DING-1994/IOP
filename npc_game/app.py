"""
app.py — ルーティング層：game パッケージと fsm パッケージを組み合わせる

モード切替：
    USE_FSM = False  → 純粋なゲームモード（WASD 移動のみ、対話なし）
    USE_FSM = True   → フルモード（LLM 駆動 NPC 対話 + シナリオ FSM）

起動方法：
    pip install -r requirements.txt
    export ANTHROPIC_API_KEY=sk-ant-...
    uvicorn app:app --reload --port 8000

アクセス：http://127.0.0.1:8000
"""
from __future__ import annotations
import os, uuid
import anthropic
from dotenv import load_dotenv

load_dotenv()
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from game import create_game, GameService, DialogEvent

# ── モード切替 ────────────────────────────────────────────
USE_FSM = True
# ─────────────────────────────────────────────────────────

_client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))

if USE_FSM:
    from fsm import create_fsm
    from bridge import FSMDialogBridge
    _fsm_svc = create_fsm(
        anthropic_client=_client,
        scenario_path="fsm/multi_npc_scenario_zh.json",
        use_rule_judge=False,   # True にするとトークン消費なしでローカルテスト可能
    )
    _bridge = FSMDialogBridge(_fsm_svc)
else:
    _bridge = None

_game: GameService = create_game(dialog_bridge=_bridge)

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── リクエストモデル ──────────────────────────────────────

class StartReq(BaseModel):
    start_day: str = "Day 1"

class MoveReq(BaseModel):
    session_id: str
    dx: int
    dy: int
    day: str

class ChatReq(BaseModel):
    session_id: str
    user_message: str


# ── ルーティング ─────────────────────────────────────────

@app.post("/start")
async def start(req: StartReq):
    """
    機能：新しいセッションを作成し、NPCの開幕台詞とシーン情報を返す。
    入力：StartReq（start_day: 開始日）
    出力：session_id, day, state, speaker, opening_line, character, npcs
    """
    sid   = str(uuid.uuid4())
    info  = await _game.start_dialog(sid, req.start_day)
    scene = _game.get_scene(req.start_day)
    return {**info, "npcs": [vars(n) for n in scene.npcs]}


@app.post("/move")
def move(req: MoveReq):
    """
    機能：プレイヤーの移動を処理する。FSM 未使用時も正常動作する。
    入力：MoveReq（session_id, dx: 列方向移動量, dy: 行方向移動量, day: 現在の日）
    出力：{"x": 新列, "y": 新行}
    """
    state = _game.move(req.dx, req.dy, req.day)
    return {"x": state.x, "y": state.y}


@app.post("/chat")
async def chat(req: ChatReq):
    """
    機能：ユーザーメッセージを送信し、NPC返答と FSM 進行結果を返す。
    入力：ChatReq（session_id, user_message: ユーザー入力テキスト）
    出力：npc_reply, advance_event, および次ステップ情報（advance 時）
    """
    try:
        event = DialogEvent(session_id=req.session_id, user_message=req.user_message)
        resp  = await _game.send_message(event)
        return vars(resp)
    except anthropic.APIStatusError as e:
        status = 503 if e.status_code == 529 else 502
        raise HTTPException(status_code=status, detail=f"AI サービスが一時的に利用不可（{e.status_code}）、しばらく後で再試行してください")


# /game/* → game/static/ を公開（bridge フロントエンドが render.js を取得するため）
app.mount("/game", StaticFiles(directory="game/static"), name="game_static")
# 静的ファイルサービス（bridge フロントエンド：ゲーム画面 + 対話ボックス）
app.mount("/", StaticFiles(directory="static", html=True), name="static")
