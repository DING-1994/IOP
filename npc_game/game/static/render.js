/**
 * game/static/render.js — 共享渲染库
 * 地图数据 + 通用绘制函数，供 game.js 和 bridge.js 共同使用
 * 依赖外部全局变量：ctx, currentDay, player, keys
 */

// ── 地图与角色数据 ────────────────────────────────────────

const NPC_META = {
  DaVinci:      { color: "#e74c3c", emoji: "🎨" },
  Donatello:    { color: "#3498db", emoji: "🔧" },
  Michelangelo: { color: "#f39c12", emoji: "🖌️" },
  Raffaello:    { color: "#9b59b6", emoji: "🌸" },
};

const NPC_POS = {
  "Day 1": { DaVinci:[5,3], Donatello:[9,3], Michelangelo:[5,7] },
  "Day 2": { Raffaello:[10,2], DaVinci:[5,5] },
  "Day 3": { DaVinci:[5,3], Donatello:[9,3], Michelangelo:[4,7] },
  "Day 4": { Raffaello:[3,7], Donatello:[9,6] },
  "Day 5": { DaVinci:[5,3], Raffaello:[10,3], Michelangelo:[3,7], Donatello:[9,7] },
};

const TILE = 36, COLS = 15, ROWS = 11;

const MAP = [
  [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],
  [1,5,0,0,0,2,2,2,0,0,0,6,6,5,1],
  [1,0,0,0,0,2,3,2,0,0,0,0,0,0,1],
  [1,0,0,8,0,2,4,2,0,7,0,0,0,0,1],
  [1,5,0,8,0,2,2,2,0,0,0,0,0,5,1],
  [1,0,0,0,0,0,0,0,0,0,0,0,0,0,1],
  [1,0,0,0,0,0,0,0,0,0,0,0,0,0,1],
  [1,5,0,0,0,4,4,4,0,0,0,0,0,5,1],
  [1,0,0,0,0,4,4,4,0,0,0,0,0,0,1],
  [1,0,0,5,0,0,0,0,0,5,0,0,0,0,1],
  [1,1,1,1,1,1,1,0,1,1,1,1,1,1,1],
];

const PAL = {
  floor:"#2a1a0e", floor2:"#261608", wall:"#1a0e06", wallF:"#3a2010",
  carpet:"#3a2545", carpet2:"#2e1e38",
  sofa:"#8b4513", sofaD:"#6b3510",
  table:"#5d3a1a", tableT:"#7d5a2a",
  plant:"#2d5016", plantL:"#3d7020", pot:"#6b3a1a",
  fridge:"#607080", fridgeL:"#aabbcc",
  tv:"#111", tvS:"#1a3a6a",
  shelf:"#7a5030", shelfD:"#5a3818",
  book1:"#c0392b", book2:"#2980b9", book3:"#27ae60",
  shadow:"rgba(0,0,0,0.4)",
};

// ── 描画関数 ─────────────────────────────────────────────

/**
 * 機能：指定マス目のタイルを種別に応じて Canvas に描画する。
 * 入力：x（列インデックス）、y（行インデックス）、t（タイル種別番号）
 * 出力：なし
 */
