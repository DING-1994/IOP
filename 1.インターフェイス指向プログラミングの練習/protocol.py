# ===================================================
# protocol.py  ―  インターフェース定義（契約書）
# ===================================================
# このファイルは「何ができるべきか」だけを定義する。
# 実装は一切書かない。
#
# 参照関係:
#   service.py  → UserStore を型として import する
#   user_store_InMemory.py → このProtocolを「満たす」実装
# ===================================================

from typing import Protocol

class UserStore(Protocol):

    async def get_user(self, uid: str) -> dict:
        # uid を渡すと、ユーザーデータ(dict)を返す約束
        ...

    async def save_user(self, uid: str, data: dict) -> None:
        # uid と data を渡すと、保存する約束
        ...