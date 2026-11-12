/* SynoArgus – fliken Översikt: alla kameror live, helskärm med ljud, tidslinje med inspelningar. Laddas efter app.js. */
'use strict';

Object.assign(EN, {
  'Översikt': 'Overview', 'Live': 'Live', 'Föregående händelse': 'Previous event', 'Nästa händelse': 'Next event', 'Inga händelser': 'No events',
  'Pausa / spela': 'Pause / play', 'Inga fler händelser – visar live': 'No more events – showing live',
  'Ingen inspelning': 'No recording', 'Laddar…': 'Loading…', 'Bild varannan sekund': 'Image every other second',
  'Livevideo är inte tillgänglig ({e}). Kamerorna visas som bilder varannan sekund.': 'Live video is not available ({e}). The cameras are shown as images every other second.',
  'go2rtc saknas': 'go2rtc is missing', 'Ljud': 'Sound', 'Stäng': 'Close', 'Spela upp': 'Play', 'Pausa': 'Pause',
  'Kunde inte läsa inspelningar: {e}': 'Could not read recordings: {e}',
  'Tryck på en kamera för helskärm med ljud. Dra tidslinjen för att spela upp inspelningar.': 'Tap a camera for full screen with sound. Drag the timeline to play recordings.',
  'Visa rådata för felsökning': 'Show raw data for troubleshooting', 'Sida {a} / {b}': 'Page {a} / {b}',
  'Lägg till en kamera under Inställningar > Kameror först.': 'Add a camera under Settings > Cameras first.',
  '1 kamera': '1 camera', 'Bild från händelsen – ingen inspelning': 'Image from the event – no recording',
  'Uppspelningen fastnade. Tryck ▶ för att försöka igen.': 'Playback got stuck. Press ▶ to try again.',
  'Gå till': 'Go to', 'Avbryt': 'Cancel', 'Välj datum och tid': 'Choose date and time',
  'Zooma in': 'Zoom in', 'Zooma ut': 'Zoom out', 'Återställ zoom': 'Reset zoom',
  'Tryck på en kamera för helskärm. Dra tidslinjen för att spela upp inspelningar. Tryck på datum och tid för att välja en tidpunkt.': 'Tap a camera for full screen. Drag the timeline to play recordings. Tap the date and time to choose a point in time.',
});

const LAYOUTS = { '1x1': [1, 1], '1x2': [2, 1], '1x3': [3, 1], '2x2': [2, 2], '2x3': [3, 2] };   // rader × kolumner -> [kolumner, rader]
const PX_PER_MIN = 8;          // tidslinjens skala
const REC_CHUNK = 300;         // sekunder per inspelningsbit
const STALL_S = 6;             // står videon still så länge laddas den om
const EVENT_NEAR_S = 30;       // visa händelsens bild om inspelning saknas inom så här många sekunder

