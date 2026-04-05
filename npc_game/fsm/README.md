# fsm パッケージ

ShareHouse RPG の有限状態機械（FSM）と NPC 対話システムを担当するパッケージ。  
ゲームロジック（`game/`）とは独立して動作し、`bridge.py` からのみ接続される。

---

## ファイル構成

```
fsm/
├── protocol.py                    # インターフェース定義層（データクラス + Protocol）
├── service.py                     # オーケストレーション層（FSMService）
├── impl.py                        # 実装層（JsonScenario, ShareHouseFSM, Judge, Store）
├── app.py                         # スタンドアロン FastAPI サーバー（ポート 8002）
├── multi_npc_scenario_zh.json     # シナリオデータ（キャラクター・日程・台詞）
└── static/
    ├── chat.js                    # 独立対話フロントエンド
    └── index.html                 # 独立対話画面
```

---

## レイヤー構造

```
protocol.py  ←  すべてのレイヤーが参照するインターフェース定義
     ↑
impl.py      ←  具体的な実装（Protocol を満たすクラス群）
     ↑
service.py   ←  impl を組み合わせた高レベル操作
     ↑
app.py       ←  HTTP エンドポイント（service を呼び出す）
```

---

## 主要ファイルの説明

### `protocol.py` — インターフェース定義層

データクラスと Protocol のみを定義。実装ロジックなし。

| 名前 | 種別 | 説明 |
|------|------|------|
| `Step` | dataclass | FSM の 1 ステップ（day, state, speaker, content, mbti_focus） |
| `Character` | dataclass | NPC キャラクター情報（name, role, personality, few_shots, emoji, color） |
| `AdvanceResult` | dataclass | FSM 進行結果（event, next_step, next_character） |
| `JudgeResult` | dataclass | 判定結果（answered: bool, reason: str） |
| `IScenario` | Protocol | シナリオ読み込みのインターフェース |
| `IFSM` | Protocol | 状態機械操作のインターフェース |
| `IJudge` | Protocol | ユーザー回答判定のインターフェース |
| `IStore` | Protocol | セッション永続化のインターフェース |

---

### `impl.py` — 実装層

`protocol.py` のインターフェースを実装するクラス群。LLM 呼び出しは `LLMJudge` のみ。

#### `JsonScenario`（implements `IScenario`）
| メソッド | 説明 |
|----------|------|
| `__init__(path)` | JSON ファイルを読み込みキャラクター・日程データを初期化する |
| `get_step(day, index)` | 指定日・インデックスの `Step` を返す |
| `get_character(name)` | NPC 名から `Character` を返す |
| `days()` | 全日程のリストを返す |
| `_flatten(day)` | （内部）日程データをフラットなステップリストに展開する |

#### `ShareHouseFSM`（implements `IFSM`）
| メソッド/プロパティ | 説明 |
|---------------------|------|
| `current_step` | 現在の `Step` を返す（終端なら `None`） |
| `turn_history` | 現在の会話履歴のコピーを返す |
| `add_turn(role, content)` | 会話ターンを履歴に追加する |
| `advance()` | 次のステップへ進み `AdvanceResult` を返す |
| `dump()` | 状態を dict にシリアライズする |
| `load(scenario, data)` | `dump()` の dict から復元する（クラスメソッド） |

#### `LLMJudge`（implements `IJudge`）
| メソッド | 説明 |
|----------|------|
| `judge(step, user_message)` | claude-haiku で回答十分性を判定する |

#### `RuleJudge`（implements `IJudge`）
| メソッド | 説明 |
|----------|------|
| `judge(step, user_message)` | 文字数（>8）のみで判定する（テスト用・トークン不使用） |

#### `MemoryStore`（implements `IStore`）
インメモリ辞書でセッションデータを保持する。サーバー再起動でデータは消える。

#### `RedisStore`（implements `IStore`）
Redis にセッションデータを TTL 付きで保存する（本番環境用）。

---

### `service.py` — オーケストレーション層

`IFSM`, `IJudge`, `IStore`, `IScenario` を保持し、HTTP レイヤーに高レベル操作を提供する。

#### `FSMService`
| メソッド | 主な呼び出し先 | 説明 |
|----------|--------------|------|
| `start_session(session_id, start_day)` | `ShareHouseFSM` → `store.save` | セッションを初期化し最初の NPC 開幕台詞を返す |
| `handle_message(session_id, user_message)` | `_npc_reply` → `judge.judge` → `fsm.advance` → `store.save` | 1 ターン処理し NPC 返答と FSM 進行結果を返す |

