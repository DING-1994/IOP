# game パッケージ

ShareHouse RPG のゲームロジック（マップ・プレイヤー移動）を担当するパッケージ。  
FSM（対話システム）とは独立して動作し、`bridge.py` からのみ接続される。

---

## ファイル構成

```
game/
├── protocol.py      # インターフェース定義層（データクラス + Protocol）
├── service.py       # オーケストレーション層（GameService）
├── impl.py          # 実装層（RoomScene, Player）
├── app.py           # スタンドアロン FastAPI サーバー（ポート 8001）
└── static/
    ├── render.js    # 共有レンダリングライブラリ（マップ・プレイヤー描画）
    ├── game.js      # ゲーム専用フロントエンド（NPC 描画・ゲームループ）
    └── index.html   # 独立ゲーム画面
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

データクラスと Protocol（抽象インターフェース）のみを定義。実装ロジックなし。

| 名前 | 種別 | 説明 |
|------|------|------|
| `PlayerState` | dataclass | プレイヤー座標 `(x, y)` |
| `NPCState` | dataclass | NPC の名前・座標・色・絵文字 |
| `SceneState` | dataclass | 現在の日付・NPC 一覧 |
| `DialogEvent` | dataclass | 対話イベント（session_id + ユーザー入力） |
| `DialogResponse` | dataclass | 対話応答（NPC 返答 + FSM 進行結果） |
| `IScene` | Protocol | シーン状態取得・衝突判定のインターフェース |
| `IPlayer` | Protocol | プレイヤー状態取得・移動のインターフェース |
| `IDialogBridge` | Protocol | 外部対話システムとの唯一の接続点 |

---

### `impl.py` — 実装層

`protocol.py` のインターフェースを実装するクラス群。

#### `RoomScene`
| メソッド | 説明 |
|----------|------|
| `get_scene_state(day)` | 指定日の NPC 一覧と状態を返す |
| `is_blocked(col, row, day)` | マス目が移動不可かどうかを判定する |

#### `Player`
| メソッド/プロパティ | 説明 |
|---------------------|------|
| `state` | 現在の `PlayerState (x, y)` を返す |
| `try_move(dx, dy, scene, day)` | 衝突判定後に座標を更新し、成否を返す |

---

### `service.py` — オーケストレーション層

`IScene` と `IPlayer` を保持し、HTTP レイヤーに高レベル操作を提供する。

#### `GameService`
| メソッド | 呼び出し先 | 説明 |
|----------|-----------|------|
| `move(dx, dy, day)` | `player.try_move` → `scene.is_blocked` | プレイヤーを移動させ新座標を返す |
| `get_scene(day)` | `scene.get_scene_state` | シーン全体の状態を返す |
| `has_dialog()` | — | 対話ブリッジが注入済みかどうかを返す |
| `start_dialog(session_id, day)` | `bridge.on_start` | 対話セッションを開始する |
| `send_message(event)` | `bridge.on_user_message` | ユーザーメッセージを FSM に転送する |

#### `create_game(bridge?)` — ファクトリ関数
`RoomScene` と `Player` を生成して `GameService` を返す。  
`bridge` を渡すとゲームに対話機能が追加される（省略時は移動のみ）。

---

### `app.py` — スタンドアロンサーバー（ポート 8001）

ゲーム単体で動作確認するための FastAPI サーバー。

| エンドポイント | 処理 |
|---------------|------|
| `POST /start` | `game_service.get_scene` を呼び出し NPC 一覧を返す |
| `POST /move` | `game_service.move` を呼び出し新座標を返す |

---

### `static/render.js` — 共有レンダリングライブラリ

`game.js`（独立サーバー用）と `static/bridge.js`（ブリッジ用）の両方から `/game/render.js` として読み込まれる共有ライブラリ。

| 定数/関数 | 説明 |
|-----------|------|
| `NPC_META` | NPC ごとの色・絵文字 |
| `NPC_POS` | 日付ごとの NPC 初期座標 |
| `MAP` | タイル種別の 2D 配列 |
| `PAL` | 色パレット |
| `drawTile(x, y, t)` | タイルを Canvas に描画する |
| `drawPlayer(tick)` | プレイヤーを Canvas に描画する |
| `isBlocked(col, row)` | マス目の移動可否を判定する |

---

### `static/game.js` — ゲーム専用フロントエンド

対話システムを持たない独立ゲーム画面のロジック。`render.js` の関数を使用する。

| 関数 | 説明 |
|------|------|
| `drawNPC(name, col, row, tick)` | NPC を描画する（強調表示なし） |
| `gameLoop()` | 入力処理 → `/move` 呼び出し → Canvas 描画を毎フレーム実行 |

**呼び出しフロー（フロントエンド）:**
```
DOMContentLoaded
  └─ gameLoop() ← requestAnimationFrame でループ
       ├─ WASD 入力 → POST /move
       ├─ drawTile() × COLS×ROWS   [render.js]
       ├─ drawNPC() × NPC数        [game.js]
       └─ drawPlayer()             [render.js]
```

---

## `IDialogBridge` による FSM との接続

`game` パッケージは FSM を直接 import しない。  
`bridge.py`（ルート）が `FSMDialogBridge` を実装し、`create_game(bridge=...)` に渡すことで接続する。

```
bridge.py
  └─ FSMDialogBridge(implements IDialogBridge)
       └─ 渡される先: create_game(bridge=FSMDialogBridge)
            └─ GameService.bridge として保持
```

---

## フロントエンドからバックエンドまでの関数呼び出しフロー

### ① 起動時（ページ読み込み）

```
[game.js]                [app.py]               [service.py]          [impl.py]
─────────────────────────────────────────────────────────────────────────────────
DOMContentLoaded
  └─ gameLoop() 開始
  └─ POST /start ───────► start()
     { day: "Day 1" }       └─ game_service
                                 .get_scene(day)
                                   └─ scene              RoomScene
                                      .get_scene_state()  .get_scene_state(day)
                                                            └─ NPC_POSから
                                                               NPCState 生成
     ◄─────────────────── { npcs, day, ... }
```

### ② 毎フレーム（WASD 移動）

```
[game.js]                [app.py]               [service.py]          [impl.py]
─────────────────────────────────────────────────────────────────────────────────
gameLoop()
  ├─ requestAnimationFrame でループ
  ├─ drawTile() × 165    [render.js]
  ├─ drawNPC() × NPC数   [game.js]
  └─ drawPlayer()        [render.js]

[キー入力あり]
  └─ POST /move ────────► move()
     { dx, dy, day }       └─ game_service
                                 .move(dx, dy, day)
                                   └─ player              Player
                                      .try_move()          .try_move(dx, dy,
                                                             scene, day)
                                                            └─ scene
                                                               .is_blocked()
                                                                └─ MAP参照
                                                                   NPC座標確認
     ◄─────────────────── { x, y }
  player.x, player.y 更新
```

### ③ 描画の詳細（毎フレーム・API 呼び出しなし）

```
[game.js] gameLoop()
  │
  ├─ [render.js] drawTile(c, r, MAP[r][c])
  │     └─ PAL の色で Canvas に矩形・図形を描画
  │
  ├─ [game.js] drawNPC(name, col, row, tick)
  │     └─ NPC_META[name].color で NPC スプライトを描画
  │
  └─ [render.js] drawPlayer(tick)
        └─ player.x, player.y の位置にプレイヤーを描画
```
