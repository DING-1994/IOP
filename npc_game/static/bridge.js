/**
 * static/bridge.js — Bridge 前端逻辑
 * 依赖 /game/render.js 提供的常量与渲染函数
 * API: POST /start  POST /move  POST /chat
 *
 * 交互方式：靠近目标 NPC 后按 E 键开始对话
 * FSM 判断回答充分后指示前往下一位 NPC
 */

// ── 运行时状态 ────────────────────────────────────────────

const S = {
  sessionId:  null,
  speaker:    "",
  character:  {},
  processing: false,   // API 调用中（阻塞移动和输入）
};

// 脚本引导状态
let expectedSpeaker = "";   // 当前应前往的 NPC
let pendingLine     = "";   // 该 NPC 的开场白
let pendingChar     = {};
let pendingState    = "";
let pendingDay      = "";

let dialogActive  = false;  // 对话框是否展开
let activeSpeaker = "";     // 画面中高亮的 NPC（对话中）

// Canvas 浮动提示
let hintMsg   = "";
let hintUntil = 0;

const keys = {};
let tick = 0, lastMove = 0;
let currentDay = "Day 1";
const player = { x: 7, y: 6 };

let canvas, ctx;
const $ = id => document.getElementById(id);

// ── Bridge 专属绘制：drawNPC（含 isTarget 指示） ──────────

// isActive = 対話中（全輝度 + 💬 アイコン表示）
// isTarget = スクリプト指定の次訪問先（▼ バウンスアニメーション）
/**
 * 機能：NPC キャラクターを Canvas 描画する。対話中は全輝度＋吹き出し、目標 NPC は▼マーカーを表示し、
 *       それ以外の NPC は暗く表示する。
 * 入力：name（NPC 名前文字列）、col（列インデックス）、row（行インデックス）、
 *       isActive（対話中フラグ）、isTarget（次訪問先フラグ）、tick（アニメーションフレームカウンター）
 * 出力：なし
 */
function drawNPC(name, col, row, isActive, isTarget, tick) {
  const px = col*TILE+TILE/2, py = row*TILE+TILE/2;
  const color = NPC_META[name]?.color ?? "#aaa";
  const bob = Math.floor(tick/14)%2===0 ? 0 : -1;
  const hairColors = {DaVinci:"#8b0000",Donatello:"#2c3e50",Michelangelo:"#d4a017",Raffaello:"#c0c0c0"};

  const dimmed = !isActive && !isTarget;

  ctx.fillStyle=PAL.shadow; ctx.beginPath(); ctx.ellipse(px,py+14,9,3,0,0,Math.PI*2); ctx.fill();
  ctx.fillStyle = dimmed ? color+"44" : color; ctx.fillRect(px-7,py-6+bob,14,16);
  ctx.fillStyle = dimmed ? "#c8a96e44" : "#c8a96e"; ctx.fillRect(px-6,py-17+bob,12,13);
  ctx.fillStyle = dimmed ? (hairColors[name]??"#333")+"44" : (hairColors[name]??"#333");
  ctx.fillRect(px-6,py-17+bob,12,4);
  ctx.fillStyle = dimmed ? "#55544" : (isActive ? "#1a1a2e" : "#555");
  ctx.fillRect(px-3,py-12+bob,2,2); ctx.fillRect(px+1,py-12+bob,2,2);

  if (isActive && Math.floor(tick/18)%2===0) {
    ctx.font="bold 13px serif"; ctx.textAlign="center"; ctx.fillStyle=color;
    ctx.fillText("💬",px,py-22+bob);
  }
  if (isTarget && !isActive) {
    const bounce = Math.sin(tick * 0.12) * 3;
    ctx.font="bold 14px monospace"; ctx.textAlign="center"; ctx.fillStyle=color;
    ctx.fillText("▼", px, py-34+bounce);
  }

  ctx.fillStyle = dimmed ? "rgba(0,0,0,0.3)" : "rgba(0,0,0,0.72)";
  const tw = name.length*5.5+10;
  ctx.fillRect(px-tw/2,py-30,tw,12);
  ctx.fillStyle = dimmed ? color+"66" : color;
  ctx.font="8px monospace"; ctx.textAlign="center";
  ctx.fillText(name,px,py-21);
}