/* ---------------------------------------------------------------- uppspelning av inspelningar (en per ruta) */
class RecPlayer {
  constructor(tile, cam, O) { this.tile = tile; this.cam = cam; this.O = O; this.video = tile.querySelector('video'); this.img = tile.querySelector('img'); this.gen = 0; }
  msg(text) { const m = this.tile.querySelector('.ov-msg'); m.hidden = !text; m.textContent = text || ''; }
  stop() {
    this.gen++; clearInterval(this.watch); clearTimeout(this.wait);
    const v = this.video; v.onended = v.onerror = null;
    try { v.pause(); v.removeAttribute('src'); v.load(); } catch (e) { /* */ }
  }
  /* spelar från T; hittas ingen inspelning visas händelsens bild, och finns nästa inspelning snart hoppar vi dit */
  async play(T, retry = 0) {
    const gen = ++this.gen, v = this.video, enc = encodeURIComponent(this.cam);
    clearInterval(this.watch); clearTimeout(this.wait);
    let r;
    try { r = await api(`/api/overview/recording?cam=${enc}&t=${T}&check=1`); } catch (e) { this.msg(e.message); return; }
    if (gen !== this.gen || !this.O.alive) return;
    if (!r.found) {
      v.hidden = true; v.removeAttribute('src'); delete v.dataset.t0; this.T = T;
      const ev = this.O.evs.filter(e => e.camera === this.cam && e.image && Math.abs(e.ts - T) <= EVENT_NEAR_S)
        .sort((a, b) => Math.abs(a.ts - T) - Math.abs(b.ts - T))[0];
      if (ev) { this.img.src = `/captures/${encodeURIComponent(ev.image).replace(/%2F/g, '/')}`; this.img.hidden = false; this.msg(''); this.badge(t('Bild från händelsen – ingen inspelning')); }
      else { this.img.hidden = true; this.badge(''); this.msg(r.detail || t('Ingen inspelning')); }
      if (r.next && r.next - T <= 60 && this.O.playing)        // nästa inspelning börjar snart: fortsätt där
        this.wait = setTimeout(() => { if (gen === this.gen) this.play(r.next); }, Math.max(0, (r.next - T) * 1000));
      return;
    }
    this.img.hidden = true; this.badge(''); this.msg(''); v.hidden = false;
    this.T = T; this.stop_ = r.stop; this.ongoing = r.ongoing; this.next = r.next;
    v.dataset.t0 = T;
    v.onended = () => { if (gen === this.gen) this.continue(); };
    v.onerror = () => { if (gen === this.gen) this.stuck(); };
    v.src = `/api/overview/recording?cam=${enc}&t=${T}&length=${REC_CHUNK}`;
    if (this.O.playing) v.play().catch(() => { /* */ });
    // vakt: står videon still trots att den ska spela laddas den om från samma ställe
    let last = -1, since = Date.now();
    this.retry = retry;
    this.watch = setInterval(() => {
      if (gen !== this.gen) return clearInterval(this.watch);
      if (!this.O.playing || v.ended) { since = Date.now(); last = v.currentTime; return; }
      if (v.currentTime !== last) { last = v.currentTime; since = Date.now(); return; }
      if (Date.now() - since > STALL_S * 1000) this.stuck();
    }, 1000);
  }
  /* biten är slut: fortsätt där den faktiskt slutade, eller på nästa inspelning om den här är slut */
  continue() {
    const v = this.video, T0 = Number(v.dataset.t0), played = v.currentTime || 0, at = T0 + played;
    const gen = this.gen, again = (t_, n) => { this.wait = setTimeout(() => { if (gen === this.gen) this.play(t_, n); }, 4000); };
    if (played < 1) {                                // inget nytt (inspelningen skrivs fortfarande): vänta och försök igen
      if ((this.retry || 0) >= 3) return this.stuckMsg();
      return again(T0, (this.retry || 0) + 1);
    }
    const r1 = t_ => Math.round(t_ * 10) / 10;
    if (at < this.stop_ - 1) return this.play(r1(at));          // bara biten tog slut
    if (this.next) return this.play(this.next);                  // inspelningen är slut: nästa
    if (this.ongoing) return again(r1(at), 0);                   // pågår fortfarande: vänta på mer
    this.play(r1(at));                                           // visar "Ingen inspelning" / händelsens bild
  }
  stuck() {
    const v = this.video, at = Number(v.dataset.t0 || this.T) + (v.currentTime || 0);
    if ((this.retry || 0) >= 3) return this.stuckMsg();
    this.play(Math.round(at * 10) / 10, (this.retry || 0) + 1);
  }
  stuckMsg() { clearInterval(this.watch); this.isStuck = true; this.msg(t('Uppspelningen fastnade. Tryck ▶ för att försöka igen.')); }
  resume() {
    const v = this.video;
    if (this.isStuck || v.hidden || v.readyState < 2 || v.error) { this.isStuck = false; return this.play(Number(v.dataset.t0 || this.T) + (v.currentTime || 0)); }
    v.play().catch(() => { /* */ });
  }
  badge(text) {
    let b = this.tile.querySelector('.ov-badge');
    if (!b) { b = document.createElement('div'); b.className = 'ov-badge'; this.tile.querySelector('.ov-media').appendChild(b); }
    b.hidden = !text; b.textContent = text || '';
  }
}