#### `_npc_reply(client, char, step, history, user_message)` — モジュール関数
claude-sonnet で NPC の返答を生成する。API 過負荷（HTTP 529）時は指数バックオフで最大 3 回再試行する。

#### `create_fsm(anthropic_client, scenario_path, use_rule_judge)` — ファクトリ関数
`JsonScenario`, `ShareHouseFSM`, `LLMJudge`（または `RuleJudge`）, `MemoryStore` を生成して `FSMService` を返す。

---

### `app.py` — スタンドアロンサーバー（ポート 8002）

FSM 単体で動作確認するための FastAPI サーバー。`static/` を `/` にマウントし、
`index.html` と `chat.js` をそのまま配信する。

| エンドポイント | メソッド | リクエスト Body | レスポンス |
|---------------|---------|----------------|-----------|
| `/start` | POST | `{ start_day: "Day 1" }` | `{ session_id, day, state, speaker, opening_line, character }` |
| `/chat` | POST | `{ session_id, user_message }` | `{ npc_reply, advance_event, next_* }` |

**`/chat` レスポンスの `advance_event` の値：**

| 値 | 意味 |
|----|------|
| `""` | FSM 進行なし（会話継続） |
| `"next_state"` | 同じ日の次の NPC へ進む |
| `"next_day"` | 翌日の最初の NPC へ進む |
| `"game_complete"` | 全ステップ完了・ゲーム終了 |

`advance_event` が `next_state` / `next_day` の場合、レスポンスに `next_day`, `next_state`, `next_speaker`, `next_opening_line`, `next_character` が追加される。

---

### `static/index.html` と `static/chat.js` — 独立対話フロントエンド

ゲーム画面を持たない対話専用フロントエンド。

**HTML の主要要素（`index.html`）：**

| 要素 ID | 役割 |
|---------|------|
| `avatar` | NPC の絵文字アイコン |
| `npc-name` | NPC 名前表示 |
| `npc-role` | NPC 役職表示 |
| `day-label` | 現在の日付表示 |
| `state-label` | 現在の FSM ステート名表示 |
| `chat-log` | 吹き出しを積み上げるスクロール領域 |
| `user-input` | テキスト入力欄（Textarea） |
| `send-btn` | 送信ボタン |

**`chat.js` の関数一覧：**

| 関数 | 説明 |
|------|------|
| `bubble(type, text, name, color)` | `chat-log` に吹き出し `<div>` を追加しスクロールする |
| `thinking()` | 「思考中...」仮吹き出しを追加して DOM 要素を返す |
| `setUI({day, state, speaker, opening_line, character})` | NPC 情報パネルを更新し開幕台詞を `bubble("npc",...)` で表示する |
| `lock(v)` | `user-input` / `send-btn` の disabled を切り替える |
| `apiStart(startDay)` | `POST /start` を fetch し JSON を返す |
| `apiChat(message)` | `POST /chat` を fetch し JSON を返す |
| `init()` | `apiStart` → `setUI` でページ初期化する |
| `send()` | `apiChat` → `bubble` → `setUI`（advance 時）の一連の処理を行う |

**フロントエンドとサーバーの通信フロー：**

```
ブラウザ                         app.py (FastAPI)          service.py / impl.py
─────────────────────────────────────────────────────────────────────────────
DOMContentLoaded
  └─ init()
       └─ POST /start ──────────────────────────────►  start_session()
          { start_day: "Day 1" }                         └─ ShareHouseFSM 初期化
                                                          └─ store.save()
          ◄─────────────────────────────────────────  { session_id, speaker,
       setUI(data)                                        opening_line, character }
       lock(false)

ユーザーが送信ボタンを押す（または Enter）
  └─ send()
       └─ POST /chat ───────────────────────────────►  handle_message()
          { session_id, user_message }                   ├─ _npc_reply()  [LLM]
                                                          ├─ judge.judge() [LLM]
                                                          └─ fsm.advance() [条件付き]
          ◄─────────────────────────────────────────  { npc_reply,
       bubble("npc", npc_reply)                           advance_event,
       [advance_event あり]                               next_speaker, ... }
         └─ setUI(next_*)  # 次 NPC へ切り替え
       lock(false)
```

**`advance_event` による分岐（`send()` 内）：**

