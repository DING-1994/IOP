# ===================================================
# service.py  ―  ビジネスロジック層
# ===================================================
# 「どの実装か」を知らない。UserStore(Protocol)だけに依存。
# これにより Firebase / InMemory どちらでも動く。
#
# 参照関係:
#   protocol.py → UserStore を型注釈として import
#   main.py     → UserService をインスタンス化して使う
#   （user_store_*.py は直接 import しない ← 重要）
# ===================================================

from protocol import UserStore  # 実装ではなくProtocolだけimport

class UserService:

    def __init__(self, store: UserStore) -> None:
        # 外から実装を注入してもらう（依存性の注入）
        self.store = store

    async def update_name(self, uid: str, name: str) -> None:
        user = await self.store.get_user(uid)   # Protocol経由で呼ぶ
        user["name"] = name
        await self.store.save_user(uid, user)   # Protocol経由で保存