/* ---------------------------------------------------------------- zoom i helskärm (nyp, dra, dubbeltryck, knappar) */
class Zoom {
  constructor(area, target) {
    this.area = area; this.el = target; this.s = 1; this.x = 0; this.y = 0; this.pts = new Map(); this.lastTap = 0;
    area.addEventListener('pointerdown', e => this.down(e));
    area.addEventListener('pointermove', e => this.move(e));
    ['pointerup', 'pointercancel', 'pointerleave'].forEach(n => area.addEventListener(n, e => this.up(e)));
    area.addEventListener('wheel', e => { e.preventDefault(); const p = this.local(e); this.zoomAt(this.s * (e.deltaY < 0 ? 1.15 : 1 / 1.15), p.x, p.y); }, { passive: false });
  }
  local(e) { const r = this.area.getBoundingClientRect(); return { x: e.clientX - r.left, y: e.clientY - r.top }; }
  apply() {
    const w = this.area.clientWidth, h = this.area.clientHeight;
    this.s = Math.min(6, Math.max(1, this.s));
    this.x = Math.min(0, Math.max(w * (1 - this.s), this.x)); this.y = Math.min(0, Math.max(h * (1 - this.s), this.y));
    this.el.style.transform = this.s === 1 ? '' : `translate(${this.x}px, ${this.y}px) scale(${this.s})`;
    this.area.classList.toggle('zoomed', this.s > 1);
  }
  zoomAt(s, cx, cy) { const k = Math.min(6, Math.max(1, s)) / this.s; this.x = cx - (cx - this.x) * k; this.y = cy - (cy - this.y) * k; this.s *= k; this.apply(); }
  step(f) { this.zoomAt(this.s * f, this.area.clientWidth / 2, this.area.clientHeight / 2); }
  reset() { this.s = 1; this.x = this.y = 0; this.apply(); }
  down(e) {
    this.area.setPointerCapture?.(e.pointerId);
    this.pts.set(e.pointerId, this.local(e));
    if (this.pts.size === 2) { const [a, b] = [...this.pts.values()]; this.pinch = { d: Math.hypot(a.x - b.x, a.y - b.y), s: this.s }; }
    if (this.pts.size === 1) {
      const now = Date.now(), p = this.local(e);
      if (now - this.lastTap < 300) { this.s > 1 ? this.reset() : this.zoomAt(2.5, p.x, p.y); this.lastTap = 0; } else this.lastTap = now;
    }
  }
  move(e) {
    if (!this.pts.has(e.pointerId)) return;
    const prev = this.pts.get(e.pointerId), p = this.local(e);
    this.pts.set(e.pointerId, p);
    if (this.pts.size === 2 && this.pinch) {
      const [a, b] = [...this.pts.values()], d = Math.hypot(a.x - b.x, a.y - b.y);
      this.zoomAt(this.pinch.s * d / Math.max(1, this.pinch.d), (a.x + b.x) / 2, (a.y + b.y) / 2);
    } else if (this.pts.size === 1 && this.s > 1) { this.x += p.x - prev.x; this.y += p.y - prev.y; this.apply(); }
  }
  up(e) { this.pts.delete(e.pointerId); if (this.pts.size < 2) this.pinch = null; }
}

/* ---------------------------------------------------------------- liveström (fMP4 via WebSocket, go2rtc-protokollet) */
class LivePlayer {
  constructor(video, cam, onFail) { this.video = video; this.cam = cam; this.onFail = onFail; this.queue = []; this.dead = false; }
  static supported() { return !!(window.ManagedMediaSource || window.MediaSource); }
  codecs() {
    const MS = window.ManagedMediaSource || window.MediaSource;
    return ['avc1.640029', 'avc1.64002A', 'avc1.640033', 'hvc1.1.6.L153.B0', 'mp4a.40.2', 'mp4a.40.5', 'flac', 'opus']
      .filter(c => MS.isTypeSupported(`video/mp4; codecs="${c}"`)).join();
  }
  start() {
    const MS = window.ManagedMediaSource || window.MediaSource;
    if (!MS) return this.fail('MSE');
    this.ms = new MS();
    if (window.ManagedMediaSource) { this.video.disableRemotePlayback = true; this.video.srcObject = this.ms; }   // iPhone/iPad
    else this.video.src = URL.createObjectURL(this.ms);
    this.ms.addEventListener('sourceopen', () => {
      const proto = location.protocol === 'https:' ? 'wss' : 'ws';
      this.ws = new WebSocket(`${proto}://${location.host}/api/live/ws?cam=${encodeURIComponent(this.cam)}`);
      this.ws.binaryType = 'arraybuffer';
      this.ws.onopen = () => this.ws.send(JSON.stringify({ type: 'mse', value: this.codecs() }));
      this.ws.onmessage = e => this.onMessage(e.data);
      this.ws.onclose = e => { if (!this.dead) this.fail('ws ' + e.code); };
    }, { once: true });
    this.timer = setTimeout(() => { if (!this.got) this.fail('timeout'); }, 12000);
  }
  onMessage(data) {
    if (typeof data === 'string') {
      let m; try { m = JSON.parse(data); } catch (e) { return; }
      if (m.type === 'mse') {
        try { this.sb = this.ms.addSourceBuffer(m.value); } catch (e) { return this.fail('codec ' + m.value); }
        this.sb.mode = 'segments';
        this.sb.addEventListener('updateend', () => this.pump());
      } else if (m.type === 'error') this.fail(m.value);
      return;
    }
    this.got = true;
    if (this.frozen) return;                 // pausad live: släpp data tills vi går tillbaka till live
    this.queue.push(new Uint8Array(data));
    this.pump();
  }
  pump() {
    const sb = this.sb, v = this.video;
    if (!sb || sb.updating || this.dead || this.frozen) return;
    if (v.buffered.length) {
      const end = v.buffered.end(v.buffered.length - 1), start = v.buffered.start(0);
      if (end - v.currentTime > 3) v.currentTime = end - 0.5;          // håll oss nära "nu"
      if (v.currentTime - start > 30) { try { sb.remove(start, v.currentTime - 10); return; } catch (e) { /* */ } }
    }
    if (!this.queue.length) return;
    const total = this.queue.reduce((n, b) => n + b.length, 0), buf = new Uint8Array(total);
    let o = 0; for (const b of this.queue) { buf.set(b, o); o += b.length; }
    this.queue = [];
    try { sb.appendBuffer(buf); } catch (e) { return this.fail('append'); }
    if (v.paused) v.play().catch(() => { /* kräver tryck */ });
  }
  fail(why) {
    if (this.dead) return;
    this.stop();
    if (this.onFail) this.onFail(why);
  }
  stop() {
    this.dead = true; clearTimeout(this.timer);
    try { if (this.ws) this.ws.close(); } catch (e) { /* */ }
    try { this.video.pause(); this.video.srcObject = null; this.video.removeAttribute('src'); this.video.load(); } catch (e) { /* */ }
  }
}