```javascript
if (advance_event === "game_complete")  → 終了メッセージを表示して処理終了
if (advance_event)                      → setUI(next_*) で次 NPC へ切り替え
// advance_event === ""                 → そのまま会話継続（入力を再有効化）
```

---

## FSM 状態遷移の概要

```
start_session()
  └─ ShareHouseFSM(scenario, "Day 1")
       └─ current_step → 最初の Step（speaker, content）

handle_message() ← ユーザー入力ごとに呼び出し
  ├─ _npc_reply()    → LLM で NPC 返答生成
  ├─ judge.judge()   → 回答十分性を判定
  └─ [answered=True]
       └─ fsm.advance()
            ├─ "next_state"    → 同じ日の次の NPC へ
            ├─ "next_day"      → 翌日の最初の NPC へ
            └─ "game_complete" → ゲーム終了
```

---

## `bridge.py`（ルート）との接続

`fsm` パッケージは `game` を直接 import しない。  
`bridge.py` が `FSMDialogBridge` を実装し、`FSMService` をラップして `game.IDialogBridge` に適合させる。

```
bridge.py
  ├─ FSMDialogBridge.on_start()       → fsm_service.start_session()
  └─ FSMDialogBridge.on_user_message() → fsm_service.handle_message()
```

---

## フロントエンドからバックエンドまでの関数呼び出しフロー

### ① 起動時（ページ読み込み）

```
[chat.js]              [app.py]            [service.py]        [impl.py]
──────────────────────────────────────────────────────────────────────────────
DOMContentLoaded
  └─ init()
       └─ lock(true)
       └─ apiStart("Day 1")
            └─ POST /start ──► start()
               { start_day }     └─ uuid生成 → sid
                                  └─ fsm_svc
                                       .start_session(sid, day)
                                         └─ ShareHouseFSM(scenario, day)
                                              └─ scenario          JsonScenario
                                                 .get_step(day, 0)  ._flatten(day)
                                                 .get_character()    JSONから読込
                                              └─ fsm.add_turn()
                                              └─ store.save()      MemoryStore
               ◄──────────────── { session_id, speaker,
       S.sessionId = ...           opening_line, character }
       setUI(data)
         └─ bubble("npc", opening_line)
       lock(false)
```

### ② メッセージ送信時（ユーザーが入力して送信）

```
[chat.js]              [app.py]            [service.py]        [impl.py / LLM]
──────────────────────────────────────────────────────────────────────────────
send()
  └─ lock(true)
  └─ bubble("user", text)
  └─ thinking()          # 「思考中...」表示
  └─ apiChat(text)
       └─ POST /chat ───► chat()
          { session_id,    └─ fsm_svc
            user_message }      .handle_message(sid, msg)
                                  └─ store.get(sid)    MemoryStore
                                  └─ ShareHouseFSM.load()
                                  └─ fsm.add_turn("user", msg)
                                  └─ _npc_reply()      claude-sonnet [LLM]
                                       └─ 529エラー時は指数バックオフで再試行
                                  └─ fsm.add_turn("assistant", reply)
                                  └─ judge.judge()     LLMJudge [LLM]
                                       └─ claude-haiku で回答十分性を判定
                                  └─ [answered=True]
                                       └─ fsm.advance()
                                            └─ scenario.get_step(day, idx+1)
                                  └─ store.save(sid, fsm.dump())
          ◄────────────── { npc_reply, advance_event, next_* }
  th.remove()            # 「思考中...」削除
  bubble("npc", npc_reply)

  [advance_event の分岐]
    ""             → lock(false)  # 会話継続
    "next_state"   → setUI(next_*)  # 同日次NPC
    "next_day"     → bubble("sys", next_day) → setUI(next_*)
    "game_complete"→ bubble("sys", "ゲーム終了") → 処理終了
```

### ③ FSM 進行の詳細（`fsm.advance()` 内部）

```
[service.py] handle_message()
  └─ fsm.advance()                    ShareHouseFSM.advance()
       └─ self._idx += 1
       └─ scenario.get_step(day, idx) JsonScenario.get_step()
            └─ _flatten(day)           JSONの state_list を展開
            └─ steps[idx] が存在       → AdvanceResult("next_state", step, char)
            └─ steps[idx] が存在しない → 翌日へ
                 └─ scenario.days()
                 └─ self._day = days[di+1]
                 └─ get_step(new_day, 0) → AdvanceResult("next_day", step, char)
                 └─ 翌日もない          → AdvanceResult("game_complete")
```