// ── 対話開閉 ─────────────────────────────────────────────

/**
 * 機能：サイドパネルに次訪問先 NPC の情報と「E キーで対話開始」案内を表示する。
 * 入力：なし（グローバル変数 expectedSpeaker を参照）
 * 出力：なし
 */
function showHint() {
  const color = NPC_META[expectedSpeaker]?.color ?? "#f0c040";
  const emoji = NPC_META[expectedSpeaker]?.emoji ?? "❓";
  $("avatar").textContent = emoji;
  $("avatar").style.borderColor = "#555";
  $("npc-name").textContent = expectedSpeaker || "...";
  $("npc-name").style.color = color;
  $("npc-role").textContent = "[ 靠近后按 E 开始对话 ]";
  $("state-label").textContent = "—";
}

/**
 * 機能：対話パネルを開き、NPC 情報と開幕台詞を表示して入力を有効化する。
 * 入力：なし（グローバル変数 expectedSpeaker, pendingLine, pendingChar 等を参照）
 * 出力：なし
 */
function openDialog() {
  dialogActive  = true;
  activeSpeaker = expectedSpeaker;
  S.speaker     = expectedSpeaker;
  S.character   = pendingChar;

  $("day-label").textContent   = pendingDay;
  $("state-label").textContent = pendingState;
  const av = $("avatar");
  av.textContent = pendingChar.emoji; av.style.borderColor = pendingChar.color;
  $("npc-name").textContent = expectedSpeaker; $("npc-name").style.color = pendingChar.color;
  $("npc-role").textContent = pendingChar.role;

  $("chat-log").innerHTML = "";
  bubble("npc", pendingLine, expectedSpeaker, pendingChar.color);

  $("user-input").disabled = false;
  $("send-btn").disabled   = false;
  $("user-input").focus();
}

/**
 * 機能：対話パネルを閉じ、入力を無効化してヒント表示に戻す。
 * 入力：なし
 * 出力：なし
 */
function closeDialog() {
  dialogActive    = false;
  activeSpeaker   = "";
  S.processing    = false;
  $("user-input").disabled = true;
  $("send-btn").disabled   = true;
  showHint();
}

/**
 * 機能：プレイヤーの隣接マス（距離 1 以内）にいる NPC の名前を返す。
 * 入力：なし（グローバル変数 player, currentDay を参照）
 * 出力：隣接 NPC の名前文字列、または存在しない場合は null
 */
function getNearbyNPC() {
  for (const [name, [nc, nr]] of Object.entries(NPC_POS[currentDay] ?? {})) {
    if (Math.abs(nc - player.x) <= 1 && Math.abs(nr - player.y) <= 1) return name;
  }
  return null;
}

/**
 * 機能：指定 NPC との対話開始を試みる。対話中・処理中・目標 NPC 不一致の場合は開始しない。
 * 入力：name（試みる NPC の名前文字列、または null）
 * 出力：なし
 */
function tryStartDialog(name) {
  if (!name || dialogActive || S.processing) return;
  if (name !== expectedSpeaker) {
    showCanvasHint(`先去找 ${expectedSpeaker}`);
    return;
  }
  openDialog();
}

/**
 * 機能：Canvas 中央に 2 秒間表示するフローティングヒントメッセージを設定する。
 * 入力：msg（表示するメッセージ文字列）
 * 出力：なし
 */
function showCanvasHint(msg) {
  hintMsg   = msg;
  hintUntil = Date.now() + 2000;
}

// ── ゲームループ ─────────────────────────────────────────────

/**
 * 機能：毎フレームの入力処理・移動 API 呼び出し・Canvas 描画（NPC 強調表示・ヒント含む）を行うメインゲームループ。
 * 入力：なし（requestAnimationFrame から自動呼び出し）
 * 出力：なし
 */
