# Bridge — game と fsm の接続構造

`game/` と `fsm/` は互いを **import しない** 独立したパッケージ。  
ルートの `bridge.py` と `app.py` が唯一の接続点となり、両パッケージを組み合わせる。

---

## なぜ直接 import しないのか

```
game/ ──import──► fsm/   ← これはやらない
```

- `game/` を単独で動かしたとき（ポート 8001）に fsm の依存が不要
- `fsm/` を単独で動かしたとき（ポート 8002）にゲームロジックが不要
- 将来 fsm を別のシステムに差し替えても `game/` のコードを変えずに済む

---

## 接続の仕組み：アダプターパターン

`game/protocol.py` の `IDialogBridge` が「対話システムとの契約」を定義する。  
`bridge.py` の `FSMDialogBridge` がその契約を満たしながら、内部で `FSMService` を呼び出す。

```
game/protocol.py          bridge.py                  fsm/service.py
─────────────────         ─────────────────────────  ──────────────────
IDialogBridge             FSMDialogBridge             FSMService
  on_start()        ◄──── implements ─────►  wraps ──► start_session()
  on_user_message()                                    handle_message()
```

`GameService` は `IDialogBridge` しか知らないので、  
`FSMDialogBridge` が渡されても、別の実装が渡されても動作が変わらない。

---

## ファイル別の役割

| ファイル | 役割 |
|---------|------|
| `game/protocol.py` | `IDialogBridge` インターフェースを定義（game 側の「口」） |
| `bridge.py` | `FSMDialogBridge` を実装。fsm と game の両方を知る唯一のファイル |
| `app.py` | `FSMDialogBridge` を生成して `create_game()` に注入する組み立て役 |
| `static/bridge.js` | ブリッジ用フロントエンド。ゲーム画面と対話UIを一画面に統合 |
| `game/static/render.js` | `/game/render.js` として配信。bridge.js と game.js が共有する描画ライブラリ |

---

## 起動時の組み立てフロー（`app.py`）

```python
# ① FSMService を生成（fsm パッケージ内で完結）
_fsm_svc = create_fsm(anthropic_client, scenario_path)

# ② アダプターで IDialogBridge に適合させる
_bridge = FSMDialogBridge(_fsm_svc)

# ③ game に注入（game は IDialogBridge しか見ない）
_game = create_game(dialog_bridge=_bridge)
```

`USE_FSM = False` にすると `_bridge = None` のまま `create_game()` に渡され、  
ゲームは移動のみのモードで動作する（コードの変更なし）。

---

## HTTP エンドポイントと内部呼び出しの対応

```
ブラウザ(bridge.js)         app.py              bridge.py           fsm/service.py
────────────────────────────────────────────────────────────────────────────────────
POST /start
{ start_day }   ──────────► start()
                              ├─ _game.start_dialog(sid, day)
                              │     └─ bridge.on_start()  ──────► _svc.start_session()
                              └─ _game.get_scene(day)
                ◄──────────── { session_id, speaker, opening_line, npcs, ... }

POST /move
{ dx, dy, day } ──────────► move()
                              └─ _game.move(dx, dy, day)
                                    └─ player.try_move()  ※ bridge は関与しない
                ◄──────────── { x, y }

POST /chat
{ session_id,   ──────────► chat()
  user_message }              └─ _game.send_message(event)
                                    └─ bridge.on_user_message() ─► _svc.handle_message()
                                                                      ├─ _npc_reply() [LLM]
                                                                      ├─ judge.judge() [LLM]
                                                                      └─ fsm.advance()
                ◄──────────── { npc_reply, advance_event, next_* }
```

---

## フロントエンドの統合（`static/bridge.js`）

`game/static/game.js`（独立ゲーム用）と `static/bridge.js`（ブリッジ用）は  
どちらも `game/static/render.js` を共有しつつ、**`drawNPC` の実装だけ異なる**。

| | `game/static/game.js` | `static/bridge.js` |
|--|----------------------|-------------------|
| `drawNPC` の引数 | `(name, col, row, tick)` | `(name, col, row, isActive, isTarget, tick)` |
| NPC 強調表示 | なし | 目標NPC に ▼、対話中に 💬、他は暗く表示 |
| 対話UI | なし | あり（チャットログ・入力欄） |
| E キー | なし | 近くの NPC に話しかける |
| `/chat` 呼び出し | なし | あり |

`bridge.js` の FSM 誘導ロジックの状態変数：

```javascript
expectedSpeaker  // FSMが指示する「次に話すべき NPC」
pendingLine      // その NPC の開幕台詞（E キーを押したときに表示）
dialogActive     // 対話パネルが開いているか
activeSpeaker    // 現在対話中の NPC（Canvas で全輝度表示）
```

---

## E キーによる対話開始フロー（`bridge.js` 内完結）

```
キーボード E キー押下
  └─ keydown ハンドラ
       └─ getNearbyNPC()        プレイヤー周囲1マスの NPC を探す
       └─ tryStartDialog(name)
            ├─ name ≠ expectedSpeaker → showCanvasHint("先に〇〇へ")  終了
            └─ name = expectedSpeaker → openDialog()
                 └─ pendingLine を bubble("npc") で表示
                 └─ 入力欄を有効化

ユーザーが送信
  └─ send()
       └─ POST /chat → NPC 返答を表示
       └─ [advance_event あり]
            └─ closeDialog()
            └─ expectedSpeaker = resp.next_speaker  # 次の NPC を更新
            └─ showCanvasHint("〇〇へ向かえ")
```

---

## 独立モードとブリッジモードの比較

| | 独立ゲーム（ポート 8001） | 独立 FSM（ポート 8002） | ブリッジ（ポート 8000） |
|--|--------------------------|------------------------|------------------------|
| サーバー | `game/app.py` | `fsm/app.py` | `app.py` |
| フロントエンド | `game/static/` | `fsm/static/` | `static/` |
| 移動 | ✅ | ❌ | ✅ |
| NPC 対話 | ❌ | ✅ | ✅ |
| FSM 誘導 | ❌ | ✅ | ✅ |
| `bridge.py` 使用 | ❌ | ❌ | ✅ |
