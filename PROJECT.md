# Hex & Stitch — Project Doc

## Genel Yapı

Tek HTML dosyası: `pack_test.html`  
Vanilla JS + CSS, no framework. CDN üzerinden asset'ler.

Asset CDN: `https://cdn.jsdelivr.net/gh/furdecimbit/voodoo-generator@main/`  
Wix backend API: `WIX_API` değişkeni (HTTP functions)

---

## Mobil Mimari

### `display:contents` trick
`#sidebar` elementine `display:contents` uygulanıyor — böylece sidebar'ın child'ları body flex'inin direkt elemanı oluyor ve `order` ile konumlandırılabiliyor.

### Mobil Sıralama (order değerleri)
```
0 — #wallet-section-label (sticky, top:80px)
1 — #preview-area
2 — #mob-tab-bar (sticky, top:126px)
3 — #sidebar-content (ritual/packs içeriği)
4 — #right-panel (equipped)
5 — #mob-settings-panel (options)
```

### Tab Sistemi
`body.dataset.mobTab` = `'packs' | 'build' | 'equipped' | 'settings'`

CSS: `body[data-mob-tab="X"] #element { display:... !important }`

**switchMobTab(tab)** — tab değiştirir, aktif buton günceller, settings açılırsa `updateSettingsToggles()` çağırır.

### Ritual Alt Sekmeleri
`body.dataset.mobRitual` = `'effigy' | 'ambiance'`

- **Effigy**: body/blade/offhand/necklace/eyes/mouth
- **Ambiance**: pins → background → name (label'lar gizli, body'ler direkt açık)

**switchRitualTab(ritual)** — alt sekme değiştirir.

Önemli: section label'lara `display:block` değil `display:flex` kullan, yoksa flex layout bozulur.

---

## Nav Bar (Mobil)

```
Packs (layers icon) | Ritual (person-standing) | Equipped (backpack) | Options (gear)
```

SVG boyutu: `28x28`, `stroke-width:2`  
Aktif tab: `rgba(232,192,96,0.08)` arkaplan + amber alt çizgi

---

## Options Panel (`#mob-settings-panel`)

- Sound: Music toggle + SFX toggle (mor arkaplan, sarı yuvarlak)
- Links: Discord + Docs
- Menu bar'dan müzik/sfx/discord/docs butonları mobilde gizlendi (`display:none !important`)

---

## Demo Mode

Wallet bağlı değilken hardcode demo itemler yüklenir:
- Her kategoriden 2 common
- 1 rare bıçak (astral_dagger)

**buildDemoGrids()** — DOMContentLoaded'da ve disconnect'ta çağrılır.  
Wallet bağlanınca `loadCollection()` gerçek itemleri yükler, demo temizlenir.  
Packs section'da "Demo mode — connect wallet to unlock your collection." notu görünür.

---

## Item Sistemi

`PACK_ITEMS` object — tüm item path'leri rarity'ye göre gruplu.  
`makeWrap(src, title, path, extraClass)` — thumb element oluşturur.  
`buildGridFlatFromItems(gridId, items, key)` — items array'den grid doldurur.  
`buildGridRarityFromItems(gridId, data, key)` — rarity filter bar'lı grid.  
`addItemToGrid(path, cat, rarity)` — tek item ekler.  
`loadCollection()` — Wix'ten veya localStorage'dan gerçek itemleri yükler.

Item path formatı: `category/rarity/filename.ext`  
Örnek: `knife/rare/astral_dagger.png`

---

## Wallet

- Solana: `connectWallet()`, `disconnectWallet()`
- Tezos: ayrı connect flow
- Mobilde: `#wallet-inline-icons` — platform icon wrap'ları (disconnected/connecting/connected CSS class'ları)
- `walletConnected` global boolean

---

## Desktop Sidebar

Sol panel: `panelback.png` arkaplan, `logo2.png` + "Ritual Effigy Workshop" başlık, yükseklik 103px  
Sağ panel header ile aynı yükseklikte.

---

## Hint Sistemi

`toggleHint(btn, event)` — `#hint-popup` fixed top-center popup, 4s sonra kapanır.  
Butonlar: `<button class="hint-btn" data-hint="..." onclick="toggleHint(this,event)">`  
İkon: soru işareti SVG, `stroke-width:4`, `15x15`

---

## Önemli CSS Notları

- `display:block !important` section label'a verilirse flex layout bozulur — label'lara `display:flex !important` kullan
- Mobilde `flex-wrap:nowrap !important` section label'lara eklendi
- `#mob-tab-bar` sticky, `top:126px` (wallet label yüksekliği + menu bar yüksekliği)
- Bewitch box: `width:calc(100% - 24px)`, `margin-left:12px`

---

## Deployment

**ASLA production'a deploy etme** — sadece local çalış, Alper açıkça söylemeden push yapma.  
Local: Python Flask veya direkt dosya açma.
