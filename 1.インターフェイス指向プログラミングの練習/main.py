# ===================================================
# main.py  ―  エントリーポイント（組み立て役）
# ===================================================
# どの実装を使うかを唯一決める場所。
# 本番に切り替える時もここの store = ... 1行だけ変える。
#
# 参照関係:
#   user_store_InMemory.py → 実装を選んで import
#   service.py             → UserService を import
#   protocol.py            → 直接は使わない（service経由）
# ===================================================

import asyncio
from user_store_InMemory import InMemoryUserStore  # ← ここだけ変えれば差し替え完了
from service import UserService

async def main() -> None:
    store = InMemoryUserStore()   # 実装を選ぶ
    service = UserService(store)  # service に注入する

    await service.update_name("user_001", "Tanaka")

    user = await store.get_user("user_001")
    print(user)  # {'name': 'Tanaka'}

asyncio.run(main())
