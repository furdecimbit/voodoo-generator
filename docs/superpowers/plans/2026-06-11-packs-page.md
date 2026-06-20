# Packs Page Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `packs.html` — a 3-column page where users view their pack inventory, open packs via an in-page card-flip reveal overlay, and find links to buy more packs.

**Architecture:** Single self-contained HTML file following forge.html patterns exactly (inline CSS + JS, no framework). Reuses all pack logic constants/functions copy-pasted from forge.html. Site header injected via `site-header.js`. Card-flip overlay replaces the pack-room.html redirect.

**Tech Stack:** Vanilla JS, CSS3 (3D transforms for card flip), HTML5. Flask dev server at `http://localhost:5050`. Assets via CDN `https://cdn.jsdelivr.net/gh/furdecimbit/voodoo-generator@main/`.

**Spec:** `docs/superpowers/specs/2026-06-11-packs-page-design.md`

---

## Chunk 1: Page Shell + 3-Column Layout

### Task 1: Create packs.html with base structure and CSS grid

**Files:**
- Create: `packs.html`

- [ ] Create `packs.html` with doctype, head (fonts, viewport), and body shell:

```html
<!DOCTYPE html>
<html lang="en" data-page="packs">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Packs — Hex & Stitch</title>
<link rel="icon" type="image/png" href="https://cdn.jsdelivr.net/gh/furdecimbit/voodoo-generator@main/icon.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Crimson+Text:ital,wght@0,400;0,600;1,400&display=swap" rel="stylesheet">
<style>
  @font-face { font-family:'Blackburn'; src:url('https://cdn.jsdelivr.net/gh/furdecimbit/voodoo-generator@main/Blackburn.ttf'); }
  @font-face { font-family:'Bloodcrow'; src:url('https://cdn.jsdelivr.net/gh/furdecimbit/voodoo-generator@main/bloodcrowc.ttf'); }
</style>
<style>
/* ── RESET ── */
*{box-sizing:border-box;margin:0;padding:0}
html,body{margin:0;padding:0;background:#080608;}
body{
  background:#080608;color:#d0c8b8;
  font-family:'Crimson Text',Georgia,serif;font-size:15px;
  display:flex;flex-direction:column;height:100vh;overflow:hidden;
}

/* ── 3-COLUMN GRID ── */
#packs-body{
  display:grid;
  grid-template-columns:460px 1fr 460px;
  grid-template-rows:1fr;
  grid-template-areas:"left center right";
  flex:1;overflow:hidden;
}
</style>
</head>
<body>
<div id="site-header-mount"></div>
<script src="site-header.js"></script>
<div id="packs-body">
  <div id="left-panel"><!-- Task 2 --></div>
  <div id="center-panel"><!-- Task 3 --></div>
  <div id="right-panel"><!-- Task 4 --></div>
</div>
<!-- overlays: Task 5 + Task 6 -->
<script>
const CDN = 'https://cdn.jsdelivr.net/gh/furdecimbit/voodoo-generator@main';
// WIX_API defined in site-header.js
</script>
</body>
</html>
```

- [ ] Open `http://localhost:5050/packs.html` — verify site header renders, 3 columns visible (empty), no console errors.

- [ ] Commit:
```bash
git add packs.html
git commit -m "feat: add packs.html shell with 3-column grid"
```

---

## Chunk 2: Left Panel — Wallet + Pack Summary + Filter

### Task 2: Left panel HTML + CSS

**Files:**
- Modify: `packs.html` — `#left-panel`

- [ ] Replace `#left-panel` with:

```html
<div id="left-panel">
  <div id="lp-header">
    <img src="panelback.png" alt="">
    <img id="lp-logo" src="logo2.png" alt="">
    <span id="lp-title">Pack<br>Vault</span>
  </div>

  <!-- Wallet section -->
  <div class="sidebar-section-label" id="wallet-section-label">
    <span class="ssl-icon">
      <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 7V4a1 1 0 0 0-1-1H5a2 2 0 0 0 0 4h15a1 1 0 0 1 1 1v4h-3a2 2 0 0 0 0 4h3a1 1 0 0 0 1-1v-2a1 1 0 0 0-1-1"/><path d="M3 5v14a2 2 0 0 0 2 2h15a1 1 0 0 0 1-1v-4"/></svg>
    </span>
    <span>Wallet</span>
  </div>

  <!-- Pack summary -->
  <div id="pack-summary">
    <div class="summary-label">Your Packs</div>
    <div id="summary-counts">
      <div class="summary-row common"><span class="sr-rarity">Common</span><span class="sr-count" id="sc-common">0</span></div>
      <div class="summary-row rare"><span class="sr-rarity">Rare</span><span class="sr-count" id="sc-rare">0</span></div>
      <div class="summary-row legendary"><span class="sr-rarity">Legendary</span><span class="sr-count" id="sc-legendary">0</span></div>
      <div class="summary-row ultimate"><span class="sr-rarity">Ultimate</span><span class="sr-count" id="sc-ultimate">0</span></div>
    </div>
  </div>

  <!-- Rarity filter -->
  <div id="rarity-filter-bar">
    <div class="rf-label">Filter</div>
    <div id="rf-btns">
      <button class="rf-btn active" data-rarity="all" onclick="setFilter('all',this)">All</button>
      <button class="rf-btn rf-common" data-rarity="common" onclick="setFilter('common',this)">Common</button>
      <button class="rf-btn rf-rare" data-rarity="rare" onclick="setFilter('rare',this)">Rare</button>
      <button class="rf-btn rf-legendary" data-rarity="legendary" onclick="setFilter('legendary',this)">Legendary</button>
      <button class="rf-btn rf-ultimate" data-rarity="ultimate" onclick="setFilter('ultimate',this)">Ultimate</button>
    </div>
  </div>
</div>
```

