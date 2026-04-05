# ===================================================
# user_store_InMemory.py  ―  メモリ上の実装（テスト用）
# ===================================================
# protocol.py の UserStore を「満たす」実装クラス。
# 継承は不要。メソッド名とシグネチャが一致すれば OK。
#
# 参照関係:
#   main.py → このクラスを import して UserService に渡す
# ===================================================

class InMemoryUserStore:
    # 継承なし ― Protocol は「見た目」で判定するため

    def __init__(self):
        self._store: dict = {}   # データはメモリ上の辞書に保持

    async def get_user(self, uid: str) -> dict:
        # uid が存在しない場合は空dictを返す（エラーにしない）
        return self._store.get(uid, {})

    async def save_user(self, uid: str, data: dict) -> None:
        # uid をキーにして上書き保存
        self._store[uid] = data