function gameLoop() {
  tick++;
  const now = Date.now();

  if (!S.processing && !dialogActive && now - lastMove > 130) {
    let nx=player.x, ny=player.y;
    if (keys["ArrowUp"]   ||keys["w"]) ny--;
    if (keys["ArrowDown"] ||keys["s"]) ny++;
    if (keys["ArrowLeft"] ||keys["a"]) nx--;
    if (keys["ArrowRight"]||keys["d"]) nx++;
    if (nx !== player.x || ny !== player.y) {
      const dx = nx - player.x, dy = ny - player.y;
      if (!isBlocked(nx, ny)) {
        player.x=nx; player.y=ny; lastMove=now;
        if (S.sessionId) {
          fetch("/move", {
            method:"POST", headers:{"Content-Type":"application/json"},
            body: JSON.stringify({session_id:S.sessionId, dx, dy, day:currentDay}),
          }).catch(()=>{});
        }
      }
    }
  }

  ctx.clearRect(0,0,canvas.width,canvas.height);
  for (let r=0;r<ROWS;r++) for (let c=0;c<COLS;c++) drawTile(c,r,MAP[r]?.[c]??0);
  for (const [name,[col,row]] of Object.entries(NPC_POS[currentDay]??{}))
    drawNPC(name, col, row, name===activeSpeaker, name===expectedSpeaker, tick);
  drawPlayer(tick);

  ctx.fillStyle="rgba(0,0,0,0.6)"; ctx.fillRect(0,0,canvas.width,20);
  ctx.fillStyle="#f0c040"; ctx.font="bold 11px monospace"; ctx.textAlign="left";
  ctx.fillText(currentDay + (activeSpeaker ? "  —  " + activeSpeaker : ""), 8, 14);

  if (Date.now() < hintUntil) {
    const w = hintMsg.length * 8 + 24;
    const cx = canvas.width / 2, cy = canvas.height / 2;
    ctx.fillStyle = "rgba(0,0,0,0.78)";
    ctx.fillRect(cx - w/2, cy - 18, w, 28);
    ctx.fillStyle = "#f0c040"; ctx.font = "12px monospace"; ctx.textAlign = "center";
    ctx.fillText(hintMsg, cx, cy);
  }

  requestAnimationFrame(gameLoop);
}

// ── API ───────────────────────────────────────────────────

/**
 * 機能：/start エンドポイントを呼び出して新しいセッションを開始し、初期 NPC 情報を取得する。
 * 入力：startDay（開始日文字列、例: "Day 1"）
 * 出力：session_id, day, state, speaker, opening_line, character を含む Promise<dict>
 */