- [ ] Add CSS for left panel (inside existing `<style>`):

```css
/* ── LEFT PANEL ── */
#left-panel{
  grid-area:left;
  background:linear-gradient(180deg,#3d2b0fcc 0%,#2c1e0acc 40%,#1e1508cc 100%),url('verticalback.png');
  background-size:cover;background-position:center;
  border-right:3px solid #7a5520;
  box-shadow:inset -6px 0 24px #00000099;
  display:flex;flex-direction:column;
  height:100%;overflow-y:auto;
}
#left-panel::-webkit-scrollbar{width:6px}
#left-panel::-webkit-scrollbar-track{background:#140e04}
#left-panel::-webkit-scrollbar-thumb{background:#7a5520;border-radius:3px}

#lp-header{
  width:100%;border-bottom:2px solid #7a5520;
  flex-shrink:0;overflow:hidden;position:relative;
  display:flex;align-items:center;height:103px;
}
#lp-header>img:first-child{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;}
#lp-logo{position:relative;z-index:2;width:56px;height:56px;object-fit:contain;margin-left:14px;flex-shrink:0;}
#lp-title{
  position:relative;z-index:2;margin-left:auto;margin-right:14px;
  font-family:'Bloodcrow',serif;font-size:18px;line-height:1.15;
  letter-spacing:.1em;text-transform:uppercase;color:#c8a050;text-align:right;
  text-shadow:0 0 14px #c8a05077,0 1px 5px #000;
}

.sidebar-section-label{
  padding:12px 16px;display:flex;align-items:center;gap:10px;
  font-family:'Bloodcrow',serif;font-size:20px;letter-spacing:.12em;text-transform:uppercase;
  color:#e8d09a;background:linear-gradient(90deg,#2a1e0a,#1a1206);
  border-top:1px solid #4a3010;border-bottom:2px solid #4a3010;
}
.ssl-icon{
  display:flex;align-items:center;justify-content:center;
  width:34px;height:34px;border-radius:6px;flex-shrink:0;
  background:#1a1006;border:1px solid #6a4a18;color:#c8a050;
}

/* Pack summary */
#pack-summary{padding:16px 16px 8px;}
.summary-label{
  font-family:'Bloodcrow',serif;font-size:13px;letter-spacing:.1em;text-transform:uppercase;
  color:#5a4020;margin-bottom:10px;
}
.summary-row{
  display:flex;justify-content:space-between;align-items:center;
  padding:6px 10px;border-radius:6px;margin-bottom:4px;
  background:rgba(0,0,0,0.2);border:1px solid #2a1a08;
}
.sr-rarity{font-family:'Bloodcrow',serif;font-size:15px;letter-spacing:.06em;}
.sr-count{font-family:'Bloodcrow',serif;font-size:22px;font-weight:bold;}
.summary-row.common  .sr-rarity{color:#a0a080} .summary-row.common  .sr-count{color:#c8c8a8}
.summary-row.rare    .sr-rarity{color:#c8a010} .summary-row.rare    .sr-count{color:#f0d020}
.summary-row.legendary .sr-rarity{color:#40c0e0} .summary-row.legendary .sr-count{color:#60e0ff}
.summary-row.ultimate  .sr-rarity{color:#e050b0} .summary-row.ultimate  .sr-count{color:#ff80d8}

/* Rarity filter */
#rarity-filter-bar{padding:12px 16px;border-top:1px solid #2a1a08;}
.rf-label{font-family:'Bloodcrow',serif;font-size:13px;letter-spacing:.1em;text-transform:uppercase;color:#5a4020;margin-bottom:8px;}
#rf-btns{display:flex;flex-wrap:wrap;gap:6px;}
.rf-btn{
  padding:5px 14px;border:1px solid #3a2c12;border-radius:4px;
  background:linear-gradient(180deg,#221808,#1a1205);
  font-family:'Bloodcrow',serif;font-size:13px;letter-spacing:.05em;
  color:#7a6040;cursor:pointer;text-transform:uppercase;
  transition:background .15s,color .15s,border-color .15s;
}
.rf-btn:hover{color:#e8c060;border-color:#7a5820;}
.rf-btn.active{background:linear-gradient(180deg,#5a3c10,#3a2808);color:#f0d060;border-color:#c0900a;box-shadow:0 0 8px #c0900a44;}
.rf-btn.rf-common.active{color:#c8c8a8;border-color:#a0a080;background:linear-gradient(180deg,#2a2a20,#1e1e18);}
.rf-btn.rf-rare.active{color:#f0d020;border-color:#c09008;background:linear-gradient(180deg,#2e2400,#221a00);}
.rf-btn.rf-legendary.active{color:#60e0ff;border-color:#30b0d8;background:linear-gradient(180deg,#001e2e,#001422);}
.rf-btn.rf-ultimate.active{color:#ff80d8;border-color:#c040a0;background:linear-gradient(180deg,#280018,#1a0010);}
```