/* ---------------------------------------------------------------- fliken */
async function renderOverview() {
  main.innerHTML = `<h2>${t('Översikt')}</h2><p class="muted">${t('Laddar…')}</p>`;
  let info;
  try { info = await api('/api/overview'); } catch (e) { main.innerHTML = `<p class="err">${esc(e.message)}</p>`; return; }
  if (S.tab !== 'overview') return;
  const cams = info.cameras.map(c => c.name);
  if (!cams.length) { main.innerHTML = `<h2>${t('Översikt')}</h2><p class="muted">${t('Lägg till en kamera under Inställningar > Kameror först.')}</p>`; return; }
  let layout = '2x2', page = 0;
  try { layout = localStorage.getItem('synoargus.layout') || layout; } catch (e) { /* */ }
  if (!LAYOUTS[layout]) layout = '2x2';
  const canLive = info.live.available && info.live.running !== false && LivePlayer.supported();
  const O = { mode: 'live', T: null, players: [], timers: [], alive: true, recs: [], evs: [], from: 0, to: 0, playing: true, follow: true };
  stoppers.add(() => { O.alive = false; stopTiles(); clearInterval(O.clock); });

  main.innerHTML = `
  <div class="ov">
    <div class="row ov-head"><h2 style="margin:0">${t('Översikt')}</h2>
      <div class="chips" id="ovLayouts">${Object.keys(LAYOUTS).map(k => `<button class="chip ${k === layout ? 'on' : ''}" data-l="${k}" title="${k === '1x1' ? t('1 kamera') : k.replace('x', ' × ')}">${layoutIcon(k)}<span>${k === '1x1' ? t('1 kamera') : k.replace('x', ' × ')}</span></button>`).join('')}</div>
      <div class="row" id="ovPager"></div></div>
    ${canLive ? '' : `<p class="warnbox">⚠ ${esc(t('Livevideo är inte tillgänglig ({e}). Kamerorna visas som bilder varannan sekund.', { e: !LivePlayer.supported() ? 'MSE' : t(info.live.error || 'go2rtc') }))}</p>`}
    <div class="ov-grid" id="ovGrid"></div>
    <div class="ov-bar">
      <div class="ov-ctrl">
        <button class="btn" data-c="prev" title="${t('Föregående händelse')}">&lt;!</button>
        <button class="btn" data-c="-60">−1 min</button><button class="btn" data-c="-10">−10 s</button>
        <button class="btn" data-c="pause" id="ovPause" title="${t('Pausa / spela')}">⏸</button>
        <button class="btn" data-c="+10">+10 s</button><button class="btn" data-c="+60">+1 min</button>
        <button class="btn primary" data-c="live" id="ovLive">LIVE</button>
        <button class="btn" data-c="next" title="${t('Nästa händelse')}">!&gt;</button>
      </div>
      <button type="button" class="ov-time" id="ovTime" title="${t('Välj datum och tid')}">&nbsp;</button>
      <form class="ov-goto" id="ovGoto" hidden><input type="datetime-local" step="1" id="ovGotoIn"><button class="btn primary">${t('Gå till')}</button><button type="button" class="btn" id="ovGotoX">${t('Avbryt')}</button></form>
      <div class="ov-tlwrap"><div class="ov-tl" id="ovTl"><div class="ov-track" id="ovTrack"></div></div><div class="ov-cursor"></div></div>
      <p class="small muted" style="margin:6px 0 0">${t('Tryck på en kamera för helskärm. Dra tidslinjen för att spela upp inspelningar. Tryck på datum och tid för att välja en tidpunkt.')}
        ${S.cfg?.overview?.debug ? `<a href="#" id="ovRaw">${t('Visa rådata för felsökning')}</a>` : ''}</p><pre class="raw" id="ovRawBox" hidden></pre>
    </div>
  </div>`;

  // ---------------------------------------------------------------- rutnät
  const slots = () => LAYOUTS[layout][0] * LAYOUTS[layout][1];
  const pages = () => Math.max(1, Math.ceil(cams.length / slots()));
  function stopTiles() { O.players.forEach(p => p.stop && p.stop()); O.players = []; O.timers.forEach(clearInterval); O.timers = []; }
  const recPlayers = () => O.players.filter(p => p instanceof RecPlayer);
  function drawGrid() {
    stopTiles();
    let [cols, rows] = LAYOUTS[layout];
    if (innerWidth < 600 && cols > rows) [cols, rows] = [rows, cols];     // stående skärm: vänd rutnätet
    page = Math.min(page, pages() - 1);
    const shown = cams.slice(page * slots(), page * slots() + slots());
    const grid = $('#ovGrid');
    grid.style.gridTemplateColumns = `repeat(${cols}, minmax(0, 1fr))`;
    // stor skärm: håll rutnätet så lågt att tidslinjen syns utan att scrolla
    grid.style.maxWidth = innerWidth >= 600 ? `max(360px, calc((100vh - 300px) * ${(16 * cols / (9 * rows)).toFixed(3)}))` : '';
    grid.dataset.rows = rows;
    grid.innerHTML = shown.map(c => `<div class="ov-tile" data-cam="${esc(c)}"><div class="ov-name">${esc(c)}</div>
      <div class="ov-media"><video muted playsinline></video><img alt="" hidden><div class="ov-msg" hidden></div></div></div>`).join('')
      + Array(Math.max(0, slots() - shown.length)).fill('<div class="ov-tile empty"></div>').join('');
    $('#ovPager').innerHTML = pages() > 1 ? `<button class="btn" data-p="-1">‹</button><span class="small">${t('Sida {a} / {b}', { a: page + 1, b: pages() })}</span><button class="btn" data-p="1">›</button>` : '';
    $$('.ov-tile[data-cam]', grid).forEach(tile => startTile(tile, tile.dataset.cam, true));
  }
  function msg(tile, text) { const m = tile.querySelector('.ov-msg'); m.hidden = !text; m.textContent = text || ''; }
  function snapshots(tile, cam) {
    const img = tile.querySelector('img'), video = tile.querySelector('video');
    video.hidden = true; img.hidden = false; msg(tile, '');
    const load = () => { if (O.alive) img.src = `/api/cameras/${encodeURIComponent(cam)}/snapshot?_=${Date.now()}`; };
    load(); O.timers.push(setInterval(load, 2000));
  }
  function startTile(tile, cam, muted) {
    const video = tile.querySelector('video'), img = tile.querySelector('img');
    video.muted = muted; img.hidden = true; video.hidden = false; msg(tile, '');
    if (O.mode === 'live') {
      if (!canLive) return snapshots(tile, cam);
      const p = new LivePlayer(video, cam, () => { if (O.alive && O.mode === 'live') snapshots(tile, cam); });
      O.players.push(p); p.start();
    } else { const p = new RecPlayer(tile, cam, O); O.players.push(p); p.play(O.T); }
  }

  // ---------------------------------------------------------------- tid och kontroller
  const now = () => Date.now() / 1000;
  const fmt = ts => {
    const d = new Date(ts * 1000), loc = S.lang === 'en' ? 'en-GB' : 'sv-SE';
    return d.toLocaleDateString(loc, { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' }) + ' · ' + d.toLocaleTimeString(loc);
  };
  function current() {
    if (O.mode === 'live') return O.frozenAt || now();
    const v = $$('.ov-tile video').find(x => !x.hidden && x.dataset.t0 && x.readyState > 0);
    if (v) return Number(v.dataset.t0) + v.currentTime;
    const p = recPlayers().find(x => x.T); return p ? p.T : O.T;
  }
  function seek(T, keepPlaying = true) {
    if (!O.alive || !$('#ovLive')) return;
    if (T >= now() - 5) return goLive();
    O.mode = 'rec'; O.T = Math.round(T); O.playing = keepPlaying; O.follow = false; O.frozenAt = null;
    $('#ovLive').classList.remove('primary'); $('#ovPause').textContent = O.playing ? '⏸' : '▶';
    stopTiles();
    $$('.ov-tile[data-cam]', main).forEach(tile => startTile(tile, tile.dataset.cam, true));
    scrollTo(O.T);
  }
  function goLive() {
    if (!O.alive || !$('#ovLive')) return;
    O.mode = 'live'; O.T = null; O.follow = true; O.playing = true; O.frozenAt = null;
    $('#ovLive').classList.add('primary'); $('#ovPause').textContent = '⏸';
    drawGrid(); scrollTo(now());
  }
  $('.ov-ctrl').addEventListener('click', e => {
    const c = e.target.closest('[data-c]')?.dataset.c; if (!c) return;
    if (c === 'live') return goLive();
    if (c === 'prev' || c === 'next') return jumpEvent(c === 'next');
    if (c === 'pause') {
      if (O.mode === 'live') {                              // frys bilden; play går tillbaka till live
        if (O.frozenAt) return goLive();
        O.frozenAt = now(); O.playing = false; $('#ovPause').textContent = '▶';
        O.players.forEach(p => { p.frozen = true; });
        O.timers.forEach(clearInterval); O.timers = [];
        $$('.ov-tile video', main).forEach(v => v.pause());
        return;
      }
      O.playing = !O.playing; $('#ovPause').textContent = O.playing ? '⏸' : '▶';
      recPlayers().forEach(p => { if (O.playing) p.resume(); else p.video.pause(); });
      return;
    }
    seek(current() + Number(c));
  });
  // <! och !>: föregående / nästa larm räknat från där vi är (i live: det senaste)
  function eventTimes() {
    const ts = O.evs.filter(e => e.alarm).map(e => e.ts);
    if (info.last_event) ts.push(info.last_event.ts);
    return [...new Set(ts)].sort((a, b) => a - b);
  }
  function jumpEvent(forward) {
    const pos = current(), list = eventTimes();
    if (forward) {
      if (O.mode === 'live' && !O.frozenAt) return toast(t('Inga fler händelser – visar live'));
      const nx = list.find(ts => ts - OVERVIEW_PRE > pos + 1);
      if (nx === undefined) { toast(t('Inga fler händelser – visar live')); return goLive(); }
      return seek(nx - OVERVIEW_PRE);
    }
    const pv = list.filter(ts => ts - OVERVIEW_PRE < pos - 2).pop();
    if (pv === undefined) return toast(t('Inga händelser'));
    seek(pv - OVERVIEW_PRE);
  }
  $('#ovLayouts').addEventListener('click', e => {
    const b = e.target.closest('[data-l]'); if (!b) return;
    layout = b.dataset.l; try { localStorage.setItem('synoargus.layout', layout); } catch (err) { /* */ }
    $$('#ovLayouts .chip').forEach(x => x.classList.toggle('on', x === b)); page = 0;
    O.mode === 'live' ? drawGrid() : seek(current(), O.playing);
  });
  $('#ovPager').addEventListener('click', e => {
    const d = Number(e.target.dataset.p || 0); if (!d) return;
    page = (page + d + pages()) % pages(); O.mode === 'live' ? drawGrid() : seek(current(), O.playing);
  });
  // tryck på datum och tid: välj en tidpunkt
  const pad = n => String(n).padStart(2, '0');
  const localInput = ts => { const d = new Date(ts * 1000); return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`; };
  $('#ovTime').onclick = () => {
    const f = $('#ovGoto'), inp = $('#ovGotoIn');
    inp.max = localInput(now()); inp.value = localInput(current());
    f.hidden = false; $('#ovTime').hidden = true; inp.focus();
    try { inp.showPicker && inp.showPicker(); } catch (e) { /* inte alla webbläsare */ }
  };
  const closeGoto = () => { $('#ovGoto').hidden = true; $('#ovTime').hidden = false; };
  $('#ovGotoX').onclick = closeGoto;
  $('#ovGoto').onsubmit = async e => {
    e.preventDefault();
    const ts = new Date($('#ovGotoIn').value).getTime() / 1000;
    closeGoto();
    if (!isFinite(ts)) return;
    if (ts >= now() - 5) return goLive();
    while (O.from && ts < O.from + 600 && O.alive) { const before = O.from; await loadEarlier(); if (O.from === before) break; }
    seek(ts);
  };
  if ($('#ovRaw')) $('#ovRaw').onclick = async e => {
    e.preventDefault(); const box = $('#ovRawBox'); box.hidden = !box.hidden; if (box.hidden) return;
    box.textContent = t('Laddar…');
    try { box.textContent = JSON.stringify(await api('/api/overview/raw'), null, 2); } catch (err) { box.textContent = err.message; }
  };

  // ---------------------------------------------------------------- helskärm med ljud
  $('#ovGrid').addEventListener('click', e => {
    const tile = e.target.closest('.ov-tile[data-cam]'); if (!tile) return;
    openFull(tile.dataset.cam);
  });
  function openFull(cam) {
    const T = O.mode === 'rec' ? Math.round(current()) : null;
    stopTiles();
    const ov = document.createElement('div');
    ov.className = 'ov-full';
    ov.innerHTML = `<div class="ov-full-head"><b>${esc(cam)}</b><span class="ov-time" id="ovFullTime"></span>
      <span class="ov-zoombtns"><button class="btn" id="ovZout" title="${t('Zooma ut')}">−</button><button class="btn" id="ovZin" title="${t('Zooma in')}">+</button><button class="btn" id="ovZ0" title="${t('Återställ zoom')}">⟲</button></span>
      <button class="btn" id="ovSound">🔊 <span>${t('Ljud')}</span></button><button class="btn" id="ovClose">✕ <span>${t('Stäng')}</span></button></div>
      <div class="ov-tile" data-cam="${esc(cam)}"><div class="ov-media"><div class="ov-zoom"><video playsinline></video><img alt="" hidden></div><div class="ov-msg" hidden></div></div></div>`;
    document.body.appendChild(ov);
    const tile = ov.querySelector('.ov-tile'), video = tile.querySelector('video');
    const zoom = new Zoom(tile.querySelector('.ov-media'), tile.querySelector('.ov-zoom'));
    $('#ovZin').onclick = () => zoom.step(1.5); $('#ovZout').onclick = () => zoom.step(1 / 1.5); $('#ovZ0').onclick = () => zoom.reset();
    const sound = S.cfg?.overview?.sound !== false;
    if (T) { O.T = T; const p = new RecPlayer(tile, cam, O); O.players.push(p); p.play(T); } else startTile(tile, cam, !sound);
    video.muted = !sound;            // trycket på kameran räknas som tillåtelse att spela ljud
    const sb = ov.querySelector('#ovSound');
    video.play().catch(() => { if (!ov.isConnected) return; video.muted = true; sb.classList.remove('primary'); video.play().catch(() => {}); });
    sb.onclick = () => { video.muted = !video.muted; sb.classList.toggle('primary', !video.muted); if (!video.muted) video.play().catch(() => {}); };
    sb.classList.toggle('primary', !video.muted);
    const close = () => {
      stopTiles(); try { video.pause(); video.removeAttribute('src'); video.load(); } catch (err) { /* */ }
      if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
      ov.remove(); document.removeEventListener('keydown', esc_);
      if (O.alive) O.mode === 'live' ? drawGrid() : seek(T || current(), O.playing);
    };
    const esc_ = e => { if (e.key === 'Escape') close(); };
    document.addEventListener('keydown', esc_);
    $('#ovClose').onclick = close;
    stoppers.add(() => { if (ov.isConnected) ov.remove(); });
    if (ov.requestFullscreen) ov.requestFullscreen().catch(() => { /* fungerar inte överallt */ });
  }

  // ---------------------------------------------------------------- tidslinje
  const tl = $('#ovTl'), track = $('#ovTrack');
  const xOf = ts => (ts - O.from) / 60 * PX_PER_MIN;
  const tOf = x => O.from + x / PX_PER_MIN * 60;
  function scrollTo(ts) { tl.scrollLeft = Math.max(0, xOf(ts) - tl.clientWidth / 2); }
  async function loadTimeline(from, to) {
    try {
      const d = await api(`/api/overview/timeline?start=${from}&end=${to}`);
      if (d.error) toast(t('Kunde inte läsa inspelningar: {e}', { e: d.error }), true);
      return d;
    } catch (e) { toast(t('Kunde inte läsa inspelningar: {e}', { e: e.message }), true); return { recordings: [], events: [] }; }
  }
  function drawTrack() {
    O.to = now() + 600;
    track.style.width = (xOf(now()) + tl.clientWidth / 2) + 'px';     // "nu" ska kunna hamna under markören
    // sammanslagna block (alla kameror) + händelser
    const merged = [];
    for (const r of O.recs.slice().sort((a, b) => a.start - b.start)) {
      const last = merged[merged.length - 1];
      if (last && r.start <= last.stop + 5) last.stop = Math.max(last.stop, r.stop); else merged.push({ start: r.start, stop: r.stop });
    }
    const hours = [];
    for (let h = Math.ceil(O.from / 1800) * 1800; h < O.to; h += 1800) hours.push(h);
    track.innerHTML = hours.map(h => `<div class="ov-tick" style="left:${xOf(h)}px"><span>${new Date(h * 1000).toLocaleTimeString(S.lang === 'en' ? 'en-GB' : 'sv-SE', { hour: '2-digit', minute: '2-digit' })}</span></div>`).join('')
      + merged.map(r => `<div class="ov-rec" style="left:${xOf(r.start)}px;width:${Math.max(2, xOf(r.stop) - xOf(r.start))}px"></div>`).join('')
      + O.evs.filter(e => e.alarm).map(e => `<div class="ov-ev" style="left:${xOf(e.ts)}px" title="${esc(e.camera)}"></div>`).join('');
  }
  async function initTimeline() {
    O.from = Math.floor((now() - 24 * 3600) / 1800) * 1800;
    const d = await loadTimeline(O.from, now());
    if (!O.alive) return;
    O.recs = d.recordings || []; O.evs = d.events || [];
    drawTrack(); scrollTo(now());
  }
  async function loadEarlier() {
    if (O.loading) return; O.loading = true;
    const old = O.from, newFrom = old - 24 * 3600, keep = tl.scrollLeft;
    const d = await loadTimeline(newFrom, old);
    O.from = newFrom; O.recs = [...(d.recordings || []), ...O.recs]; O.evs = [...(d.events || []), ...O.evs];
    drawTrack(); tl.scrollLeft = keep + xOf(old); O.loading = false;
  }
  let scrollTimer = null, userScroll = false;
  tl.addEventListener('pointerdown', () => { userScroll = true; });
  tl.addEventListener('wheel', () => { userScroll = true; }, { passive: true });
  tl.addEventListener('touchstart', () => { userScroll = true; }, { passive: true });
  tl.addEventListener('scroll', () => {
    if (tl.scrollLeft < 200 && !O.loading && O.from) loadEarlier();
    const ts = tOf(tl.scrollLeft + tl.clientWidth / 2);
    $('#ovTime').textContent = fmt(ts);
    if (!userScroll) return;
    clearTimeout(scrollTimer);
    scrollTimer = setTimeout(() => { userScroll = false; if (O.alive) seek(tOf(tl.scrollLeft + tl.clientWidth / 2)); }, 500);
  });

  // ---------------------------------------------------------------- klocka
  O.clock = setInterval(() => {
    if (!O.alive) return;
    const ts = current();
    if (!userScroll) { $('#ovTime').textContent = fmt(ts); if (O.mode === 'live' || O.playing) scrollTo(ts); }
    const ft = document.getElementById('ovFullTime'); if (ft) ft.textContent = fmt(ts);
    O.tick = (O.tick || 0) + 1;
    if (O.tick % 60 === 0 && O.from) {
      api('/api/overview').then(d => { info.last_event = d.last_event; }).catch(() => {});
      loadTimeline(now() - 1800, now()).then(d => {
        if (!O.alive) return;
        const key = r => r.camera + '|' + r.start;
        const fresh = d.recordings || [], fk = new Set(fresh.map(key));
        O.recs = O.recs.filter(r => !fk.has(key(r))).concat(fresh);
        O.evs = O.evs.concat((d.events || []).filter(e => !O.evs.some(x => x.id === e.id)));
        drawTrack();
      });
    }
  }, 1000);

  drawGrid();
  initTimeline();
}
const OVERVIEW_PRE = 3;

function layoutIcon(k) {
  const [c, r] = LAYOUTS[k];
  let cells = '';
  for (let y = 0; y < r; y++) for (let x = 0; x < c; x++) cells += `<rect x="${1 + x * (22 / c)}" y="${1 + y * (16 / r)}" width="${22 / c - 2}" height="${16 / r - 2}" rx="1"/>`;
  return `<svg viewBox="0 0 24 18" width="22" height="16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.6">${cells}</svg>`;
}
