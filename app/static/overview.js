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
});

const LAYOUTS = { '1x2': [2, 1], '1x3': [3, 1], '2x2': [2, 2], '2x3': [3, 2] };   // rader × kolumner -> [kolumner, rader]
const PX_PER_MIN = 8;          // tidslinjens skala
const REC_CHUNK = 300;         // sekunder per inspelningsbit

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
      <div class="chips" id="ovLayouts">${Object.keys(LAYOUTS).map(k => `<button class="chip ${k === layout ? 'on' : ''}" data-l="${k}" title="${k.replace('x', ' × ')}">${layoutIcon(k)}<span>${k.replace('x', ' × ')}</span></button>`).join('')}</div>
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
      <div class="ov-time" id="ovTime">&nbsp;</div>
      <div class="ov-tlwrap"><div class="ov-tl" id="ovTl"><div class="ov-track" id="ovTrack"></div></div><div class="ov-cursor"></div></div>
      <p class="small muted" style="margin:6px 0 0">${t('Tryck på en kamera för helskärm med ljud. Dra tidslinjen för att spela upp inspelningar.')}
        <a href="#" id="ovRaw">${t('Visa rådata för felsökning')}</a></p><pre class="raw" id="ovRawBox" hidden></pre>
    </div>
  </div>`;

  // ---------------------------------------------------------------- rutnät
  const slots = () => LAYOUTS[layout][0] * LAYOUTS[layout][1];
  const pages = () => Math.max(1, Math.ceil(cams.length / slots()));
  function stopTiles() { O.players.forEach(p => p.stop && p.stop()); O.players = []; O.timers.forEach(clearInterval); O.timers = []; }
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
    } else playRecording(tile, cam, O.T);
  }
  async function playRecording(tile, cam, T) {
    const video = tile.querySelector('video'), enc = encodeURIComponent(cam);
    try {
      const r = await api(`/api/overview/recording?cam=${enc}&t=${T}&check=1`);
      if (!O.alive || O.T !== T) return;
      if (!r.found) { video.hidden = true; msg(tile, r.detail || t('Ingen inspelning')); return; }
    } catch (e) { msg(tile, e.message); return; }
    video.hidden = false; msg(tile, '');
    video.src = `/api/overview/recording?cam=${enc}&t=${T}&length=${REC_CHUNK}`;
    video.dataset.t0 = T;
    video.onended = () => { if (O.mode === 'rec' && O.T === T) { /* nästa bit */ playRecording(tile, cam, T + REC_CHUNK); } };
    if (O.playing) video.play().catch(() => { /* */ });
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
    return v ? Number(v.dataset.t0) + v.currentTime : O.T;
  }
  function seek(T, keepPlaying = true) {
    if (T >= now() - 5) return goLive();
    O.mode = 'rec'; O.T = Math.round(T); O.playing = keepPlaying; O.follow = false; O.frozenAt = null;
    $('#ovLive').classList.remove('primary'); $('#ovPause').textContent = O.playing ? '⏸' : '▶';
    stopTiles();
    $$('.ov-tile[data-cam]', main).forEach(tile => startTile(tile, tile.dataset.cam, true));
    scrollTo(O.T);
  }
  function goLive() {
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
      $$('.ov-tile video', main).forEach(v => { if (O.playing) v.play().catch(() => {}); else v.pause(); });
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
  $('#ovRaw').onclick = async e => {
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
      <button class="btn" id="ovSound">🔊 ${t('Ljud')}</button><button class="btn" id="ovClose">✕ ${t('Stäng')}</button></div>
      <div class="ov-tile" data-cam="${esc(cam)}"><div class="ov-media"><video playsinline controls></video><img alt="" hidden><div class="ov-msg" hidden></div></div></div>`;
    document.body.appendChild(ov);
    const tile = ov.querySelector('.ov-tile'), video = tile.querySelector('video');
    if (T) { O.T = T; playRecording(tile, cam, T); video.muted = false; } else startTile(tile, cam, false);
    video.muted = false;            // trycket på kameran räknas som tillåtelse att spela ljud
    video.play().catch(() => { video.muted = true; video.play().catch(() => {}); });
    $('#ovSound').onclick = () => { video.muted = !video.muted; $('#ovSound').classList.toggle('primary', !video.muted); if (!video.muted) video.play().catch(() => {}); };
    $('#ovSound').classList.toggle('primary', !video.muted);
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
    scrollTimer = setTimeout(() => { userScroll = false; seek(tOf(tl.scrollLeft + tl.clientWidth / 2)); }, 500);
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