- [ ] Verify in browser: left panel renders with header, wallet label, summary rows, filter buttons.

- [ ] Commit:
```bash
git add packs.html
git commit -m "feat: packs page left panel — wallet section, pack summary, rarity filter"
```

---

## Chunk 3: Center Panel — Pack Grid

### Task 3: Center panel HTML + CSS + pack grid render

**Files:**
- Modify: `packs.html` — `#center-panel`

- [ ] Replace `#center-panel` with:

```html
<div id="center-panel">
  <div id="cp-header">
    <span id="cp-title">Pack Inventory</span>
    <span id="cp-total-badge"></span>
  </div>
  <div id="pack-grid-wrap">
    <div id="pack-grid"></div>
    <div id="pack-empty-state">
      <div id="pes-icon">⛧</div>
      <div id="pes-text">No packs in your collection.</div>
      <div id="pes-sub">Get one from the Drip or Objkt marketplace →</div>
    </div>
    <div id="no-wallet-overlay">
      <div id="nwo-inner">
        <div id="nwo-icon">🔒</div>
        <div id="nwo-text">Connect your wallet<br>to view your packs</div>
      </div>
    </div>
  </div>
</div>
```

- [ ] Add CSS for center panel:

```css
/* ── CENTER PANEL ── */
#center-panel{
  grid-area:center;
  display:flex;flex-direction:column;
  background:#080608;position:relative;overflow:hidden;
}
#center-panel::before{
  content:'';position:absolute;inset:0;
  background:url('verticalback.png') center/cover no-repeat;
  opacity:.12;pointer-events:none;z-index:0;
}
#cp-header{
  position:relative;z-index:1;flex-shrink:0;
  display:flex;align-items:center;gap:14px;
  padding:20px 28px 16px;
  border-bottom:1px solid #2a1a08;
  background:linear-gradient(180deg,#12100800,transparent);
}
#cp-title{
  font-family:'Bloodcrow',serif;font-size:26px;letter-spacing:.14em;
  text-transform:uppercase;color:#e8d09a;
  text-shadow:0 0 20px #c8a05044;
}
#cp-total-badge{
  font-family:'Bloodcrow',serif;font-size:14px;letter-spacing:.08em;
  color:#7a6040;padding:3px 12px;border:1px solid #3a2808;
  border-radius:20px;background:#0e0a04;
}

#pack-grid-wrap{
  position:relative;z-index:1;flex:1;overflow-y:auto;padding:24px 28px;
}
#pack-grid-wrap::-webkit-scrollbar{width:4px}
#pack-grid-wrap::-webkit-scrollbar-thumb{background:#4a3010;border-radius:2px}

#pack-grid{
  display:grid;
  grid-template-columns:repeat(auto-fill,minmax(160px,1fr));
  gap:20px;
}

/* Pack card */
.pack-card{
  display:flex;flex-direction:column;align-items:center;gap:10px;
  padding:16px 10px 14px;border-radius:12px;cursor:pointer;
  border:1px solid #3a2808;
  background:linear-gradient(160deg,#1a1208,#0e0a06);
  position:relative;transition:transform .15s,box-shadow .2s,border-color .2s;
}
.pack-card:hover{transform:translateY(-4px);}
.pack-card.rarity-common{border-color:#4a4a3a;}
.pack-card.rarity-rare{border-color:#7a5808;box-shadow:0 0 14px #c8a01022;}
.pack-card.rarity-legendary{border-color:#2a6a8a;box-shadow:0 0 14px #40c0e022;}
.pack-card.rarity-ultimate{border-color:#7a2060;box-shadow:0 0 14px #e050b022;}
.pack-card:hover.rarity-common{border-color:#8a8a6a;box-shadow:0 0 18px #c8c8a822;}
.pack-card:hover.rarity-rare{border-color:#e8b020;box-shadow:0 0 20px #f0c04055;}
.pack-card:hover.rarity-legendary{border-color:#50d0f0;box-shadow:0 0 20px #50d0f055;}
.pack-card:hover.rarity-ultimate{border-color:#f060b8;box-shadow:0 0 20px #f060b855;}

.pc-img-wrap{position:relative;width:120px;height:120px;}
.pc-img{width:100%;height:100%;object-fit:contain;display:block;border-radius:8px;}
.pc-count{
  position:absolute;top:-6px;right:-6px;
  background:#cc2222;color:#fff;
  font-family:'Bloodcrow',serif;font-size:14px;font-weight:bold;
  width:26px;height:26px;border-radius:50%;
  display:flex;align-items:center;justify-content:center;
  box-shadow:0 0 8px #cc222299;
}
.pc-label{
  font-family:'Bloodcrow',serif;font-size:17px;letter-spacing:.08em;
  text-transform:uppercase;
}
.pack-card.rarity-common .pc-label{color:#c8c8a8}
.pack-card.rarity-rare .pc-label{color:#f0d020}
.pack-card.rarity-legendary .pc-label{color:#60e0ff}
.pack-card.rarity-ultimate .pc-label{color:#ff80d8}

.pc-open-btn{
  font-family:'Bloodcrow',serif;font-size:14px;letter-spacing:.08em;text-transform:uppercase;
  padding:7px 20px;border-radius:20px;cursor:pointer;
  border:1px solid #4a3010;background:#0e0a04;color:#c8a050;
  transition:border-color .2s,color .2s,box-shadow .2s;
}
.pc-open-btn:hover{border-color:#e8c060;color:#e8c060;box-shadow:0 0 12px #e8c06033;}

/* Empty state */
#pack-empty-state{
  display:none;flex-direction:column;align-items:center;justify-content:center;
  gap:12px;padding:60px 20px;text-align:center;
}
#pack-empty-state.visible{display:flex;}
#pes-icon{font-size:48px;opacity:.3;}
#pes-text{font-family:'Bloodcrow',serif;font-size:20px;letter-spacing:.08em;color:#5a4020;}
#pes-sub{font-family:'Bloodcrow',serif;font-size:14px;color:#3a2810;}

/* No wallet overlay */
#no-wallet-overlay{
  display:none;position:absolute;inset:0;z-index:10;
  background:rgba(8,6,8,.75);backdrop-filter:blur(4px);
  align-items:center;justify-content:center;
}
#no-wallet-overlay.visible{display:flex;}
#nwo-inner{text-align:center;}
#nwo-icon{font-size:40px;margin-bottom:12px;}
#nwo-text{font-family:'Bloodcrow',serif;font-size:20px;letter-spacing:.08em;color:#c8a050;line-height:1.5;}
```

