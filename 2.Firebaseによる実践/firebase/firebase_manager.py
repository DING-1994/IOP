"""
Firebase機能統合ファイル
firebase_manager.py は Firebase との通信だけを知るべきファイルです。

クラス構成:
    FirebaseAuthManager    ← ユーザー認証のみ（register / login）
    FirebaseStorageManager ← ゲームデータ保存のみ（save / get / download）
    FirebaseManager        ← 両方を継承（既存コードへの影響ゼロ）
"""

import os
import json
from datetime import datetime
from typing import Dict, Any, Optional, Tuple

import pyrebase
import firebase_admin
from firebase_admin import credentials, storage


_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "firebase_config.json")

def load_firebase_config() -> Dict[str, Any]:
    """Firebase設定をロード"""
    with open(_CONFIG_PATH, encoding='utf-8') as f:
        return json.load(f)


# ============================================================
# 基底クラス：Firebase接続の初期化（両クラスで共有）
# ============================================================
class _FirebaseBase:

    def __init__(self):
        self.auth = None
        self.current_user = None
        self.firebase_app = None
        self.user_info = None
        self.auth_user = None
        self.is_guest_mode = True
        self.storage_client = None
        self.admin_app = None
        self._session_game_mapping: dict = {}

        self._initialize_firebase()

    def _initialize_firebase(self):
        """Firebase初期化"""
        try:
            config = load_firebase_config()
            if not config:
                print("⚠️ Firebase設定が利用不可、テストモードを使用")
                return

            # Pyrebase は databaseURL を必須とするためダミーを補完
            if "databaseURL" not in config:
                config["databaseURL"] = f"https://{config.get('projectId', 'dummy')}.firebaseio.com"

            # Pyrebaseを初期化（認証用）
            self.firebase_app = pyrebase.initialize_app(config)
            self.auth = self.firebase_app.auth()

            # Firebase Admin SDKを初期化（Storage用）
            try:
                if not firebase_admin._apps:
                    service_account_paths = [
                        "firebase/serviceAccountKey.json",
                        "serviceAccountKey.json",
                        os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
                    ]
                    cred = None
                    for path in service_account_paths:
                        if path and os.path.exists(path):
                            cred = credentials.Certificate(path)
                            break

                    if cred:
                        self.admin_app = firebase_admin.initialize_app(cred, {
                            'storageBucket': config.get('storageBucket')
                        })
                    else:
                        self.admin_app = firebase_admin.initialize_app(options={
                            'storageBucket': config.get('storageBucket')
                        })
                else:
                    self.admin_app = firebase_admin.get_app()

                self.storage_client = storage
                print("✅ Firebase Admin SDK初期化成功")

            except Exception as e:
                print(f"⚠️ Firebase Admin SDK初期化失敗: {e}")
                self.storage_client = None
                self.admin_app = None

            print("✅ Firebase基礎サービス初期化成功")

        except Exception as e:
            print(f"❌ Firebase初期化失敗: {e}")
            self.firebase_app = None
            self.auth = None
            self.storage_client = None

    # ----------------------------------------------------------
    # ユーザー認証
    # ----------------------------------------------------------


# ============================================================
# 認証クラス：register / login のみ
# ============================================================
class FirebaseAuthManager(_FirebaseBase):
    """
    ユーザー認証に特化したクラス。
    他プロジェクトで認証だけ使いたい場合はこれを import する。
    """

    def register_user(self, email: str, virtual_name: str, password: str) -> Tuple[bool, str]:
        """新規ユーザー登録"""
        if not self.firebase_app or not self.auth:
            # テストモード登録
            user_id = f"test_{email.replace('@', '_').replace('.', '_')}"
            self._set_current_user(user_id, email, virtual_name)
            return True, f"登録成功！ようこそ {virtual_name}"

        try:
            user = self.auth.create_user_with_email_and_password(email, password)

            if user and 'localId' in user:
                self.auth_user = user
                self._set_current_user(user['localId'], email, virtual_name, token=user.get('idToken', ''))

                print(f"✅ Firebase登録成功: {virtual_name}")
                return True, f"登録成功！ようこそ {virtual_name}"
            else:
                return False, "登録失敗、再試行してください"

        except Exception as e:
            error_msg = str(e)
            if "EMAIL_EXISTS" in error_msg or "email-already-in-use" in error_msg:
                return False, "このメールアドレスは既に登録済みです"
            elif "WEAK_PASSWORD" in error_msg:
                return False, "パスワード強度不足、より複雑なパスワードを設定してください"
            elif "INVALID_EMAIL" in error_msg:
                return False, "メールアドレス形式が無効です"
            else:
                # テストモードにフォールバック
                user_id = f"test_{email.replace('@', '_').replace('.', '_')}"
                self._set_current_user(user_id, email, virtual_name)
                return True, f"登録成功！ようこそ {virtual_name}"

    def login_user(self, email: str, password: str) -> Tuple[bool, str]:
        """ユーザーログイン"""
        if not self.firebase_app or not self.auth:
            return False, "Firebase未正常初期化"

        try:
            user = self.auth.sign_in_with_email_and_password(email, password)

            if user and 'localId' in user:
                # 表示名をメールから生成
                virtual_name = email.split('@')[0]

                self.auth_user = user
                self._set_current_user(user['localId'], email, virtual_name, token=user['idToken'])

                print(f"✅ ユーザーログイン成功: {virtual_name} ({email})")
                return True, f"お帰りなさい、{virtual_name}！"
            else:
                return False, "ログイン失敗、メールアドレスとパスワードを確認してください"

        except Exception as e:
            error_msg = str(e)
            if "INVALID_EMAIL" in error_msg:
                return False, "メールアドレス形式が無効です"
            elif "EMAIL_NOT_FOUND" in error_msg:
                return False, "このメールアドレスは未登録です"
            elif "INVALID_PASSWORD" in error_msg or "INVALID_LOGIN_CREDENTIALS" in error_msg:
                return False, "パスワードが正しくありません"
            elif "USER_DISABLED" in error_msg:
                return False, "アカウントは無効化されています"
            elif "TOO_MANY_ATTEMPTS_TRY_LATER" in error_msg:
                return False, "ログイン試行回数が多すぎます、しばらく後に再試行してください"
            else:
                return False, "ログイン失敗、再試行してください"

    def _set_current_user(self, uid: str, email: str, virtual_name: str, token: str = "") -> None:
        """current_user / user_info / is_guest_mode を一括セット（内部用）"""
        self.current_user = {
            'uid': uid,
            'email': email,
            'display_name': virtual_name.strip(),
            'token': token
        }
        self.user_info = {
            'user_id': uid,
            'email': email,
            'virtual_name': virtual_name.strip(),
            'login_time': datetime.now().isoformat()
        }
        self.is_guest_mode = False