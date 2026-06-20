# Packs Page Design — packs.html

## Overview

A dedicated packs page (`packs.html`) where users can view their pack inventory, open packs via a card-flip reveal overlay, and find links to purchase more packs. Uses the same visual language as `forge.html`.

---

## Layout — 3 Column (desktop), flex-column (mobile)

Mirrors forge.html's grid: `460px | 1fr | 460px`, `100vh`, `overflow:hidden`.  
Site header injected via `site-header.js` (sticky, `data-page="packs"`).

### Left Column — Inventory Panel

- Wallet section label (same pattern as forge sidebar)
- Pack summary row: count per rarity (Common / Rare / Legendary / Ultimate)
- Rarity filter bar: All / Common / Rare / Legendary / Ultimate — filters visible pack cards in center
- Background: `verticalback.png` + dark gradient overlay, `border-right: 3px solid #7a5520`

### Center Column — Pack Grid

- Grid of owned pack cards, one card type per rarity
- Each card: large pack image (`common_pack.png` etc.), rarity name, count badge (red circle top-right), platform badge (Drip/Objkt logo bottom-right)
- Rarity glow on hover (same `.pack-card` styles as forge)
- Click → Preview Popup
- Empty state: "No packs in your collection. Get one below →" with arrow pointing right
- Demo state (no wallet): cards blurred with "Connect wallet to view your packs" overlay

**Preview Popup** (modal, not full-screen):
- Pack image centered, count remaining, "Open Pack" button + "Cancel" link
- Same dark overlay background as forge's `#pack-preview`

### Right Column — Get Packs

- Header image (`equipback.png`) matching forge right panel
- "Get Packs" section title
- Drip buy button (drip.jpeg logo + label)
- Objkt buy button (objkt.jpeg logo + label)
- Pack tier table: each rarity row shows item count + contents summary + bonus chance
- Background: `verticalback.png` + gradient, `border-left: 3px solid #7a5520`

---

## Pack Opening Overlay (full-screen, z-index 2000)

Replaces pack-room.html redirect. Entirely in-page.

### Flow

1. User clicks "Open Pack" in preview popup
2. Preview popup closes
3. Full-screen dark overlay fades in
4. Pack image shown large, brief "burst" CSS animation (scale + fade out)
5. N face-down cards appear in a row (backed with dark card texture or gradient)
6. Cards flip left-to-right with 300ms stagger, CSS 3D `rotateY` flip
7. Each card front: item image, item name, category label, rarity color border, stat pips (Curse / Doom / Hex)
8. After last card flips: "Claim All" button fades in
9. Click "Claim All" → items saved to inventory (Wix API + localStorage), overlay closes, pack count decremented, pack grid re-renders

### Card Flip CSS

```
.reveal-card { transform-style: preserve-3d; transition: transform 0.55s cubic-bezier(.4,0,.2,1); }
.reveal-card.flipped { transform: rotateY(180deg); }
.reveal-card-front { backface-visibility: hidden; transform: rotateY(180deg); }
.reveal-card-back  { backface-visibility: hidden; }
```

### Item Count Per Pack

| Pack | Cards |
|------|-------|
| Common | 5 |
| Rare | 3 |
| Legendary | 4 |
| Ultimate | 5 |

---

## Data & State

Reuses all existing pack logic from `forge.html` verbatim:
- `PACK_ITEMS` — full item catalog
- `packInventory` — localStorage per wallet key
- `rollPackItems(rarity)` — local fallback roll
- `processDrop(rarity)` — Wix API call + local fallback
- `saveCollection(items)` — persists to Wix + localStorage
- `walletKey(k)` — namespaced localStorage key

`WIX_API` and `CDN` constants come from `site-header.js`.

---

## Mobile

Body becomes `flex-direction:column`. Same `display:contents` trick on left panel.  
Tab bar: Packs / Buy / Settings (simplified — no Ritual/Equipped tabs needed here).  
Card flip overlay: cards stack 2-per-row on small screens.

---

## Files

| File | Role |
|------|------|
| `packs.html` | New page — all HTML/CSS/JS inline |
| `site-header.js` | Injected header + wallet dropdown (unchanged) |
| `pack-room.html` | Kept but no longer linked from packs flow |

---

## Out of Scope

- Pack purchase flow (Drip/Objkt links only, no in-app buy)
- Trading or transferring packs
- Pack history / opened pack log
