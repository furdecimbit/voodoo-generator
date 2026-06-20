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
          <div id="wic-profile-info" style="display:none;flex-direction:column;align-items:flex-end;gap:1px;margin-right:10px;">
            <span id="wic-witch-name" style="font-family:Bloodcrow,serif;font-size:13px;letter-spacing:.08em;color:#e8c060;text-transform:uppercase;white-space:nowrap;"></span>
            <span id="wic-wallet-sub" style="font-family:Bloodcrow,serif;font-size:13px;letter-spacing:.05em;color:#5a4020;white-space:nowrap;"></span>
          </div>
          <button id="wic-avatar" onclick="toggleProfilePanel()" title="Profile" style="width:52px;height:52px;border-radius:50%;overflow:hidden;border:2px solid #3a2808;background:#0e0a04;flex-shrink:0;display:flex;align-items:center;justify-content:center;transition:border-color .2s;cursor:pointer;padding:0;position:relative;">
            <svg id="wic-av-default" viewBox="0 0 24 24" fill="none" stroke="#c8a050" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:22px;height:22px;flex-shrink:0;"><circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/></svg>
            <img id="wic-av-img" src="" alt="" style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover;display:none;">
          </button>
        </div>

      </div>
    </div>
    `;

  const css = `
    <style id="site-header-styles">
      html, body { -webkit-overflow-scrolling: touch; }
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

      /* Wallet area */
      #site-header-wallet {
        display:flex; align-items:center; gap:10px;
        position:relative; z-index:1;
      }
      #wic-profile-info { display:none; }
      #wic-avatar { border-color:#cc2020; box-shadow:0 0 8px #cc202044; margin-right:0 !important; }
      #wic-avatar.wallet-connected { border-color:#20cc50 !important; box-shadow:0 0 10px #20cc5066 !important; }

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
        width:52px; height:52px; border-radius:50%;
        border:2px solid #3a2808; background:#0e0a04;
        cursor:pointer; overflow:hidden; padding:0;
        display:flex; align-items:center; justify-content:center;
        transition:border-color .2s, transform .15s, box-shadow .2s;
        flex-shrink:0;
      }
      .wallet-icon-circle img { width:100%; height:100%; object-fit:cover; display:block; }
      .wallet-icon-circle svg { width:26px; height:26px; color:#c8a050; stroke:currentColor; }
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
        font-size:32px; color:#c8a050; line-height:0; padding:0; padding-bottom:2px;
      }
      #sidebar-toggle:hover { border-color:#6a4818; background:#1a1006; }

      /* ── Left drawer ── */
      #site-sidebar {
        position:fixed; top:82px; left:0;
        height:calc(100vh - 82px);
        width:220px;
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
        display:flex; align-items:center; gap:16px;
        padding:0 20px; height:58px;
        text-decoration:none; white-space:nowrap;
        color:#6a5030;
        font-family:'Bloodcrow',serif; font-size:18px; letter-spacing:.08em; text-transform:uppercase;
        transition:color .2s, background .2s;
        border-left:2px solid transparent;
      }
      .ssb-link:hover { color:#c8a050; background:rgba(232,192,96,.07); }
      .ssb-link.active { color:#e8c060; background:rgba(232,192,96,.1); border-left-color:#e8c060; }
      .ssb-icon { width:26px; height:26px; display:flex; align-items:center; justify-content:center; flex-shrink:0; }
      .ssb-icon svg, .ssb-icon i { width:22px; height:22px; }

      /* Socials */
      #site-sidebar-socials {
        padding: 14px 12px;
        border-bottom: 1px solid #2a1a06;
        display: flex;
        flex-direction: row;
        justify-content: center;
        gap: 8px;
      }
      .ssb-social {
        display: flex; align-items: center; justify-content: center;
        width: 40px; height: 40px; border-radius: 10px;
        text-decoration: none;
        color: #5a4020;
        border: 1px solid #2a1a06;
        transition: color .2s, background .2s, border-color .2s;
      }
      .ssb-social:hover { color: #c8a050; background: rgba(232,192,96,.07); border-color: #4a3010; }
      .ssb-social svg { width: 34px; height: 34px; flex-shrink: 0; }
      .ssb-social span { display: none; }


      /* Copyright */
      #ssb-copyright {
        margin-top: auto;
        padding: 10px 12px;
        text-align: center;
        font-size: 11px; letter-spacing: .08em; text-transform: uppercase;
        color: #2a1a06;
      }


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
        #wic-avatar { width:40px !important; height:40px !important; }
      }
    </style>`;

  const mount = document.getElementById('site-header-mount');
  if(mount) mount.innerHTML = css + html;
  else document.body.insertAdjacentHTML('afterbegin', css + html);

  // Inject profile dropdown
  const profilePanelEl = document.createElement('div');
  profilePanelEl.id = 'profile-expand-panel';
  profilePanelEl.style.cssText = 'position:fixed;display:none;flex-direction:column;gap:8px;background:linear-gradient(160deg,#1a1006,#120c04);border:1px solid #3a2808;border-radius:14px;padding:16px;min-width:260px;box-shadow:0 8px 32px #000000cc;z-index:99999;font-family:Bloodcrow,serif;';
  profilePanelEl.innerHTML = `
    <div style="padding:8px 4px;border-bottom:1px solid #2a1a08;">
      <div id="pep-witchname" style="font-size:17px;letter-spacing:.1em;text-transform:uppercase;color:#e8c060;white-space:nowrap;"></div>
      <div id="pep-username" style="font-size:13px;letter-spacing:.06em;color:#5a4020;margin-top:3px;"></div>
    </div>
    <div style="padding:8px 4px;border-bottom:1px solid #2a1a08;display:flex;flex-direction:column;gap:6px;">
      <div style="font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:#4a3010;margin-bottom:4px;">Wallet</div>
      <div style="display:flex;align-items:center;gap:10px;">
        <img src="drip.jpeg" style="width:30px;height:30px;border-radius:50%;object-fit:cover;border:1px solid #3a2010;flex-shrink:0;">
        <span id="pep-sol-addr" style="font-size:13px;color:#5a4020;letter-spacing:.04em;flex:1;">Not connected</span>
        <button id="pep-sol-btn" onclick="window._pepToggleSol()" style="font-family:Bloodcrow,serif;font-size:13px;letter-spacing:.07em;text-transform:uppercase;color:#c8a050;background:#0e0804;border:1px solid #3a2810;padding:5px 14px;border-radius:10px;cursor:pointer;">Connect</button>
      </div>
      <div style="display:flex;align-items:center;gap:10px;">
        <img src="objkt.jpeg" style="width:30px;height:30px;border-radius:50%;object-fit:cover;border:1px solid #3a2010;flex-shrink:0;">
        <span id="pep-tez-addr" style="font-size:13px;color:#5a4020;letter-spacing:.04em;flex:1;">Not connected</span>
        <button id="pep-tez-btn" onclick="window._pepToggleTez()" style="font-family:Bloodcrow,serif;font-size:13px;letter-spacing:.07em;text-transform:uppercase;color:#c8a050;background:#0e0804;border:1px solid #3a2810;padding:5px 14px;border-radius:10px;cursor:pointer;">Connect</button>
      </div>
    </div>
    <a href="profile.html" style="display:block;padding:10px 4px;font-family:Bloodcrow,serif;font-size:16px;letter-spacing:.08em;text-transform:uppercase;color:#c8a050;text-decoration:none;border-bottom:1px solid #2a1a08;">Go to Profile</a>
    <button onclick="window.hexLogout&&window.hexLogout();window.location.href='login.html';" style="font-family:Bloodcrow,serif;font-size:16px;letter-spacing:.08em;text-transform:uppercase;color:#e05030;background:none;border:none;cursor:pointer;padding:10px 4px;text-align:left;">Sign Out</button>
  `;
  document.body.appendChild(profilePanelEl);

  function toggleProfilePanel(){
    const panel = document.getElementById('profile-expand-panel');
    const btn   = document.getElementById('wic-avatar');
    if(!panel || !btn) return;
    const isOpen = panel.style.display === 'flex';
    if(!isOpen){
      const rect = btn.getBoundingClientRect();
      panel.style.top   = (rect.bottom + 8) + 'px';
      panel.style.right = (window.innerWidth - rect.right) + 'px';
      panel.style.left  = 'auto';
      // populate
      const wn = document.getElementById('pep-witchname');
      const un = document.getElementById('pep-username');
      if(wn) wn.textContent = sessionStorage.getItem('hex_witchName') || '';
      if(un) un.textContent = sessionStorage.getItem('hex_username') || '';
    }
    panel.style.display = isOpen ? 'none' : 'flex';
  }
  window.toggleProfilePanel = toggleProfilePanel;

  // Fallback connect — used when page doesn't define its own
  async function _fallbackConnectSol(){
    const p = window.phantom?.solana || (window.solana?.isPhantom ? window.solana : null) || window.solana;
    if(!p){ alert('No Solana wallet found. Please install Phantom.'); return; }
    try {
      const resp = await p.connect();
      const pubkey = resp.publicKey.toString();
      window._solanaProvider = p;
      setHeaderWallet(pubkey, 'sol');
    } catch(e){ console.error('Sol connect error', e); }
  }
  async function _fallbackDisconnectSol(){
    try{ if(window._solanaProvider) await window._solanaProvider.disconnect(); }catch(e){}
    try{ if(window.phantom?.solana) await window.phantom.solana.disconnect(); }catch(e){}
    window._solanaProvider = null;
    setHeaderWallet(null, null);
  }

  window._pepToggleSol = function(){
    const key = sessionStorage.getItem('wallet_key');
    const platform = sessionStorage.getItem('wallet_platform');
    const connected = key && platform !== 'tez';
    if(connected){
      const fn = typeof window.disconnectWallet === 'function' ? window.disconnectWallet : _fallbackDisconnectSol;
      fn();
    } else {
      const fn = typeof window.connectWallet === 'function' ? window.connectWallet : _fallbackConnectSol;
      fn();
    }
  };
  window._pepToggleTez = function(){
    const key = sessionStorage.getItem('wallet_key');
    const platform = sessionStorage.getItem('wallet_platform');
    const connected = key && platform === 'tez';
    if(connected){
      if(typeof window.disconnectTezos === 'function') window.disconnectTezos();
    } else {
      if(typeof window.connectTezos === 'function') window.connectTezos();
    }
  };

  // Close profile panel when clicking outside
  document.addEventListener('click', e => {
    const panel = document.getElementById('profile-expand-panel');
    const btn   = document.getElementById('wic-avatar');
    if(!panel || !btn) return;
    if(panel.style.display === 'flex' && !panel.contains(e.target) && e.target !== btn && !btn.contains(e.target)){
      panel.style.display = 'none';
    }
  });

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
      <div id="site-sidebar-socials">
        <a href="https://alper-ozdil-projetcs.gitbook.io/hex-and-stitch" target="_blank" class="ssb-social" title="GitBook">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg>
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

      <div id="site-sidebar-inner">${sidebarItemsHTML}</div>


      <div id="ssb-copyright">© 2025 Hex &amp; Stitch<br><a href="https://alperozdil.com" target="_blank" style="color:#4a3010;text-decoration:none;font-size:10px;letter-spacing:.06em;">Designed &amp; Developed by Alper Özdil</a></div>
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
    if(key && platform){
      sessionStorage.setItem('wallet_key', key);
      sessionStorage.setItem('wallet_platform', platform);
      // Link wallet to hex account if logged in
      const hexUserId = sessionStorage.getItem('hex_userId');
      if(hexUserId){
        fetch(`${WIX_API}/linkWallet`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ userId: hexUserId, wallet: key, platform: platform === 'tez' ? 'tez' : 'sol' })
        }).then(r => r.json()).then(d => {
          if(d.error && d.error.includes('already assigned')){
            alert('This wallet is already assigned to another account.');
            setHeaderWallet(null, null);
          }
        }).catch(() => {});
        _updateWitchNameUI(sessionStorage.getItem('hex_witchName'));
      } else if(!sessionStorage.getItem('witch_name')){
        _updateWitchNameUI(null);
      } else {
        _updateWitchNameUI(sessionStorage.getItem('witch_name'));
      }
    } else {
      sessionStorage.removeItem('wallet_key');
      sessionStorage.removeItem('wallet_platform');
      sessionStorage.removeItem('witch_name');
      _updateWitchNameUI(null);
    }
    // Profile info row
    const profileInfo = document.getElementById('wic-profile-info');
    const walletSub   = document.getElementById('wic-wallet-sub');
    if(profileInfo) profileInfo.style.display = (key && platform) ? 'flex' : 'none';
    if(walletSub && key && platform) {
      const short = key.slice(0,4)+'...'+key.slice(-4);
      walletSub.textContent = (platform === 'sol' ? 'Solana · ' : 'Tezos · ') + short;
    }
    const avEl = document.getElementById('wic-avatar');
    if(avEl) avEl.classList.toggle('wallet-connected', !!(key && platform));
    if(typeof window.updateLandingWallet === 'function') window.updateLandingWallet();
    // Update profile panel wallet rows
    const pepSolAddr = document.getElementById('pep-sol-addr');
    const pepTezAddr = document.getElementById('pep-tez-addr');
    const pepSolBtn  = document.getElementById('pep-sol-btn');
    const pepTezBtn  = document.getElementById('pep-tez-btn');
    if(key && platform === 'sol'){
      if(pepSolAddr) pepSolAddr.textContent = key.slice(0,4)+'...'+key.slice(-4);
      if(pepSolBtn)  pepSolBtn.textContent  = 'Disconnect';
      if(pepTezAddr) pepTezAddr.textContent = 'Not connected';
      if(pepTezBtn)  pepTezBtn.textContent  = 'Connect';
    } else if(key && platform === 'tez'){
      if(pepTezAddr) pepTezAddr.textContent = key.slice(0,4)+'...'+key.slice(-4);
      if(pepTezBtn)  pepTezBtn.textContent  = 'Disconnect';
      if(pepSolAddr) pepSolAddr.textContent = 'Not connected';
      if(pepSolBtn)  pepSolBtn.textContent  = 'Connect';
    } else {
      if(pepSolAddr) pepSolAddr.textContent = 'Not connected';
      if(pepTezAddr) pepTezAddr.textContent = 'Not connected';
      if(pepSolBtn)  pepSolBtn.textContent  = 'Connect';
      if(pepTezBtn)  pepTezBtn.textContent  = 'Connect';
    }
  }
  window.setHeaderWallet = setHeaderWallet;

  function _ensureHeaderProfile(){
    const av = document.getElementById('wic-avatar');
    if(av){
      av.addEventListener('mouseenter', () => { av.style.borderColor = '#6a4818'; });
      av.addEventListener('mouseleave', () => { _refreshHeaderAvatar(false); });
    }
  }

  function _updateWitchNameUI(name){
    const el = document.getElementById('wic-witch-name');
    if(el) el.textContent = name || '';
    _refreshHeaderAvatar(false);
  }

  function _refreshHeaderAvatar(hover){
    const av  = document.getElementById('wic-avatar');
    const img = document.getElementById('wic-av-img');
    const def = document.getElementById('wic-av-default');
    if(!av || !img || !def) return;
    const idx = localStorage.getItem('profile_avatar_idx');
    const connected = !!sessionStorage.getItem('wallet_key');
    av.style.borderColor = hover ? '#6a4818' : '#3a2808';
    if(idx !== null){
      const pad = String(parseInt(idx)).padStart(2,'0');
      img.src = `avatars/avatar_${pad}.png`;
      img.style.display = 'block';
      def.style.display = 'none';
    } else {
      img.style.display = 'none';
      def.style.display = '';
    }
  }

  // Refresh when avatar picked on profile page (same tab — storage event doesn't fire)
  window._headerAvatarRefresh = _refreshHeaderAvatar;

  // Refresh avatar when localStorage changes (cross-tab)
  window.addEventListener('storage', e => {
    if(e.key === 'profile_avatar_idx') _refreshHeaderAvatar(false);
  });

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
  _ensureHeaderProfile();
  _refreshHeaderAvatar(false);
  if(savedKey) setHeaderWallet(savedKey, savedPlatform);

  // Hex account (username/password login) — show witchName if logged in
  const hexWitchName = sessionStorage.getItem('hex_witchName');
  if(hexWitchName) _updateWitchNameUI(hexWitchName);

  // Expose logout for other pages
  window.hexLogout = function(){
    sessionStorage.removeItem('hex_userId');
    sessionStorage.removeItem('hex_witchName');
    sessionStorage.removeItem('hex_username');
    _updateWitchNameUI(null);
  };

})();
