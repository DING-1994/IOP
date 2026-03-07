# ============================================================
# firebase/protocol.py  —  Firebase インターフェース定義
# ============================================================
# 「何ができるべきか」だけを宣言する。実装は一切書かない。
# ============================================================

from typing import Protocol, Tuple, Any, Optional


# ============================================================
# 責務1: ユーザー認証
# 対応実装: FirebaseAuthManager
# ============================================================
class IUserAuth(Protocol):
    """
    ユーザーの登録・ログインを担う。
    参照元: AuthController / UserSession
    """

    current_user: Optional[dict]
    # {"uid": str, "email": str, "display_name": str} | None
    # メソッドではなく属性として直接アクセスされるためここに明示。

    def register_user(
        self, email: str, virtual_name: str, password: str
    ) -> Tuple[bool, str]:
        """
        新規ユーザー登録。
        Returns: (成功フラグ, メッセージ)
        """
        ...

    def login_user(
        self, email: str, password: str
    ) -> Tuple[bool, str]:
        """
        ログイン。成功時は current_user をセットする。
        Returns: (成功フラグ, メッセージ)
        """
        ...
