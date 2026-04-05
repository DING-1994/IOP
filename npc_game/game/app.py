"""
game/app.py — 独立ゲームサーバー（対話システムなし）

移動機能のみを提供し、フロントエンドはゲーム画面のみを表示する。

起動方法（プロジェクトルートから）：
    uvicorn game.app:app --reload --port 8001

アクセス：http://127.0.0.1:8001
"""
from __future__ import annotations
import pathlib
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from game import create_game

_game = create_game()  # dialog_bridge=None：移動のみのモード

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class StartReq(BaseModel):
    start_day: str = "Day 1"

class MoveReq(BaseModel):
    dx: int
    dy: int
    day: str


@app.post("/start")
def start(req: StartReq):
    """
    機能：シーンの NPC 位置一覧を返す。フロントエンドの初期描画に使用する。
    入力：StartReq（start_day: 開始日）
    出力：{"npcs": [{name, col, row, color, emoji}, ...]}
    """
    scene = _game.get_scene(req.start_day)
    return {"npcs": [vars(n) for n in scene.npcs]}


@app.post("/move")
def move(req: MoveReq):
    """
    機能：プレイヤーの移動を処理し、新しい座標を返す。
    入力：MoveReq（dx: 列方向移動量, dy: 行方向移動量, day: 現在の日）
    出力：{"x": 新列, "y": 新行}
    """
    state = _game.move(req.dx, req.dy, req.day)
    return {"x": state.x, "y": state.y}


_static_dir = pathlib.Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=str(_static_dir), html=True), name="static")
