# Protocol パターン — README

Pythonの `Protocol` を使って、差し替え可能な設計を実現するサンプルプロジェクト。

---

## ファイル構成

```
PROTOCOL/
├── protocol.py              # インターフェース定義（契約書）
├── user_store_InMemory.py   # メモリ実装（テスト用）
├── service.py               # ビジネスロジック層
└── main.py                  # エントリーポイント
```

## 依存関係図

```
┌─────────────────────────────────────────────────────────┐
│                        main.py                          │
│                    エントリーポイント                      │
└────────────────┬──────────────────┬─────────────────────┘
                 │ import           │ import
                 ▼                  ▼
  ┌──────────────────────┐  ┌──────────────────────────┐
  │      service.py      │  │  user_store_InMemory.py  │
  │   ビジネスロジック層    │  │      テスト用の実装         │
  └──────────┬───────────┘  └────────────┬─────────────┘
             │ import（型のみ）            │ 満たす
             ▼                           ▼
  ┌──────────────────────────────────────────────────────┐
  │                    protocol.py                       │
  │              UserStore（インターフェース）               │
  └──────────────────────────────────────────────────────┘
```

> `service.py` は `user_store_*.py` を直接 import しない。
> Protocol を介してのみ繋がる。

---

## 1. `protocol.py` — 契約を定義する

**役割：** 「何ができるべきか」だけを宣言する。実装は一切書かない。

```python
from typing import Protocol

class UserStore(Protocol):
    async def get_user(self, uid: str) -> dict: ...
    async def save_user(self, uid: str, data: dict) -> None: ...
```

**ポイント：**
- `Protocol` を継承したクラスはインターフェースになる
- メソッド本体は `...` だけでよい
- このファイルは他のファイルから**型として**参照される

---

## 2. `user_store_InMemory.py` — テスト用の実装

**役割：** `protocol.py` の `UserStore` を満たす実装。

```python
class InMemoryUserStore:        # 継承不要
    def __init__(self):
        self._store: dict = {}

    async def get_user(self, uid: str) -> dict:
        return self._store.get(uid, {})

    async def save_user(self, uid: str, data: dict) -> None:
        self._store[uid] = data
```

**ポイント：**
- `UserStore` を継承しなくても、メソッド名とシグネチャが一致すれば Protocol を満たす（鸭子类型）
- データはメモリ上の `dict` に保持するだけなので、外部接続が不要


---

## 3. `service.py` — ビジネスロジック層

**役割：** ユーザーに関する操作を担う。実装クラスを直接 import しなく、protocolをimport。

```python
from protocol import UserStore      # 実装ではなく Protocol だけ import

class UserService:
    def __init__(self, store: UserStore) -> None:
        self.store = store           # 外から実装を注入してもらう

    async def update_name(self, uid: str, name: str) -> None:
        user = await self.store.get_user(uid)
        user["name"] = name
        await self.store.save_user(uid, user)
```

**ポイント：**
- `store` の型は `UserStore`（Protocol）であり、`InMemoryUserStore` でも、他の実装：例えば、Firebase利用するもの`FirebaseUserStore` でも受け取れる
- このファイルは `user_store_*.py` を一切 import しない ← これが設計の核心
- Protoclに定義された機能に基づいて、新たな関数（例えば、update_name）を作られる
- テストのしやすさと本番への切り替えやすさが両立する


## protocol.pyと分けておく理由

|          | `protocol.py`        | `service.py`   |
|----------|----------------------|----------------|
| 役割     | 契約の定義           | ロジックの実装 |
| 変更頻度 | ほぼ変わらない       | 機能追加で変わる |
| 参照元   | service / 全実装クラス | main のみ    |

---

## 4. `main.py` — 組み立てと実行

**役割：** どの実装を使うかを唯一決める場所。

```python
import asyncio
from user_store_InMemory import InMemoryUserStore
from service import UserService

async def main() -> None:
    store = InMemoryUserStore()    # ← ここだけ変えれば差し替え完了
    service = UserService(store)
    await service.update_name("user_001", "Tanaka")
    user = await store.get_user("user_001")
    print(user)   # {'name': 'Ding'}

asyncio.run(main())
```

**ポイント：**
- `store = ...` の1行を変えるだけで Firebase 版に切り替えられる
- `service.py` や `protocol.py` は一切変更しない

---

## 実行方法

```bash
python main.py
# 出力: {'name': 'Tanaka'}
```
