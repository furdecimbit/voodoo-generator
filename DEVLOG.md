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

### getOrCreateProfile endpoint eklendi (http-functions.js)
- Wallet bağlanınca Wix'te satır yoksa otomatik oluşturuyor
- Varsa `witchname` field'ını döndürüyor
- witchName üretme henüz YOK — null dönüyor (auth sistemi ile gelecek)
- **Wix wallet field sorunu:** eski kayıtlar `SolanaWallet` dolu `wallet` boş — `wallet` field'ı manuel doldurulmalı

### Paket açılış videoları rarity'e göre ayrıldı
- `common.MP4`, `rare.MP4`, `legendary.MP4`, `ultimate.MP4` klasöre eklendi
- `startOpen()` artık `${activePack.rarity}.MP4` oynuyor

### Skip butonu videonun altına taşındı ve büyütüldü

### Login zorunluluğu — tüm sayfalara eklendi
- index.html, forge.html, pack-room.html, collection.html, profile.html → `hex_userId` yoksa `login.html`'e yönlendir
- profile.html: wallet bağlı olmasa da profil kartı gösterilir, wallet bağlama hint'i görünür
- Wallet bağlanınca hint gizlenir
- witchName: `hex_witchName` (username login) veya `witch_name` (wallet login) okunur

### Kullanıcı auth sistemi — TAMAMLANDI

**Backend (http-functions.js — Wix'e yapıştırılacak):**
- `POST /signup` — username (min 3) + password (min 6) → SHA-256 hash → HexUsers CMS'e kayıt → witchName otomatik üretilir
- `POST /login` — username + hash karşılaştır → userId + witchName döner
- witchName prefixes: DarkRitual, ShadowWitch, VoidCaster, CursedSage, BoneWeaver, HexBinder, GrimSoul, BloodMoon, NightShade, AshWalker, RuneKeeper, SoulBinder, VexedSpirit, CryptWarden, DuskRite + #1000-9999

**Frontend:**
- `login.html` — Sign In / Create Account tab toggle, hata mesajları, Enter ile submit
- Başarılı girişte sessionStorage: `hex_userId`, `hex_witchName`, `hex_username` → index.html'e yönlendir
- Zaten giriş yapılmışsa direkt index.html'e yönlendir

**site-header.js:**
- Sayfa yüklenince `hex_witchName` sessionStorage'dan okuyup header'a yazar
- `window.hexLogout()` ile çıkış yapılabilir

**HexUsers CMS collection gerekli:** username, passwordHash, witchName, userId field'ları

### Kullanıcı auth sistemi — PLANLANДИ, henüz yapılmadı
- Karar: Wix Members yok, kendi custom login sistemi
- Wallet bağımsız profil: username + şifre
- Wix'te "HexUsers" koleksiyonu gerekiyor (username, passwordHash, witchName, userId)
- Devam için: önce Wix'te HexUsers koleksiyonu oluştur, sonra "kullanıcı sistemi yapalım" de

---

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

### HexMain tek koleksiyon migrasyonu — TAMAMLANDI

- **Backend (http-functions.js):** Import2 + HexUsers koleksiyonları → tek `HexMain` koleksiyonu
- `userId` primary key; `solanaWallet`, `tezosWallet` ayrı field; `items`, `openedMints`, `slots` JSON string
- Yeni endpoint'ler: `/signup`, `/login`, `/linkWallet`, `/getItems?userId=`, `/getOpenedMints?userId=`, `/openPack` (body: userId), `/getSlots?userId=`, `/saveSlots` (body: userId)
- **Frontend güncellemeleri:**
  - `pack-room.html`: `getOpenedMints` ve `openPack` artık `userId` kullanıyor
  - `forge.html`: tüm Wix çağrıları `userId` kullanıyor
  - `collection.html`: `getItems` artık `userId` kullanıyor
  - `site-header.js`: wallet bağlanınca `hex_userId` varsa `POST /linkWallet` çağırıyor (getOrCreateProfile kaldırıldı)
- `login.html`: Sign In / Create Account tabları, sessionStorage: `hex_userId`, `hex_witchName`, `hex_username`
- Tüm sayfalara login guard eklendi (`hex_userId` yoksa `login.html`)
- `HexMain.csv` Wix import için `/voodoo` klasöründe

---

### `packs.html` linkleri `pack-room.html` olarak düzeltildi
- `index.html` splash "Buy Mystery Packs" linki: `packs.html` → `pack-room.html`
- `index.html` menü Packs kartı: `packs.html` → `pack-room.html`
- `forge.html` pack open yönlendirmesi: `packs.html` → `pack-room.html`
- `pack_test.html` pack open yönlendirmesi: `packs.html` → `pack-room.html`
