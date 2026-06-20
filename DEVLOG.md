# Voodoo / Hex & Stitch — Dev Log

---

## 2026-06-12

### Packs kartı pack_test.html'e bağlandı
- `index.html`: packs kartından `locked` class kaldırıldı, `href="pack-room.html"` eklendi
- Badge: "Wallet required" → "Demo available"
- Wallet bağlanınca unlock listesinden packs çıkarıldı (zaten açık olduğu için)

### pack-room.html — 3-panel Pack Room sıfırdan yazıldı
- Sol panel: Wallet bağlantısı (Solana + Tezos) + Helius ile çekilen açılmamış pack listesi
- Orta panel: Pack seç → float → tıkla → video → kart kart reveal (her karta tıkla) → Claim
- Sağ panel: Session'da açılan pack sayısı rarity'ye göre
- Dev helper: `devLoadPacks()` console'dan test için

---

## 2026-06-16

### Pack duplicate-open güvenlik fix

**Backend (hex/src/backend/http-functions.js — Wix'e manuel yapıştırılacak):**
- `mintAddress` artık zorunlu parametre — eksikse `badRequest` döner
- Duplicate kontrol her zaman çalışır (`if (existing && mintAddress)` → `if (existing)`)

**Frontend (pack-room.html):**
- `startOpen()`: mint ID yoksa açmayı engeller, kullanıcıya mesaj verir
- `openPack` yanıtı kontrol edilir: `already opened` → reset + uyarı; diğer server hatalarında local roll yapılmaz
- Network hatasında (Wix'e ulaşılamıyor) local roll fallback korunur

---

### forge.html — pins grid sırası düzeltildi
- Grid önce, "Placed: X/5" ve açıklama metni grid'in altına taşındı

---

### Pack açınca itemler forge'a yansımıyordu — düzeltildi
- **Sorun:** pack-room'da Wix `openPack` başarılı olsa da olmasa da rolled items localStorage'a kaydedilmiyordu; forge localStorage fallback'e düşünce boş geliyordu
- **Fix:** `revealCards()` içinde itemler hem Wix'e hem `wallet_${currentWallet}_collection` key'li localStorage'a yazılıyor (forge'daki `walletKey('collection')` formatıyla eşleştirildi)

### Forge sayfasında wallet auto-restore eklendi
- **Sorun:** `site-header.js` sessionStorage'dan wallet'ı restore ederken sadece header UI'yı güncelliyor, `window.connectWallet()` çağırmıyor; forge `loadWalletPacks` hiç tetiklenmiyordu
- **Fix:** `forge.html` `DOMContentLoaded`'da sessionStorage'dan `wallet_key` / `wallet_platform` okuyup `loadWalletPacks` çağırıyor — sayfa ilk açıldığında wallet bağlıymış gibi collection yükleniyor

### Pack kart sayısı kuralları düzeltildi
- **Sorun:** Wix `packItems.js` `rollPackItems` rastgele 2 veya 3 kart veriyordu
- **Fix:** Common 5×C, Rare 2×R+1×C, Legendary 2×L+1×R+1×C, Ultimate 2×U+1×L+1×R+1×C
- Wix editöre manuel yapıştırılması gerekiyor: `/Documents/hex/src/backend/packItems.js`

### index.html mobil düzeltmeleri
- Splash butonlar (`width:400px` sabit) → `min(400px, calc(100vw - 32px))` — dar ekranda taşmıyor
- `#splash-profile` genişliği de aynı formüle geçirildi
- `@media (max-width:480px)`: font, padding, ikon küçültüldü
- `#menu-body` `overflow:hidden` eklendi; `#landing-cards` `height:100vh` → `height:100%` — `position:fixed; inset:0` parent'ı kullanıyor, 4 kart tam ekrana sığıyor, scroll yok

### pack-room kart reveal → stacked deck UI

- Kartlar yan yana grid yerine üst üste stacked deck olarak gösteriliyor
- En öndeki karta basınca flip animasyonu → 900ms sonra sağa uçarak kayboluyor
- Bir sonraki kart otomatik öne geçiyor, tüm kartlar bitince "Close" butonu görünüyor
- "Claim Items" → "Close" olarak yeniden adlandırıldı
- `stackCards[]` global array ile sıra takibi, `positionStack()` her çıkarma sonrası offset yeniden hesaplar

---

### `packs.html` linkleri `pack-room.html` olarak düzeltildi
- `index.html` splash "Buy Mystery Packs" linki: `packs.html` → `pack-room.html`
- `index.html` menü Packs kartı: `packs.html` → `pack-room.html`
- `forge.html` pack open yönlendirmesi: `packs.html` → `pack-room.html`
- `pack_test.html` pack open yönlendirmesi: `packs.html` → `pack-room.html`
