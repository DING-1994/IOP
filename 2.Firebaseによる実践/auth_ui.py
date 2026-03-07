"""
auth_ui.py — 最小構成の登録・ログイン画面
"""

import gradio as gr
from firebase.firebase_manager import FirebaseAuthManager
from firebase.auth_service import AuthService

# ----------------------------------------------------------
# 依存注入（テスト時はここだけ変える）
# ----------------------------------------------------------
# from firebase.memory_store import InMemoryFirebaseStore
# service = AuthService(InMemoryFirebaseStore())
service = AuthService(FirebaseAuthManager())

# ----------------------------------------------------------
# UI
# ----------------------------------------------------------

with gr.Blocks(title="ログイン / 登録") as demo:
    gr.Markdown("## 🔐 ユーザー認証")

    status = gr.Textbox(label="状態", value=service.user_info(), interactive=False)

    with gr.Tab("ログイン"):
        login_email    = gr.Textbox(label="メールアドレス", placeholder="example@mail.com")
        login_password = gr.Textbox(label="パスワード", type="password")
        login_btn      = gr.Button("ログイン", variant="primary")
        login_msg      = gr.Textbox(label="結果", interactive=False)

        login_btn.click(
            service.login,
            inputs=[login_email, login_password],
            outputs=[login_msg, status]
        )

    with gr.Tab("新規登録"):
        reg_email    = gr.Textbox(label="メールアドレス", placeholder="example@mail.com")
        reg_name     = gr.Textbox(label="表示名", placeholder="ニックネーム")
        reg_password = gr.Textbox(label="パスワード", type="password")
        reg_confirm  = gr.Textbox(label="パスワード（確認）", type="password")
        reg_btn      = gr.Button("登録", variant="primary")
        reg_msg      = gr.Textbox(label="結果", interactive=False)

        reg_btn.click(
            service.register,
            inputs=[reg_email, reg_name, reg_password, reg_confirm],
            outputs=[reg_msg, status]
        )


if __name__ == "__main__":
    demo.launch()