- [ ] Add pack grid JS (in `<script>` block):

```js
const PACK_IMGS = {
  common:'common_pack.png', rare:'rare_pack.png',
  legendary:'legendary_pack.png', ultimate:'ultimate_pack.png'
};
const RARITIES = ['common','rare','legendary','ultimate'];

let walletConnected = false;
let currentWalletKey = null;
let packInventory = {common:0,rare:0,legendary:0,ultimate:0};
let activeFilter = 'all';

function walletKey(k){ return currentWalletKey ? `wallet_${currentWalletKey}_${k}` : k; }

function loadPackInventory(){
  const saved = JSON.parse(localStorage.getItem(walletKey('packInventory'))||'null');
  if(saved) packInventory = saved;
}

function renderPackGrid(){
  const grid = document.getElementById('pack-grid');
  const empty = document.getElementById('pack-empty-state');
  grid.innerHTML = '';
  let any = false;
  let total = 0;
  RARITIES.forEach(r=>{
    const count = packInventory[r]||0;
    if(count<=0) return;
    if(activeFilter !== 'all' && activeFilter !== r) return;
    any = true; total += count;
    const card = document.createElement('div');
    card.className = `pack-card rarity-${r}`;
    card.dataset.rarity = r;
    card.innerHTML = `
      <div class="pc-img-wrap">
        <img class="pc-img" src="${PACK_IMGS[r]}" alt="${r}">
        <div class="pc-count">${count}</div>
      </div>
      <div class="pc-label">${r}</div>
      <button class="pc-open-btn" onclick="event.stopPropagation();openPackPreview('${r}')">Open</button>`;
    grid.appendChild(card);
  });
  empty.classList.toggle('visible', !any);
  // update summary counts
  RARITIES.forEach(r=>{
    const el = document.getElementById('sc-'+r);
    if(el) el.textContent = packInventory[r]||0;
  });
  // total badge
  const badge = document.getElementById('cp-total-badge');
  if(badge) badge.textContent = total > 0 ? total + ' packs' : '';
}

function setFilter(rarity, btn){
  activeFilter = rarity;
  document.querySelectorAll('.rf-btn').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');
  renderPackGrid();
}

function updateWalletOverlay(){
  const ov = document.getElementById('no-wallet-overlay');
  if(ov) ov.classList.toggle('visible', !walletConnected);
}

// Called by site-header.js after wallet state changes
window.connectWallet    = function(){};
window.connectTezos     = function(){};
window.disconnectWallet = function(){ walletConnected=false; currentWalletKey=null; packInventory={common:0,rare:0,legendary:0,ultimate:0}; renderPackGrid(); updateWalletOverlay(); if(typeof window.setHeaderWallet==='function') window.setHeaderWallet(null,null); };
window.disconnectTezos  = window.disconnectWallet;

document.addEventListener('DOMContentLoaded', ()=>{
  loadPackInventory();
  renderPackGrid();
  updateWalletOverlay();
});
```

- [ ] Verify in browser: pack grid renders (empty state visible since no wallet). Filter buttons work (click Rare → only rare cards show).

- [ ] Commit:
```bash
git add packs.html
git commit -m "feat: packs page center panel — pack grid, filter, empty state, no-wallet overlay"
```

---

## Chunk 4: Right Panel — Buy Packs + Drop Table

### Task 4: Right panel HTML + CSS

**Files:**
- Modify: `packs.html` — `#right-panel`

- [ ] Replace `#right-panel` with:

```html
<div id="right-panel">
  <div id="rp-header-img"><img src="equipback.png" alt=""></div>
  <div id="rp-scroll">
    <div class="rp-section-title">Get Packs</div>
    <div id="buy-links">
      <a href="#" target="_blank" class="buy-link-btn" id="buy-drip-btn">
        <img src="drip.jpeg" class="buy-link-icon" alt="Drip">
        <span>Buy on Drip</span>
      </a>
      <a href="#" target="_blank" class="buy-link-btn" id="buy-objkt-btn">
        <img src="objkt.jpeg" class="buy-link-icon" alt="Objkt">
        <span>Buy on Objkt</span>
      </a>
    </div>

    <div class="rp-section-title" style="margin-top:16px;">Pack Contents</div>
    <div id="drop-table">
      <div class="dt-row rarity-common">
        <div class="dt-rarity">Common</div>
        <div class="dt-contents">5 items · 5× Common<br><span class="dt-bonus">10% chance: 1 → Rare</span></div>
      </div>
      <div class="dt-row rarity-rare">
        <div class="dt-rarity">Rare</div>
        <div class="dt-contents">3 items · 2× Rare + 1× Common<br><span class="dt-bonus">10% chance: 1 Rare → Legendary</span></div>
      </div>
      <div class="dt-row rarity-legendary">
        <div class="dt-rarity">Legendary</div>
        <div class="dt-contents">4 items · 2× Legendary + 1× Rare + 1× Common<br><span class="dt-bonus">10% chance: 1 Legendary → Ultimate</span></div>
      </div>
      <div class="dt-row rarity-ultimate">
        <div class="dt-rarity">Ultimate</div>
        <div class="dt-contents">5 items · 2× Ultimate + 1× Legendary + 1× Rare + 1× Common<br><span class="dt-bonus">No upgrade — already the peak</span></div>
      </div>
    </div>
  </div>
  <div id="rp-footer">Hex &amp; Stitch &nbsp;·&nbsp; <a href="https://alperozdil.com" target="_blank">alperozdil.com</a></div>
</div>
```

- [ ] Add CSS for right panel:

```css
/* ── RIGHT PANEL ── */
#right-panel{
  grid-area:right;
  background:linear-gradient(180deg,#1a1208cc,#141008cc),url('verticalback.png');
  background-size:cover;background-position:center;
  border-left:3px solid #7a5520;
  box-shadow:inset 6px 0 24px #00000099;
  display:flex;flex-direction:column;overflow:hidden;
}
#rp-header-img{flex-shrink:0;height:103px;border-bottom:2px solid #7a5520;overflow:hidden;}
#rp-header-img img{width:100%;height:100%;object-fit:cover;object-position:center 50%;display:block;}
#rp-scroll{flex:1;overflow-y:auto;padding:0;}
#rp-scroll::-webkit-scrollbar{width:4px}
#rp-scroll::-webkit-scrollbar-thumb{background:#4a3010;border-radius:2px}

.rp-section-title{
  font-family:'Bloodcrow',serif;font-size:14px;letter-spacing:.12em;text-transform:uppercase;
  color:#5a4020;padding:14px 16px 6px;border-bottom:1px solid #2a1a08;
}

/* Buy links */
#buy-links{display:flex;flex-direction:column;gap:8px;padding:12px 14px;}
.buy-link-btn{
  display:flex;align-items:center;gap:12px;padding:12px 16px;
  background:linear-gradient(135deg,#1a1008,#120c04);
  border:1px solid #3a2808;border-radius:10px;text-decoration:none;
  font-family:'Bloodcrow',serif;font-size:16px;letter-spacing:.06em;color:#c8a050;
  transition:border-color .2s,box-shadow .2s;
}
.buy-link-btn:hover{border-color:#7a5520;box-shadow:0 0 14px #c8a05022;}
.buy-link-icon{width:32px;height:32px;border-radius:50%;object-fit:cover;border:1px solid #4a3010;flex-shrink:0;}

/* Drop table */
#drop-table{padding:10px 14px;display:flex;flex-direction:column;gap:8px;}
.dt-row{
  padding:10px 12px;border-radius:8px;border:1px solid;
  background:rgba(0,0,0,.25);
}
.dt-row.rarity-common{border-color:#4a4a3a;}
.dt-row.rarity-rare{border-color:#7a5808;}
.dt-row.rarity-legendary{border-color:#2a6a8a;}
.dt-row.rarity-ultimate{border-color:#7a2060;}
.dt-rarity{
  font-family:'Bloodcrow',serif;font-size:14px;letter-spacing:.08em;text-transform:uppercase;
  margin-bottom:4px;
}
.dt-row.rarity-common .dt-rarity{color:#c8c8a8}
.dt-row.rarity-rare .dt-rarity{color:#f0d020}
.dt-row.rarity-legendary .dt-rarity{color:#60e0ff}
.dt-row.rarity-ultimate .dt-rarity{color:#ff80d8}
.dt-contents{font-family:'Crimson Text',serif;font-size:13px;color:#7a6040;line-height:1.5;}
.dt-bonus{color:#5a4030;font-style:italic;}

#rp-footer{
  flex-shrink:0;padding:8px 14px;border-top:1px solid #2a1808;
  font-family:'Bloodcrow',serif;font-size:11px;color:#3a2810;text-align:center;
}
#rp-footer a{color:#5a4020;text-decoration:none;}
```

- [ ] Verify in browser: right panel shows "Get Packs" buy buttons and drop table with rarity-colored rows.

- [ ] Commit:
```bash
git add packs.html
git commit -m "feat: packs page right panel — buy links and drop table"
```

---

## Chunk 5: Pack Preview Popup

### Task 5: Preview modal HTML + CSS + JS

**Files:**
- Modify: `packs.html` — add overlay HTML before `</body>`

- [ ] Add preview popup HTML before closing `</body>`:

```html
<!-- PACK PREVIEW POPUP -->
<div id="pack-preview-popup">
  <div id="ppp-box">
    <img id="ppp-img" src="" alt="">
    <div id="ppp-rarity"></div>
    <div id="ppp-count"></div>
    <button id="ppp-open-btn" onclick="startPackOpen()">⛧ Open Pack</button>
    <button id="ppp-cancel-btn" onclick="closePackPreview()">Cancel</button>
  </div>
</div>
```

- [ ] Add CSS:

```css
/* ── PACK PREVIEW POPUP ── */
#pack-preview-popup{
  display:none;position:fixed;inset:0;z-index:3000;
  background:rgba(0,0,0,.8);backdrop-filter:blur(6px);
  align-items:center;justify-content:center;
}
#pack-preview-popup.active{display:flex;}
#ppp-box{
  display:flex;flex-direction:column;align-items:center;gap:14px;
  background:linear-gradient(160deg,#1a1208,#0e0a06);
  border:1px solid #4a3010;border-radius:16px;
  padding:32px 40px;
  box-shadow:0 8px 48px #000000cc;
  animation:pppIn .25s ease;
}
@keyframes pppIn{from{opacity:0;transform:scale(.92)}to{opacity:1;transform:none}}
#ppp-img{width:200px;height:200px;object-fit:contain;border-radius:12px;}
#ppp-rarity{
  font-family:'Bloodcrow',serif;font-size:22px;letter-spacing:.12em;text-transform:uppercase;color:#e8d09a;
}
#ppp-count{font-family:'Bloodcrow',serif;font-size:14px;letter-spacing:.06em;color:#5a4020;}
#ppp-open-btn{
  font-family:'Bloodcrow',serif;font-size:20px;letter-spacing:.1em;
  padding:12px 40px;border-radius:8px;cursor:pointer;
  background:linear-gradient(135deg,#3a0a5a,#6a1aaa);color:#e8c0ff;
  border:2px solid #aa44ee;box-shadow:0 0 18px #aa44ee44;
  transition:box-shadow .2s;
}
#ppp-open-btn:hover{box-shadow:0 0 32px #cc66ffaa;}
#ppp-cancel-btn{
  font-family:'Bloodcrow',serif;font-size:14px;color:#4a3820;
  background:none;border:none;cursor:pointer;
}
#ppp-cancel-btn:hover{color:#c8a050;}
```

- [ ] Add JS for preview popup:

```js
let _previewRarity = null;

function openPackPreview(rarity){
  if(!packInventory[rarity]||packInventory[rarity]<=0) return;
  _previewRarity = rarity;
  const popup = document.getElementById('pack-preview-popup');
  document.getElementById('ppp-img').src = PACK_IMGS[rarity];
  document.getElementById('ppp-rarity').textContent = rarity + ' Pack';
  document.getElementById('ppp-count').textContent = packInventory[rarity] + ' remaining';
  popup.classList.add('active');
}
function closePackPreview(){
  document.getElementById('pack-preview-popup').classList.remove('active');
  _previewRarity = null;
}
```

- [ ] Verify in browser: add `packInventory = {common:2}` temporarily in console → pack card appears → click Open button → preview popup shows with image, count, buttons. Cancel closes it.

- [ ] Remove temporary console test. Commit:
```bash
git add packs.html
git commit -m "feat: packs page pack preview popup"
```

---

## Chunk 6: Card Flip Reveal Overlay

### Task 6: Full-screen card flip overlay HTML + CSS + JS

**Files:**
- Modify: `packs.html` — add overlay HTML + full card flip logic

- [ ] Add card flip overlay HTML before closing `</body>`:

```html
<!-- CARD FLIP REVEAL OVERLAY -->
<div id="card-reveal-overlay">
  <div id="cro-header">
    <span id="cro-rarity-label"></span>
  </div>
  <div id="cro-cards-row"></div>
  <button id="cro-claim-btn" onclick="claimAll()" style="display:none">✦ Claim All Items</button>
</div>
```

- [ ] Add CSS for card flip overlay:

```css
/* ── CARD FLIP OVERLAY ── */
#card-reveal-overlay{
  display:none;position:fixed;inset:0;z-index:4000;
  background:radial-gradient(ellipse at 50% 40%,#1a0a0a 0%,#030201 70%);
  flex-direction:column;align-items:center;justify-content:center;gap:32px;
  padding:24px;
}
#card-reveal-overlay.active{display:flex;}

#cro-header{text-align:center;}
#cro-rarity-label{
  font-family:'Bloodcrow',serif;font-size:28px;letter-spacing:.16em;text-transform:uppercase;
  color:#e8d09a;text-shadow:0 0 30px #c8a05066;
}

#cro-cards-row{
  display:flex;gap:16px;flex-wrap:wrap;justify-content:center;
  max-width:900px;
}

/* Flip card base */
.flip-card{
  width:140px;height:200px;perspective:800px;cursor:pointer;flex-shrink:0;
}
.flip-card-inner{
  width:100%;height:100%;position:relative;
  transform-style:preserve-3d;
  transition:transform .55s cubic-bezier(.4,0,.2,1);
}
.flip-card.flipped .flip-card-inner{ transform:rotateY(180deg); }

.flip-card-back,.flip-card-front{
  position:absolute;inset:0;backface-visibility:hidden;border-radius:12px;overflow:hidden;
  border:2px solid #3a2808;
}
.flip-card-back{
  background:linear-gradient(135deg,#1a1208,#0e0a06);
  display:flex;align-items:center;justify-content:center;
  font-size:48px;color:#3a2808;
}
.flip-card-front{
  transform:rotateY(180deg);
  background:linear-gradient(160deg,#1e1408,#120e06);
  display:flex;flex-direction:column;align-items:center;gap:6px;padding:10px 8px 12px;
}
.fc-img{width:100px;height:100px;object-fit:contain;border-radius:8px;flex-shrink:0;}
.fc-name{
  font-family:'Bloodcrow',serif;font-size:11px;letter-spacing:.05em;text-transform:uppercase;
  color:#e8d09a;text-align:center;line-height:1.3;
  overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;
}
.fc-cat{font-family:'Bloodcrow',serif;font-size:10px;color:#5a4020;letter-spacing:.04em;text-transform:uppercase;}
.fc-stats{display:flex;gap:4px;margin-top:2px;}
.fc-stat{
  font-family:'Bloodcrow',serif;font-size:11px;font-weight:bold;padding:2px 5px;
  border-radius:3px;background:rgba(0,0,0,.4);border:1px solid rgba(255,255,255,.1);
}
.fc-stat.curse{color:#ff6040}.fc-stat.doom{color:#a0b8ff}.fc-stat.hex{color:#dd88ff}

/* Rarity borders on front */
.flip-card.rarity-common  .flip-card-front{border-color:#6a6a5a;}
.flip-card.rarity-rare    .flip-card-front{border-color:#c8a010;box-shadow:0 0 10px #c8a01044;}
.flip-card.rarity-legendary .flip-card-front{border-color:#40c0e0;box-shadow:0 0 12px #40c0e044;}
.flip-card.rarity-ultimate  .flip-card-front{border-color:#e050b0;box-shadow:0 0 14px #e050b055;}

/* Claim button */
#cro-claim-btn{
  font-family:'Bloodcrow',serif;font-size:22px;letter-spacing:.1em;text-transform:uppercase;
  padding:14px 48px;border-radius:8px;cursor:pointer;
  background:linear-gradient(135deg,#1a3020,#0e1e14);
  color:#70cc70;border:1px solid #308030;
  box-shadow:0 2px 18px #70cc7022;
  transition:box-shadow .2s,transform .1s;
  animation:claimIn .35s ease;
}
@keyframes claimIn{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:none}}
#cro-claim-btn:hover{box-shadow:0 2px 30px #70cc7055;transform:translateY(-2px);}
```

- [ ] Add full pack opening + card flip JS. Paste PACK_ITEMS constant from forge.html and add:

```js
// ── Copy PACK_ITEMS from forge.html here (full constant) ──
// const PACK_ITEMS = { ... };  // paste verbatim

function rollOne(rarity, cat){
  const items = PACK_ITEMS[rarity]?.[cat];
  if(!items||!items.length) return null;
  return {path:items[Math.floor(Math.random()*items.length)],cat,rarity};
}

function rollPackItems(rarity){
  const cats=['body','knife','offhand','necklace','eyes'];
  let slots=[];
  if(rarity==='common'){
    slots=[{r:'common'},{r:'common'},{r:'common'},{r:'common'},{r:'common'}];
    if(Math.random()<.10) slots[Math.floor(Math.random()*5)].r='rare';
  } else if(rarity==='rare'){
    slots=[{r:'rare'},{r:'rare'},{r:'common'}];
    if(Math.random()<.10){const i=slots.findIndex(s=>s.r==='rare');slots[i].r='legendary';}
  } else if(rarity==='legendary'){
    slots=[{r:'legendary'},{r:'legendary'},{r:'rare'},{r:'common'}];
    if(Math.random()<.10){const i=slots.findIndex(s=>s.r==='legendary');slots[i].r='ultimate';}
  } else {
    slots=[{r:'ultimate'},{r:'ultimate'},{r:'legendary'},{r:'rare'},{r:'common'}];
  }
  const shuffled=[...cats].sort(()=>Math.random()-.5);
  return slots.map((slot,i)=>rollOne(slot.r,shuffled[i%shuffled.length])||rollOne('common',shuffled[i%shuffled.length])).filter(Boolean);
}

const STAT_SEEDS = {};
function itemStats(path){
  if(!STAT_SEEDS[path]){
    let h=0; for(const c of path){h=(h<<5)-h+c.charCodeAt(0)|0;}
    const r=path.includes('/rare/')?1:path.includes('/legendary/')?2:path.includes('/ultimate/')?3:0;
    const b=(r+1)*4;
    STAT_SEEDS[path]={curse:b+Math.abs(h)%5,doom:b+Math.abs(h>>3)%5,hex:b+Math.abs(h>>6)%5};
  }
  return STAT_SEEDS[path];
}

let _pendingItems = [];

async function startPackOpen(){
  if(!_previewRarity) return;
  closePackPreview();
  const rarity = _previewRarity;

  // Deduct pack
  packInventory[rarity] = Math.max(0,(packInventory[rarity]||1)-1);
  localStorage.setItem(walletKey('packInventory'), JSON.stringify(packInventory));
  renderPackGrid();

  // Roll items (try Wix, fall back locally)
  let items = [];
  try{
    const res = await fetch(`${WIX_API}/openPack`,{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({wallet:currentWalletKey,rarity,mintAddress:''})
    });
    const data = await res.json();
    if(data.items) items = data.items;
  }catch(e){ items = rollPackItems(rarity); }
  if(!items.length) items = rollPackItems(rarity);
  _pendingItems = items;

  // Save to collection
  saveToCollection(items);

  // Show overlay
  showCardReveal(rarity, items);
}

function saveToCollection(items){
  const saved = JSON.parse(localStorage.getItem(walletKey('collection'))||'[]');
  items.forEach(item=>{ if(!saved.find(s=>s.path===item.path)) saved.push(item); });
  localStorage.setItem(walletKey('collection'), JSON.stringify(saved));
}

function showCardReveal(rarity, items){
  const overlay = document.getElementById('card-reveal-overlay');
  document.getElementById('cro-rarity-label').textContent = rarity.toUpperCase() + ' PACK';
  document.getElementById('cro-claim-btn').style.display = 'none';
  const row = document.getElementById('cro-cards-row');
  row.innerHTML = '';

  items.forEach((item, i)=>{
    const name = item.path.split('/').pop().replace(/\.(png|PNG|jpg)$/i,'').replace(/_/g,' ');
    const stats = itemStats(item.path);
    const catLabel = (item.cat||'').split('_')[0];
    const imgSrc = CDN + '/' + item.path;

    const card = document.createElement('div');
    card.className = `flip-card rarity-${item.rarity}`;
    card.innerHTML = `
      <div class="flip-card-inner">
        <div class="flip-card-back">⛧</div>
        <div class="flip-card-front">
          <img class="fc-img" src="${imgSrc}" alt="${name}">
          <div class="fc-name">${name}</div>
          <div class="fc-cat">${catLabel}</div>
          <div class="fc-stats">
            <span class="fc-stat curse">${stats.curse}</span>
            <span class="fc-stat doom">${stats.doom}</span>
            <span class="fc-stat hex">${stats.hex}</span>
          </div>
        </div>
      </div>`;
    row.appendChild(card);

    // Staggered flip
    setTimeout(()=>{
      card.classList.add('flipped');
      if(i === items.length-1){
        setTimeout(()=>{
          document.getElementById('cro-claim-btn').style.display='';
        }, 600);
      }
    }, 600 + i * 350);
  });

  overlay.classList.add('active');
}

function claimAll(){
  document.getElementById('card-reveal-overlay').classList.remove('active');
  _pendingItems = [];
  _previewRarity = null;
}
```

