"""
game/impl.py — 実装層
protocol.py で定義されたインターフェースのみを実装し、業務オーケストレーションロジックは含まない。
"""
from __future__ import annotations
from .protocol import IScene, IPlayer, PlayerState, SceneState, NPCState

# ── マップデータ ──────────────────────────────────────────
# 0=床 1=壁 2=カーペット 3=ソファ 4=テーブル 5=植物 6=冷蔵庫 7=テレビ 8=本棚
MAP = [
    [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
    [1, 5, 0, 0, 0, 2, 2, 2, 0, 0, 0, 6, 6, 5, 1],
    [1, 0, 0, 0, 0, 2, 3, 2, 0, 0, 0, 0, 0, 0, 1],
    [1, 0, 0, 8, 0, 2, 4, 2, 0, 7, 0, 0, 0, 0, 1],
    [1, 5, 0, 8, 0, 2, 2, 2, 0, 0, 0, 0, 0, 5, 1],
    [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    [1, 5, 0, 0, 0, 4, 4, 4, 0, 0, 0, 0, 0, 5, 1],
    [1, 0, 0, 0, 0, 4, 4, 4, 0, 0, 0, 0, 0, 0, 1],
    [1, 0, 0, 5, 0, 0, 0, 0, 0, 5, 0, 0, 0, 0, 1],
    [1, 1, 1, 1, 1, 1, 1, 0, 1, 1, 1, 1, 1, 1, 1],
]
COLS, ROWS = 15, 11
BLOCKED_TILES = {1, 3, 4, 5, 6, 7, 8}

NPC_META: dict[str, dict] = {
    "DaVinci":      {"color": "#e74c3c", "emoji": "🎨"},
    "Donatello":    {"color": "#3498db", "emoji": "🔧"},
    "Michelangelo": {"color": "#f39c12", "emoji": "🖌️"},
    "Raffaello":    {"color": "#9b59b6", "emoji": "🌸"},
}

NPC_POS: dict[str, dict[str, tuple[int, int]]] = {
    "Day 1": {"DaVinci": (5, 3), "Donatello": (9, 3), "Michelangelo": (5, 7)},
    "Day 2": {"Raffaello": (10, 2), "DaVinci": (5, 5)},
    "Day 3": {"DaVinci": (5, 3), "Donatello": (9, 3), "Michelangelo": (4, 7)},
    "Day 4": {"Raffaello": (3, 7), "Donatello": (9, 6)},
    "Day 5": {"DaVinci": (5, 3), "Raffaello": (10, 3), "Michelangelo": (3, 7), "Donatello": (9, 7)},
}


class RoomScene:
    """IScene 実装 — 固定レイアウトの室内シーン。"""

    def get_scene_state(self, day: str) -> SceneState:
        """
        機能：指定日の NPC 位置一覧を含むシーン状態を生成して返す。
        入力：day（日付文字列、例: "Day 1"）
        出力：SceneState（day, active_speaker="", npcs リスト）
        """
        npcs = [
            NPCState(
                name=name, col=col, row=row,
                color=NPC_META[name]["color"],
                emoji=NPC_META[name]["emoji"],
            )
            for name, (col, row) in NPC_POS.get(day, {}).items()
        ]
        return SceneState(day=day, active_speaker="", npcs=npcs)

    def is_blocked(self, col: int, row: int, day: str) -> bool:
        """
        機能：指定マス目が移動不可（壁・家具・NPC 占有）かどうかを判定する。
        入力：col（列）、row（行）、day（現在の日）
        出力：bool（True なら移動不可）
        """
        if not (0 <= col < COLS and 0 <= row < ROWS):
            return True
        if MAP[row][col] in BLOCKED_TILES:
            return True
        return any(
            abs(nc - col) < 1 and abs(nr - row) < 1
            for nc, nr in NPC_POS.get(day, {}).values()
        )


class Player:
    """IPlayer 実装 — プレイヤーキャラクターの位置と移動を管理する。"""

    def __init__(self, start_col: int = 7, start_row: int = 6):
        """
        機能：指定の初期座標でプレイヤーを初期化する。
        入力：start_col（初期列、デフォルト 7）、start_row（初期行、デフォルト 6）
        出力：なし
        """
        self._x = start_col
        self._y = start_row

    @property
    def state(self) -> PlayerState:
        """
        機能：現在のプレイヤー座標を返す。
        入力：なし
        出力：PlayerState（x: 列, y: 行）
        """
        return PlayerState(x=self._x, y=self._y)

    def try_move(self, dx: int, dy: int, scene: IScene, day: str) -> bool:
        """
        機能：指定方向への移動を試み、移動可能な場合は座標を更新する。
        入力：dx（列方向移動量）、dy（行方向移動量）、scene（衝突判定用）、day（現在の日）
        出力：bool（True なら移動成功）
        """
        nx, ny = self._x + dx, self._y + dy
        if scene.is_blocked(nx, ny, day):
            return False
        self._x, self._y = nx, ny
        return True
