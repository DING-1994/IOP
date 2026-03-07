"""
auth_service.py — 認証サービス層
Gradio UI のために存在するロジックであり

責務:
    - 入力バリデーション
    - store（IUserAuth）への委譲
    - UI向けの結果メッセージ生成

auth_ui.py はこのクラスだけを知る。store を直接触らない。
auth_service.py が持っているのは「UIのための」ロジックです：

入力が空かチェック
パスワード一致チェック

"""

from firebase.protocol import IUserAuth
# only import protocoal rather than firebase_manager.py


class AuthService:

    def __init__(self, store: IUserAuth):
        self.store = store

    def login(self, email: str, password: str) -> tuple[str, str]:
        if not email.strip() or not password.strip(): # variables from UI
            return "⚠️ メールアドレスとパスワードを入力してください", self.user_info()

        _, message = self.store.login_user(email.strip(), password.strip()) # functions from services
        return message, self.user_info()

    def register(self, email: str, virtual_name: str, password: str, password_confirm: str) -> tuple[str, str]:
        if not all([email.strip(), virtual_name.strip(), password.strip()]):
            return "⚠️ すべての項目を入力してください", self.user_info()

        if password != password_confirm:
            return "⚠️ パスワードが一致しません", self.user_info()

        _, message = self.store.register_user(email.strip(), virtual_name.strip(), password.strip())
        return message, self.user_info()

    def user_info(self) -> str:
        u = self.store.current_user
        if u:
            return f"✅ ログイン中: {u['display_name']} ({u['email']})"
        return "未ログイン"