function drawTile(x, y, t) {
  const px = x*TILE, py = y*TILE;
  if (t !== 1) {
    ctx.fillStyle = (x+y)%2===0 ? PAL.floor : PAL.floor2;
    ctx.fillRect(px, py, TILE, TILE);
  }
  if (t === 1) {
    ctx.fillStyle = PAL.wall;  ctx.fillRect(px,py,TILE,TILE);
    ctx.fillStyle = PAL.wallF; ctx.fillRect(px+1,py+1,TILE-2,TILE-2);
  } else if (t === 2) {
    ctx.fillStyle = (x+y)%2===0 ? PAL.carpet : PAL.carpet2;
    ctx.fillRect(px+2,py+2,TILE-4,TILE-4);
  } else if (t === 3) {
    ctx.fillStyle=PAL.sofaD; ctx.fillRect(px+2,py+4,TILE-4,TILE-6);
    ctx.fillStyle=PAL.sofa;  ctx.fillRect(px+4,py+6,TILE-8,TILE-14);
    ctx.fillStyle=PAL.sofaD; ctx.fillRect(px+2,py+4,4,TILE-8);
    ctx.fillStyle=PAL.sofaD; ctx.fillRect(px+TILE-6,py+4,4,TILE-8);
  } else if (t === 4) {
    ctx.fillStyle=PAL.table;  ctx.fillRect(px+3,py+4,TILE-6,TILE-8);
    ctx.fillStyle=PAL.tableT; ctx.fillRect(px+4,py+5,TILE-8,5);
  } else if (t === 5) {
    ctx.fillStyle=PAL.pot;    ctx.fillRect(px+12,py+22,12,TILE-22);
    ctx.fillStyle=PAL.plantL; ctx.beginPath();ctx.arc(px+18,py+14,11,0,Math.PI*2);ctx.fill();
    ctx.fillStyle=PAL.plant;  ctx.beginPath();ctx.arc(px+12,py+18,7,0,Math.PI*2);ctx.fill();
    ctx.fillStyle=PAL.plant;  ctx.beginPath();ctx.arc(px+24,py+18,7,0,Math.PI*2);ctx.fill();
  } else if (t === 6) {
    ctx.fillStyle=PAL.fridge; ctx.fillRect(px+4,py+2,TILE-8,TILE-4);
    ctx.fillStyle=PAL.fridgeL;ctx.fillRect(px+6,py+4,TILE-12,10);
    ctx.fillStyle="#889";     ctx.fillRect(px+6,py+16,TILE-12,TILE-20);
    ctx.fillStyle="#667";     ctx.fillRect(px+TILE-10,py+6,2,6);
    ctx.fillStyle="#667";     ctx.fillRect(px+TILE-10,py+18,2,8);
  } else if (t === 7) {
    ctx.fillStyle="#1a1a1a"; ctx.fillRect(px+2,py+4,TILE-4,TILE-10);
    ctx.fillStyle=PAL.tvS;   ctx.fillRect(px+4,py+6,TILE-8,TILE-16);
    ctx.fillStyle="#111";    ctx.fillRect(px+TILE/2-2,py+TILE-8,4,6);
    ctx.fillStyle="#333";    ctx.fillRect(px+4,py+TILE-5,TILE-8,3);
  } else if (t === 8) {
    ctx.fillStyle=PAL.shelfD; ctx.fillRect(px+4,py+2,TILE-8,TILE-4);
    ctx.fillStyle=PAL.shelf;  ctx.fillRect(px+5,py+3,TILE-10,4);
    ctx.fillStyle=PAL.shelf;  ctx.fillRect(px+5,py+13,TILE-10,4);
    ctx.fillStyle=PAL.shelf;  ctx.fillRect(px+5,py+23,TILE-10,4);
    [PAL.book1,PAL.book2,PAL.book3,PAL.book1].forEach((c,i)=>{ ctx.fillStyle=c; ctx.fillRect(px+6+i*6,py+7,4,6); });
    [PAL.book2,PAL.book3,PAL.book1].forEach((c,i)=>{ ctx.fillStyle=c; ctx.fillRect(px+6+i*7,py+17,5,6); });
  }
}

/**
 * 機能：プレイヤーキャラクターを現在座標に Canvas 描画する。移動中はボブアニメーションを適用する。
 * 入力：tick（アニメーションフレームカウンター）
 * 出力：なし
 */
function drawPlayer(tick) {
  const px = player.x*TILE+TILE/2, py = player.y*TILE+TILE/2;
  const moving = Object.values(keys).some(Boolean);
  const bob = moving && Math.floor(tick/8)%2===0 ? -1 : 0;

  ctx.fillStyle=PAL.shadow; ctx.beginPath(); ctx.ellipse(px,py+14,9,3,0,0,Math.PI*2); ctx.fill();
  ctx.fillStyle="#27ae60"; ctx.fillRect(px-7,py-6+bob,14,16);
  ctx.fillStyle="#c8a96e"; ctx.fillRect(px-6,py-17+bob,12,13);
  ctx.fillStyle="#5d3a1a"; ctx.fillRect(px-6,py-17+bob,12,4); ctx.fillRect(px-8,py-14+bob,3,6);
  ctx.fillStyle="#1a1a2e"; ctx.fillRect(px-3,py-12+bob,2,2); ctx.fillRect(px+1,py-12+bob,2,2);
  ctx.fillStyle="#2ecc71"; ctx.font="8px monospace"; ctx.textAlign="center";
  ctx.fillText("YOU",px,py-22+bob);
}

/**
 * 機能：指定マス目が移動不可（壁・家具・NPC 占有・境界外）かどうかを判定する。
 * 入力：col（列インデックス）、row（行インデックス）
 * 出力：bool（true なら移動不可）
 */
function isBlocked(col, row) {
  if (col<0||col>=COLS||row<0||row>=ROWS) return true;
  if ([1,3,4,5,6,7,8].includes(MAP[row]?.[col])) return true;
  for (const [nc,nr] of Object.values(NPC_POS[currentDay]??{}))
    if (Math.abs(nc-col)<1 && Math.abs(nr-row)<1) return true;
  return false;
}