async function apiStart(startDay) {
  const r = await fetch("/start", {
    method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({start_day: startDay}),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

/**
 * 機能：/chat エンドポイントにユーザーメッセージを送信し、NPC 返答と FSM 進行結果を取得する。
 * 入力：message（ユーザー入力テキスト）
 * 出力：npc_reply, advance_event 等を含む Promise<dict>
 */
async function apiChat(message) {
  const r = await fetch("/chat", {
    method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({session_id:S.sessionId, user_message:message}),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

// ── 対話 UI ───────────────────────────────────────────────

/**
 * 機能：チャットログに吹き出し要素を追加して最下部にスクロールする。
 * 入力：type（"npc" / "user" / "sys"）、text（表示テキスト）、name（NPC 名前、npc タイプ時）、
 *       color（NPC 名前の色、npc タイプ時）
 * 出力：作成した DOM 要素
 */
function bubble(type, text, name, color) {
  const log = $("chat-log");
  const d = document.createElement("div");
  d.className = "bubble " + type;
  if (type==="npc") d.innerHTML = `<b style="color:${color}">${name}</b><br>${text}`;
  else d.textContent = type==="user" ? `你：${text}` : `▶ ${text}`;
  log.appendChild(d);
  log.scrollTop = log.scrollHeight;
  return d;
}

/**
 * 機能：「思考中...」の一時的な吹き出しをチャットログに追加して返す。
 * 入力：なし
 * 出力：作成した DOM 要素（後で .remove() で削除する）
 */
function thinking() {
  const d = bubble("sys", "思考中...");
  d.classList.add("thinking");
  return d;
}

// ── メインフロー ────────────────────────────────────────────────

/**
 * 機能：ページ読み込み時に /start を呼び出してセッションを初期化し、最初の目標 NPC をセットする。
 * 入力：なし（URL クエリパラメータ day を参照）
 * 出力：なし
 */
async function init() {
  const startDay = new URLSearchParams(location.search).get("day") || "Day 1";
  const data = await apiStart(startDay).catch(e => {
    bubble("sys", "⚠ 连接失败：" + e.message);
    return null;
  });
  if (!data) return;

  S.sessionId     = data.session_id;
  expectedSpeaker = data.speaker;
  pendingLine     = data.opening_line;
  pendingChar     = data.character   ?? {};
  pendingState    = data.state       ?? "";
  pendingDay      = data.day;
  currentDay      = data.day;

  $("day-label").textContent = data.day;
  showHint();
  $("chat-log").innerHTML = "";
  bubble("sys", `前往 ${expectedSpeaker} 开始对话`);
}

/**
 * 機能：ユーザー入力を送信し、NPC 返答を表示する。FSM advance 時は次の NPC へ誘導して対話を閉じる。
 * 入力：なし（テキストエリアの値を参照）
 * 出力：なし
 */
async function send() {
  if (S.processing || !dialogActive) return;
  const text = $("user-input").value.trim();
  if (!text) return;
  $("user-input").value = "";

  S.processing = true;
  $("user-input").disabled = true;
  $("send-btn").disabled   = true;

  bubble("user", text);
  const th = thinking();

  const resp = await apiChat(text).catch(e => {
    th.remove();
    bubble("sys", "⚠ " + e.message);
    S.processing = false;
    $("user-input").disabled = false;
    $("send-btn").disabled   = false;
  });
  if (!resp) return;
  th.remove();

  bubble("npc", resp.npc_reply, S.speaker, S.character.color);

  if (resp.advance_event === "game_complete") {
    bubble("sys", "🎉 游戏结束！");
    S.processing = false;
    return;
  }

  if (resp.advance_event) {
    await new Promise(r => setTimeout(r, 800));
    bubble("sys", resp.advance_event === "next_day"
      ? `── ${resp.next_day} ──`
      : "── 对话完成，前往下一位 ──");
    await new Promise(r => setTimeout(r, 600));

    expectedSpeaker = resp.next_speaker;
    pendingLine     = resp.next_opening_line;
    pendingChar     = resp.next_character   ?? {};
    pendingState    = resp.next_state       ?? "";
    pendingDay      = resp.next_day         ?? currentDay;
    currentDay      = pendingDay;

    closeDialog();
    showCanvasHint(`前往 ${expectedSpeaker}`);
    return;
  }

  S.processing = false;
  $("user-input").disabled = false;
  $("send-btn").disabled   = false;
  $("user-input").focus();
}

// ── 启动 ─────────────────────────────────────────────────

document.addEventListener("keydown", e => {
  if (e.target.tagName === "TEXTAREA" || e.target.tagName === "INPUT") return;
  keys[e.key] = true;
  if (e.key === "e" || e.key === "E") {
    e.preventDefault();
    tryStartDialog(getNearbyNPC());
  }
});
document.addEventListener("keyup", e => {
  if (e.target.tagName === "TEXTAREA" || e.target.tagName === "INPUT") return;
  keys[e.key] = false;
});

document.addEventListener("DOMContentLoaded", () => {
  canvas = document.getElementById("game");
  ctx    = canvas.getContext("2d");

  $("send-btn").onclick = send;
  $("user-input").addEventListener("keydown", e => {
    if (e.key==="Enter" && !e.shiftKey) { e.preventDefault(); send(); }
  });

  gameLoop();
  init();
});