- [ ] Paste the full `PACK_ITEMS` constant from `forge.html` lines 4924 into packs.html script (it's the large JSON object).

- [ ] Verify in browser (using console to set `packInventory = {common:1}; renderPackGrid()`): click Open on common pack → preview popup → Open Pack → overlay appears → cards flip one by one left-to-right → Claim All button appears → click closes overlay.

- [ ] Commit:
```bash
git add packs.html
git commit -m "feat: packs page card flip reveal overlay with staggered flip animation"
```

---

## Chunk 7: Wallet Integration + Polish

### Task 7: Wire up wallet connect/disconnect + mobile basics

**Files:**
- Modify: `packs.html` — wallet JS bridge + mobile CSS

- [ ] Add Beacon SDK script tag (same as forge.html) in `<head>`:
```html
<script src="https://unpkg.com/@airgap/beacon-dapp@4.8.1/dist/walletbeacon.dapp.min.js"></script>
```

- [ ] Copy `connectWallet`, `disconnectWallet`, `connectTezos`, `disconnectTezos` functions verbatim from forge.html. They call `setWalletStatus` and `loadCollection` internally — replace `loadCollection` calls with `loadPacksFromWallet`.

- [ ] Add `loadPacksFromWallet` function:
```js
async function loadPacksFromWallet(){
  if(typeof window.setHeaderSyncing === 'function') window.setHeaderSyncing(true);
  try{
    // Try Wix for pack counts
    const res = await fetch(`${WIX_API}/getPacks?wallet=${encodeURIComponent(currentWalletKey)}`);
    if(res.ok){
      const data = await res.json();
      if(data.packs) packInventory = data.packs;
    }
  }catch(e){
    // Fall back to localStorage
    loadPackInventory();
  }
  renderPackGrid();
  updateWalletOverlay();
  if(typeof window.setHeaderSyncing === 'function') window.setHeaderSyncing(false);
  if(typeof window.setHeaderWallet === 'function') window.setHeaderWallet(currentWalletKey, window.tezosAddress ? 'tez' : 'sol');
}
```

- [ ] Add basic mobile CSS (below existing styles):
```css
@media(max-width:900px){
  body{ overflow-y:auto; }
  #packs-body{
    display:flex;flex-direction:column;height:auto;
    grid-template-areas:none;grid-template-columns:none;
  }
  #left-panel,#right-panel{ width:100%;border-right:none;border-left:none;border-top:2px solid #3a2808; }
  #center-panel{ min-height:60vh; }
  #cro-cards-row{ gap:10px; }
  .flip-card{ width:120px;height:170px; }
  .fc-img{ width:80px;height:80px; }
}
```

- [ ] Verify in browser: resize to mobile — columns stack vertically. Wallet connect flow triggers syncing spinner on wallet icon.

- [ ] Final check: open `http://localhost:5050/packs.html` fresh — no console errors, header renders, 3 columns on desktop, filter works, demo overlay shows.

- [ ] Commit:
```bash
git add packs.html
git commit -m "feat: packs page wallet integration and mobile layout"
```
