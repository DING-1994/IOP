/**
 * game/static/game.js — 独立游戏前端
 * 只有 Canvas 像素渲染 + WASD 移动，无对话系统
 * 依赖 render.js 提供的常量与绘制函数
 * API: POST /start  POST /move
 */

// ── 运行时状态 ────────────────────────────────────────────

const keys = {};
let tick = 0, lastMove = 0;
let currentDay = "Day 1";
const player = { x: 7, y: 6 };

let canvas, ctx;

// ── ゲーム専用：drawNPC（ターゲット強調なし） ──────────────────

/**
 * 機能：NPC キャラクターを指定マス目に Canvas 描画する（目標 NPC の強調表示なし）。
 * 入力：name（NPC 名前文字列）、col（列インデックス）、row（行インデックス）、tick（アニメーションフレームカウンター）
 * 出力：なし
 */
function drawNPC(name, col, row, tick) {
  const px = col*TILE+TILE/2, py = row*TILE+TILE/2;
  const color = NPC_META[name]?.color ?? "#aaa";
  const bob = Math.floor(tick/14)%2===0 ? 0 : -1;
  const hairColors = {DaVinci:"#8b0000",Donatello:"#2c3e50",Michelangelo:"#d4a017",Raffaello:"#c0c0c0"};

  ctx.fillStyle=PAL.shadow; ctx.beginPath(); ctx.ellipse(px,py+14,9,3,0,0,Math.PI*2); ctx.fill();
  ctx.fillStyle=color+"66"; ctx.fillRect(px-7,py-6+bob,14,16);
  ctx.fillStyle="#c8a96e"; ctx.fillRect(px-6,py-17+bob,12,13);
  ctx.fillStyle=hairColors[name]??"#333"; ctx.fillRect(px-6,py-17+bob,12,4);
  ctx.fillStyle="#555";
  ctx.fillRect(px-3,py-12+bob,2,2); ctx.fillRect(px+1,py-12+bob,2,2);
  ctx.fillStyle="rgba(0,0,0,0.72)";
  const tw = name.length*5.5+10;
  ctx.fillRect(px-tw/2,py-30,tw,12);
  ctx.fillStyle=color; ctx.font="8px monospace"; ctx.textAlign="center";
  ctx.fillText(name,px,py-21);
}

// ── ゲームループ ─────────────────────────────────────────────

/**
 * 機能：毎フレームの入力処理・移動 API 呼び出し・Canvas 描画を行うメインゲームループ。
 * 入力：なし（requestAnimationFrame から自動呼び出し）
 * 出力：なし
 */
function gameLoop() {
  tick++;
  const now = Date.now();
  if (now - lastMove > 130) {
    let nx=player.x, ny=player.y;
    if (keys["ArrowUp"]   ||keys["w"]) ny--;
    if (keys["ArrowDown"] ||keys["s"]) ny++;
    if (keys["ArrowLeft"] ||keys["a"]) nx--;
    if (keys["ArrowRight"]||keys["d"]) nx++;
    if (nx !== player.x || ny !== player.y) {
      const dx = nx - player.x, dy = ny - player.y;
      if (!isBlocked(nx, ny)) {
        player.x=nx; player.y=ny; lastMove=now;
        fetch("/move", {
          method:"POST", headers:{"Content-Type":"application/json"},
          body: JSON.stringify({dx, dy, day:currentDay}),
        }).catch(()=>{});
      }
    }
  }

  ctx.clearRect(0,0,canvas.width,canvas.height);
  for (let r=0;r<ROWS;r++) for (let c=0;c<COLS;c++) drawTile(c,r,MAP[r]?.[c]??0);
  for (const [name,[col,row]] of Object.entries(NPC_POS[currentDay]??{}))
    drawNPC(name, col, row, tick);
  drawPlayer(tick);

  ctx.fillStyle="rgba(0,0,0,0.6)"; ctx.fillRect(0,0,canvas.width,20);
  ctx.fillStyle="#f0c040"; ctx.font="bold 11px monospace"; ctx.textAlign="left";
  ctx.fillText(currentDay, 8, 14);

  requestAnimationFrame(gameLoop);
}

// ── 启动 ─────────────────────────────────────────────────

document.addEventListener("keydown", e => { keys[e.key]=true; });
document.addEventListener("keyup",   e => { keys[e.key]=false; });

document.addEventListener("DOMContentLoaded", () => {
  canvas = document.getElementById("game");
  ctx    = canvas.getContext("2d");

  currentDay = new URLSearchParams(location.search).get("day") || "Day 1";
  document.getElementById("day-label").textContent = currentDay;

  gameLoop();
});
