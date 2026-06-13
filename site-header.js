const CDN_BASE = 'https://cdn.jsdelivr.net/gh/furdecimbit/voodoo-generator@main';
const WIX_API  = 'https://www.alperozdil.com/_functions';

(function(){
  const page = document.documentElement.dataset.page || 'forge';

  const NAV_LUCIDE = {
    home:        'house',
    forge:       'person-standing',
    packs:       'layers',
    collection:  'package-open',
    leaderboard: 'trophy',
    profile:     'user-round',
  };

  const nav = [
    { id:'home',       label:'Home',       href:'index.html' },
    { id:'forge',      label:'Ritual',     href:'forge.html' },
    { id:'packs',      label:'Packs',      href:'pack-room.html' },
    { id:'collection', label:'Collection', href:'collection.html' },
    { id:'profile',    label:'Profile',    href:'profile.html' },
  ];

  const sidebarItemsHTML = nav.map(n => `
    <a href="${n.href}" class="ssb-link${n.id === page ? ' active' : ''}">
      <span class="ssb-icon"><i data-lucide="${NAV_LUCIDE[n.id]}"></i></span>
      <span class="ssb-label">${n.label}</span>
    </a>
  `).join('');

  const html = `
    <div id="site-header">
      <div id="site-header-top">

        <!-- Left: hamburger + logo -->
        <div id="site-header-left">
          <button id="sidebar-toggle" onclick="window.toggleNavDrawer()" title="Menu">&#9776;</button>
          <div id="site-header-brand">
            <img id="site-header-logo" src="logo2.png" alt="Hex &amp; Stitch">
          </div>
        </div>

        <!-- Wallet — icon + dropdown -->
        <div id="site-header-wallet">
          <span id="wic-demo-label">DEMO MODE — CONNECT TO GET PACKS &amp; ITEMS</span>
          <button class="wallet-icon-circle disconnected" id="wic-main" onclick="toggleWalletPanel()" title="Wallet">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 7V4a1 1 0 0 0-1-1H5a2 2 0 0 0 0 4h15a1 1 0 0 1 1 1v4h-3a2 2 0 0 0 0 4h3a1 1 0 0 0 1-1v-2a1 1 0 0 0-1-1"/><path d="M3 5v14a2 2 0 0 0 2 2h15a1 1 0 0 0 1-1v-4"/></svg>
          </button>
        </div>

      </div>
    </div>
    `;

  const css = `
    <style id="site-header-styles">
      @font-face { font-family:'Bloodcrow'; src:url('${CDN_BASE}/bloodcrowc.ttf'); }

      #site-header {
        width:100%; position:sticky; top:0; z-index:1000;
        font-family:'Bloodcrow',serif;
        border-bottom:2px solid #3a2808;
      }

      /* ── Top bar ── */
      #site-header-top {
        display:flex; align-items:center; justify-content:space-between;
        padding:0 28px; height:80px;
        background:linear-gradient(90deg,#120c04,#0e0a04,#120c04);
        position:relative; overflow:hidden;
      }
      #site-header-top::before {
        content:''; position:absolute; inset:0;
        background:url('panelback.png') center/cover no-repeat;
        opacity:.15; pointer-events:none;
      }

      /* Left group */
      #site-header-left {
        display:flex; align-items:center; gap:12px;
        position:relative; z-index:1;
      }

      /* Brand */
      #site-header-brand {
        display:flex; align-items:center;
      }
      #site-header-logo {
        height:62px; width:auto;
        filter:drop-shadow(0 0 14px #e8c06055);
      }

      /* Demo label */
      #wic-demo-label {
        font-family:'Bloodcrow',serif; font-size:13px; letter-spacing:.07em;
        color:#7a5828; white-space:nowrap; margin-right:12px;
        text-transform:uppercase;
      }

      /* Wallet area */
      #site-header-wallet {
        display:flex; align-items:center; gap:0;
        position:relative; z-index:1;
      }

      /* Dropdown panel — appended to body, truly above everything */
      #wallet-expand-panel {
        position:fixed;
        display:none;
        flex-direction:column; gap:6px;
        background:linear-gradient(160deg,#1a1006,#120c04);
        border:1px solid #3a2808; border-radius:12px;
        padding:12px; min-width:240px;
        box-shadow:0 8px 32px #000000cc;
        z-index:99999;
        font-family:'Bloodcrow',serif;
      }
      #wallet-expand-panel.open { display:flex; }
      .wep-item {
        display:flex; align-items:center; gap:10px;
        padding:8px 4px;
        border-bottom:1px solid #2a1a08;
      }
      .wep-item:last-child { border-bottom:none; }
      .wep-logo {
        width:32px; height:32px; border-radius:50%; object-fit:cover;
        border:1px solid #4a3010; flex-shrink:0;
      }
      .wep-info { display:flex; flex-direction:column; gap:2px; flex:1; min-width:0; }
      .wep-name { font-size:13px; letter-spacing:.08em; color:#c8a050; text-transform:uppercase; }
      .wep-addr { font-size:11px; color:#70c880; letter-spacing:.05em; }
      .wep-btn {
        font-family:'Bloodcrow',serif; font-size:12px; letter-spacing:.07em;
        text-transform:uppercase; color:#8a7040;
        background:#0e0804; border:1px solid #3a2810;
        padding:5px 12px; border-radius:14px; cursor:pointer;
        transition:color .2s, border-color .2s;
        white-space:nowrap; flex-shrink:0;
      }
      .wep-btn:hover { color:#e8c060; border-color:#6a4818; }
      .wep-btn.disconnect { color:#804030; border-color:#4a2010; }
      .wep-btn.disconnect:hover { color:#e05030; border-color:#802010; }

      /* Icon circles */
      #wallet-icons { display:flex; align-items:center; gap:8px; }
      .wallet-icon-circle {
        width:44px; height:44px; border-radius:50%;
        border:2px solid #3a2808; background:#0e0a04;
        cursor:pointer; overflow:hidden; padding:0;
        display:flex; align-items:center; justify-content:center;
        transition:border-color .2s, transform .15s, box-shadow .2s;
        flex-shrink:0;
      }
      .wallet-icon-circle img { width:100%; height:100%; object-fit:cover; display:block; }
      .wallet-icon-circle svg { width:22px; height:22px; color:#c8a050; stroke:currentColor; }
      .wallet-icon-circle:hover { border-color:#6a4818; transform:scale(1.08); }
      .wallet-icon-circle.connected    { border-color:#20cc50; box-shadow:0 0 10px #20cc5066; }
      .wallet-icon-circle.disconnected { border-color:#cc2020; box-shadow:0 0 10px #cc202066; }
      .wallet-icon-circle.active       { border-color:#e8c060; box-shadow:0 0 12px #e8c06044; }

      /* Syncing spinner */
      @keyframes wic-spin { to { transform: rotate(360deg); } }
      .wallet-icon-circle.syncing {
        border-color: transparent;
        border-top-color: #e8c050;
        border-right-color: #e8c05066;
        animation: wic-spin .7s linear infinite;
        box-shadow: none;
      }
      .wallet-icon-circle.syncing svg { opacity: .4; }

      /* ── Hamburger toggle button ── */
      #sidebar-toggle {
        width:44px; height:44px; border-radius:12px;
        border:1px solid #3a2808; background:#0e0a04;
        display:flex; align-items:center; justify-content:center;
        cursor:pointer; flex-shrink:0;
        position:relative; z-index:1;
        transition:border-color .2s, background .2s;
        font-size:22px; color:#c8a050; line-height:1; padding:0;
      }
      #sidebar-toggle:hover { border-color:#6a4818; background:#1a1006; }

      /* ── Left drawer ── */
      #site-sidebar {
        position:fixed; top:82px; left:0;
        height:calc(100vh - 82px);
        width:200px;
        background:linear-gradient(180deg,#120c04ee,#0e0a04ee);
        border-right:1px solid #3a2808;
        z-index:1001;
        transform:translateX(-100%);
        transition:transform .25s cubic-bezier(.4,0,.2,1);
        display:flex; flex-direction:column; justify-content:space-between;
        backdrop-filter:blur(8px);
      }
      #site-sidebar.open { transform:translateX(0); }
      #site-sidebar-inner {
        display:flex; flex-direction:column;
        padding:10px 0;
      }
      .ssb-link {
        display:flex; align-items:center; gap:14px;
        padding:0 20px; height:50px;
        text-decoration:none; white-space:nowrap;
        color:#6a5030;
        font-family:'Bloodcrow',serif; font-size:15px; letter-spacing:.08em; text-transform:uppercase;
        transition:color .2s, background .2s;
        border-left:2px solid transparent;
      }
      .ssb-link:hover { color:#c8a050; background:rgba(232,192,96,.07); }
      .ssb-link.active { color:#e8c060; background:rgba(232,192,96,.1); border-left-color:#e8c060; }
      .ssb-icon { width:22px; height:22px; display:flex; align-items:center; justify-content:center; flex-shrink:0; }
      .ssb-icon svg, .ssb-icon i { width:18px; height:18px; }

      /* Socials */
      #site-sidebar-socials {
        margin-top: auto;
        padding: 16px 12px;
        border-top: 1px solid #2a1a06;
        display: flex;
        flex-direction: column;
        gap: 4px;
      }
      .ssb-social {
        display: flex; align-items: center; gap: 12px;
        padding: 8px 10px; border-radius: 8px;
        text-decoration: none;
        color: #5a4020;
        font-family: 'Bloodcrow', serif; font-size: 14px; letter-spacing: .08em; text-transform: uppercase;
        transition: color .2s, background .2s;
      }
      .ssb-social:hover { color: #c8a050; background: rgba(232,192,96,.07); }
      .ssb-social svg { width: 18px; height: 18px; flex-shrink: 0; }

      /* Admin gate */
      #ssb-admin-wrap {
        padding: 10px 12px 6px;
        border-top: 1px solid #2a1a06;
      }
      #ssb-admin-gate {
        display: flex; gap: 6px;
      }
      #ssb-admin-input {
        flex: 1; background: #1a0e04; border: 1px solid #3a2810;
        border-radius: 6px; padding: 7px 10px;
        color: #c8a050; font-family: 'Bloodcrow', serif; font-size: 13px;
        letter-spacing: .06em; outline: none;
      }
      #ssb-admin-input::placeholder { color: #5a4020; }
      #ssb-admin-gate button {
        background: #2a1a06; border: 1px solid #3a2810; border-radius: 6px;
        color: #c8a050; font-size: 16px; width: 34px; cursor: pointer;
        transition: background .2s;
      }
      #ssb-admin-gate button:hover { background: #3a2810; }

      /* Backdrop */
      #site-sidebar-backdrop {
        display:none; position:fixed; inset:0; z-index:1000;
        background:rgba(0,0,0,.45);
      }
      #site-sidebar-backdrop.open { display:block; }

      /* Responsive */
      @media (max-width:900px){
        #site-header-top { padding:0 16px; height:68px; }
        #site-header-logo { height:48px; }
        #site-sidebar { top:70px; height:calc(100vh - 70px); }
      }
      @media (max-width:640px){
        .wallet-icon-circle { width:36px; height:36px; }
        #wic-demo-label { display:none; }
      }
    </style>`;

  const mount = document.getElementById('site-header-mount');
  if(mount) mount.innerHTML = css + html;
  else document.body.insertAdjacentHTML('afterbegin', css + html);

  // Inject wallet dropdown directly into body so it's above all stacking contexts
  const panelEl = document.createElement('div');
  panelEl.id = 'wallet-expand-panel';
  panelEl.innerHTML = `
    <div class="wep-item" id="wep-sol">
      <img src="drip.jpeg" class="wep-logo" alt="Solana">
      <div class="wep-info">
        <span class="wep-name">Solana</span>
        <span class="wep-addr" id="wep-sol-addr"></span>
      </div>
      <button class="wep-btn" id="wep-sol-btn" onclick="headerConnectSol()">Connect</button>
    </div>
    <div class="wep-item" id="wep-tez">
      <img src="objkt.jpeg" class="wep-logo" alt="Tezos">
      <div class="wep-info">
        <span class="wep-name">Tezos</span>
        <span class="wep-addr" id="wep-tez-addr"></span>
      </div>
      <button class="wep-btn" id="wep-tez-btn" onclick="headerConnectTez()">Connect</button>
    </div>
    <div class="wep-item" id="wep-profile-link">
      <a href="profile.html" class="wep-btn" style="text-decoration:none;text-align:center;width:100%;display:block;">View Profile</a>
    </div>`;
  document.body.appendChild(panelEl);

  // Inject sidebar + backdrop
  {
    const sidebarEl = document.createElement('div');
    sidebarEl.id = 'site-sidebar';
    sidebarEl.innerHTML = `
      <div id="site-sidebar-inner">${sidebarItemsHTML}</div>
      <div id="ssb-admin-wrap">
        <div id="ssb-admin-gate">
          <input type="password" id="ssb-admin-input" placeholder="Admin secret…"
            onkeydown="if(event.key==='Enter') window.ssbAdminLogin()">
          <button onclick="window.ssbAdminLogin()">⛧</button>
        </div>
      </div>

      <div id="site-sidebar-socials">
        <a href="https://alper-ozdil-projetcs.gitbook.io/hex-and-stitch" target="_blank" class="ssb-social" title="GitBook">
          <svg viewBox="0 0 24 24" fill="currentColor"><path d="M10.802 17.77a.703.703 0 1 1-.002 1.406.703.703 0 0 1 .002-1.406m11.024-4.347a.703.703 0 1 1-.001 1.406.703.703 0 0 1 .001-1.406M4.987 6.965a.703.703 0 1 1-.002 1.406.703.703 0 0 1 .002-1.406m16.386 3.37c-.624-.626-1.492-.795-2.26-.557L16.06 6.73c.265-.76.1-1.638-.523-2.264a1.95 1.95 0 0 0-2.756 0 1.95 1.95 0 0 0 0 2.757c.623.623 1.49.793 2.258.557l3.05 3.05c-.266.76-.1 1.637.523 2.261a1.95 1.95 0 0 0 2.76-2.757zm-9.261 4.662c-.624-.626-1.491-.795-2.26-.557L6.8 11.387c.266-.76.1-1.638-.523-2.264a1.95 1.95 0 0 0-2.756 0 1.95 1.95 0 0 0 0 2.757c.623.623 1.49.793 2.258.557l3.052 3.05c-.266.76-.1 1.638.523 2.262a1.95 1.95 0 0 0 2.76-2.756z"/></svg>
          <span>GitBook</span>
        </a>
        <a href="https://discord.com/invite/V57fUq93xB" target="_blank" class="ssb-social" title="Discord">
          <svg viewBox="0 0 24 24" fill="currentColor"><path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028 14.09 14.09 0 0 0 1.226-1.994.076.076 0 0 0-.041-.106 13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128 10.2 10.2 0 0 0 .372-.292.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.892.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.955-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.946 2.418-2.157 2.418z"/></svg>
          <span>Discord</span>
        </a>
        <a href="http://x.com/alperozdilart" target="_blank" class="ssb-social" title="X">
          <svg viewBox="0 0 24 24" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-4.714-6.231-5.401 6.231H2.746l7.73-8.835L1.254 2.25H8.08l4.253 5.622 5.912-5.622zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>
          <span>X</span>
        </a>
      </div>
    `;
    document.body.appendChild(sidebarEl);

    const backdropEl = document.createElement('div');
    backdropEl.id = 'site-sidebar-backdrop';
    backdropEl.onclick = () => window.toggleNavDrawer();
    document.body.appendChild(backdropEl);
  }

  // Load Lucide icons
  if(typeof lucide !== 'undefined'){
    lucide.createIcons();
  } else {
    const s = document.createElement('script');
    s.src = 'https://unpkg.com/lucide@latest/dist/umd/lucide.min.js';
    s.onload = () => lucide.createIcons();
    document.head.appendChild(s);
  }

  // Close wallet panel when clicking outside
  document.addEventListener('click', e => {
    const panel  = document.getElementById('wallet-expand-panel');
    const circle = document.getElementById('wic-main');
    if(!panel || !circle) return;
    if(!panel.contains(e.target) && e.target !== circle && !circle.contains(e.target)){
      panel.classList.remove('open');
      circle.classList.remove('active');
    }
  });

  // ── Nav drawer toggle ──
  function toggleNavDrawer(){
    const sb = document.getElementById('site-sidebar');
    const bd = document.getElementById('site-sidebar-backdrop');
    if(sb) sb.classList.toggle('open');
    if(bd) bd.classList.toggle('open');
  }
  window.toggleNavDrawer = toggleNavDrawer;

  // ── Wallet panel toggle ──
  function toggleWalletPanel(){
    const panel  = document.getElementById('wallet-expand-panel');
    const circle = document.getElementById('wic-main');
    if(!panel || !circle) return;
    const isOpen = panel.classList.contains('open');
    if(!isOpen){
      const rect = circle.getBoundingClientRect();
      panel.style.top   = (rect.bottom + 8) + 'px';
      panel.style.right = (window.innerWidth - rect.right) + 'px';
      panel.style.left  = 'auto';
    }
    panel.classList.toggle('open', !isOpen);
    circle.classList.toggle('active', !isOpen);
  }
  window.toggleWalletPanel = toggleWalletPanel;

  // ── Header connect/disconnect ──
  function headerConnectSol(){
    const fn = window.connectWallet || window.connectSol;
    if(typeof fn === 'function') fn();
  }
  function headerConnectTez(){
    const fn = window.connectTezos || window.connectTez;
    if(typeof fn === 'function') fn();
  }
  function headerDisconnect(platform){
    if(platform === 'tez'){
      if(typeof window.disconnectTezos === 'function') window.disconnectTezos();
    } else {
      if(typeof window.disconnectWallet === 'function') window.disconnectWallet();
    }
    setHeaderWallet(null, null);
  }
  window.headerConnectSol  = headerConnectSol;
  window.headerConnectTez  = headerConnectTez;
  window.headerDisconnect  = headerDisconnect;

  window.ssbAdminLogin = function() {
    const input = document.getElementById('ssb-admin-input');
    if (input && input.value === 'hex-admin-2026') {
      window.open('admin.html', '_blank');
      input.value = '';
      toggleNavDrawer();
    } else if (input) {
      input.style.borderColor = '#8b2020';
      setTimeout(() => { input.style.borderColor = '#3a2810'; }, 800);
    }
  };

  // ── Wallet UI state ──
  function setHeaderWallet(key, platform){
    const circle   = document.getElementById('wic-main');
    const solAddr  = document.getElementById('wep-sol-addr');
    const tezAddr  = document.getElementById('wep-tez-addr');
    const solBtn   = document.getElementById('wep-sol-btn');
    const tezBtn   = document.getElementById('wep-tez-btn');
    const demoLabel = document.getElementById('wic-demo-label');
    const profileLink = document.getElementById('wep-profile-link');
    if(!circle) return;

    circle.classList.remove('connected','disconnected','syncing','active');
    if(solAddr) solAddr.textContent = '';
    if(tezAddr) tezAddr.textContent = '';
    if(solBtn){ solBtn.textContent='Connect'; solBtn.classList.remove('disconnect'); solBtn.onclick=headerConnectSol; }
    if(tezBtn){ tezBtn.textContent='Connect'; tezBtn.classList.remove('disconnect'); tezBtn.onclick=headerConnectTez; }

    if(profileLink) profileLink.style.display = (key && platform) ? '' : 'none';

    if(key && platform){
      const short = key.slice(0,4)+'...'+key.slice(-4);
      circle.classList.add('connected');
      circle.title = platform.toUpperCase()+': '+short;
      if(demoLabel) demoLabel.style.display = 'none';
      if(platform === 'tez'){
        if(tezAddr) tezAddr.textContent = short;
        if(tezBtn){ tezBtn.textContent='Disconnect'; tezBtn.classList.add('disconnect'); tezBtn.onclick=()=>headerDisconnect('tez'); }
      } else {
        if(solAddr) solAddr.textContent = short;
        if(solBtn){ solBtn.textContent='Disconnect'; solBtn.classList.add('disconnect'); solBtn.onclick=()=>headerDisconnect('sol'); }
      }
      sessionStorage.setItem('wallet_key', key);
      sessionStorage.setItem('wallet_platform', platform);
      // Fetch or create profile — witch name
      if(!sessionStorage.getItem('witch_name')){
        fetch(`${WIX_API}/getOrCreateProfile`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ wallet: key, platform })
        })
        .then(r => r.json())
        .then(d => {
          if(d.witchName){
            sessionStorage.setItem('witch_name', d.witchName);
            _updateWitchNameUI(d.witchName);
          }
        })
        .catch(() => {});
      } else {
        _updateWitchNameUI(sessionStorage.getItem('witch_name'));
      }
    } else {
      circle.classList.add('disconnected');
      circle.title = 'Wallet';
      if(demoLabel) demoLabel.style.display = '';
      sessionStorage.removeItem('wallet_key');
      sessionStorage.removeItem('wallet_platform');
      sessionStorage.removeItem('witch_name');
      _updateWitchNameUI(null);
    }
    if(typeof window.updateLandingWallet === 'function') window.updateLandingWallet();
  }
  window.setHeaderWallet = setHeaderWallet;

  function _updateWitchNameUI(name){
    let el = document.getElementById('wic-witch-name');
    if(!el){
      el = document.createElement('span');
      el.id = 'wic-witch-name';
      el.style.cssText = 'font-family:Bloodcrow,serif;font-size:13px;letter-spacing:.08em;color:#e8c060;text-transform:uppercase;white-space:nowrap;margin-right:14px;';
      const wallet = document.getElementById('site-header-wallet');
      if(wallet) wallet.insertBefore(el, wallet.firstChild);
    }
    el.textContent = name || '';
    el.style.display = name ? '' : 'none';
  }

  function setHeaderSyncing(on){
    const c = document.getElementById('wic-main');
    if(!c) return;
    if(on){ c.classList.remove('connected','disconnected'); c.classList.add('syncing'); }
    else   { c.classList.remove('syncing'); }
  }
  window.setHeaderSyncing = setHeaderSyncing;

  // Restore from session on page load
  const savedKey      = sessionStorage.getItem('wallet_key');
  const savedPlatform = sessionStorage.getItem('wallet_platform');
  if(savedKey) setHeaderWallet(savedKey, savedPlatform);

})();
