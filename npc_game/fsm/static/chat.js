/**
 * fsm/static/chat.js — 独立对话前端
 * 只有对话框 UI，无游戏画面
 * API: POST /start  POST /chat
 */

// ── 运行时状态 ────────────────────────────────────────────

const S = {
  sessionId:  null,
  speaker:    "",
  character:  {},
  processing: false,
};

const $ = id => document.getElementById(id);

// ── UI ────────────────────────────────────────────────────

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
  if (type === "npc") d.innerHTML = `<b style="color:${color}">${name}</b><br>${text}`;
  else d.textContent = type === "user" ? `你：${text}` : `▶ ${text}`;
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

/**
 * 機能：サイドパネルの NPC 情報と開幕台詞を更新し、セッション状態変数をセットする。
 * 入力：day（日付文字列）、state（FSM ステート名）、speaker（NPC 名前）、
 *       opening_line（NPC の開幕台詞）、character（NPC キャラクター情報 dict）
 * 出力：なし
 */
function setUI({ day, state, speaker, opening_line, character }) {
  $("day-label").textContent = day;
  $("state-label").textContent = state;
  S.speaker = speaker; S.character = character;
  const av = $("avatar");
  av.textContent = character.emoji; av.style.borderColor = character.color;
  $("npc-name").textContent = speaker; $("npc-name").style.color = character.color;
  $("npc-role").textContent = character.role;
  bubble("npc", opening_line, speaker, character.color);
}

/**
 * 機能：入力フィールドと送信ボタンのロック状態を切り替える。
 * 入力：v（true でロック、false でアンロック）
 * 出力：なし
 */
function lock(v) {
  S.processing = v;
  $("user-input").disabled = v;
  $("send-btn").disabled = v;
  if (!v) $("user-input").focus();
}

// ── API ───────────────────────────────────────────────────

/**
 * 機能：/start エンドポイントを呼び出して新しいセッションを開始し、初期 NPC 情報を取得する。
 * 入力：startDay（開始日文字列、例: "Day 1"）
 * 出力：session_id, day, state, speaker, opening_line, character を含む Promise<dict>
 */
async function apiStart(startDay) {
  const r = await fetch("/start", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ start_day: startDay }),
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
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: S.sessionId, user_message: message }),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

// ── メインフロー ────────────────────────────────────────────────

/**
 * 機能：ページ読み込み時に /start を呼び出してセッションを初期化し、最初の NPC 情報を表示する。
 * 入力：なし（URL クエリパラメータ day を参照）
 * 出力：なし
 */
async function init() {
  lock(true);
  bubble("sys", "连接中...");
  const data = await apiStart(
    new URLSearchParams(location.search).get("day") || "Day 1"
  );
  S.sessionId = data.session_id;
  setUI(data);
  lock(false);
}

/**
 * 機能：ユーザー入力を送信し、NPC 返答を表示する。FSM advance 時は次の NPC 情報を setUI で更新する。
 * 入力：なし（テキストエリアの値を参照）
 * 出力：なし
 */
async function send() {
  if (S.processing) return;
  const text = $("user-input").value.trim();
  if (!text) return;
  $("user-input").value = "";
  lock(true);
  bubble("user", text);
  const th = thinking();

  const resp = await apiChat(text).catch(e => {
    th.remove(); bubble("sys", "⚠ " + e.message); lock(false);
  });
  if (!resp) return;
  th.remove();

  bubble("npc", resp.npc_reply, S.speaker, S.character.color);

  if (resp.advance_event === "game_complete") {
    bubble("sys", "🎉 游戏结束！"); return;
  }
  if (resp.advance_event) {
    await new Promise(r => setTimeout(r, 800));
    bubble("sys", resp.advance_event === "next_day" ? `── ${resp.next_day} ──` : "── 下一位 ──");
    await new Promise(r => setTimeout(r, 300));
    setUI({
      day:          resp.next_day,
      state:        resp.next_state,
      speaker:      resp.next_speaker,
      opening_line: resp.next_opening_line,
      character:    resp.next_character,
    });
  }
  lock(false);
}

// ── 启动 ─────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
  $("send-btn").onclick = send;
  $("user-input").addEventListener("keydown", e => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
  });
  init();
});
