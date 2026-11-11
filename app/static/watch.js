/* SynoArgus – fliken Bevakning (Inställningar > Bevakning). Laddas efter app.js. */
'use strict';

Object.assign(EN, {
  'Bevakning': 'Watch', 'experimentell': 'experimental',
  'Bevakningen håller koll på en zon i bilden och säger till när något avviker: någon kommer fram, rörelsen i zonen upphör, någon lämnar zonen eller någon annan kommer in i bild. Den bygger på rörelse, inte på AI, och fungerar därför även i mörker och på långt håll. Starta den för hand eller med en webhook.': 'The watch keeps an eye on a zone in the picture and tells you when something deviates: someone arrives, the motion in the zone stops, someone leaves the zone or someone else enters the picture. It is based on motion, not AI, so it also works in the dark and at a distance. Start it by hand or with a webhook.',
  'Lägg till en kamera under Inställningar > Kameror först.': 'Add a camera under Settings > Cameras first.',
  'Starta bevakning': 'Start watch', 'Starta – zonen är redan upptagen': 'Start – the zone is already occupied', 'Stoppa bevakning': 'Stop watch',
  'Pågår sedan {t} ({m} min)': 'Running since {t} ({m} min)', 'Inte igång': 'Not running',
  'Testläge: händelser loggas här men inget skickas': 'Test mode: events are logged here but nothing is sent',
  'Zonen: {o} · {a}': 'The zone: {o} · {a}', 'upptagen': 'occupied', 'tom': 'empty', 'rörelse': 'motion', 'stilla': 'quiet',
  '{f} bilder/s · {ms} ms per bild · hämtning {s} ms': '{f} images/s · {ms} ms per image · fetch {s} ms',
  'Kan inte hämta bilder: {e}': 'Cannot fetch images: {e}',
  'En bevakning pågår redan på {cam}. Stoppa den först.': 'A watch is already running on {cam}. Stop it first.',
  'En kalibrering pågår på {cam}. Bevakning och kalibrering kan inte köras samtidigt.': 'A calibration is running on {cam}. Watch and calibration cannot run at the same time.',
  'Spara bevakningen innan du startar den.': 'Save the watch before starting it.',
  'Senaste händelser': 'Latest events', 'Inga händelser ännu.': 'No events yet.', 'test': 'test', 'ignorerad': 'ignored',
  'Zon': 'Zone', 'Tryck Hämta bild och dra en ruta runt det som ska bevakas. Ta med lite marginal. En ny ruta ersätter den gamla.': 'Press Get image and drag a box around what should be watched. Leave a little margin. A new box replaces the old one.',
  'Ingen zon ritad ännu.': 'No zone drawn yet.', 'Zon: {w} × {h} % av bilden': 'Zone: {w} × {h} % of the picture',
  'Bilder per sekund': 'Images per second', 'Stoppa automatiskt efter (min, 0 = aldrig)': 'Stop automatically after (min, 0 = never)',
  'Testläge (logga bara, skicka inget)': 'Test mode (only log, send nothing)',
  'Räkna inte rörelse i kamerans uteslutningszoner': 'Do not count motion in the camera\'s exclusion zones',
  'Vad ska ge en händelse?': 'What should give an event?',
  'Ankomst till zonen': 'Arrival at the zone', 'Någon rör sig fram till zonen och stannar där, eller zonen blir aktiv.': 'Someone moves up to the zone and stops there, or the zone becomes active.',
  'Aktivitet upphör': 'Activity stops', 'Zonen är stilla utan att någon har lämnat den.': 'The zone is quiet although nobody has left it.',
  'Aktivitet återupptas': 'Activity resumes', 'Rörelse i zonen igen efter att den varit stilla.': 'Motion in the zone again after it has been quiet.',
  'Lämnar zonen, mot kameran': 'Leaves the zone, towards the camera', 'Någon går från zonen och kommer närmare (nedåt i bilden eller växer).': 'Someone walks away from the zone and comes closer (down in the picture or growing).',
  'Lämnar zonen, åt annat håll': 'Leaves the zone, in another direction', 'Någon går från zonen åt något annat håll.': 'Someone walks away from the zone in some other direction.',
  'Någon kommer in i bild': 'Someone enters the picture', 'Rörelse som inte började vid zonen, t.ex. någon som går förbi.': 'Motion that did not start at the zone, e.g. someone walking past.',
  'Dröjer kvar': 'Lingers', 'Den som kom in i bild stannar vid zonen eller blir kvar i bilden.': 'Whoever entered the picture stops at the zone or stays in the picture.',
  'Bevakningen har pågått länge': 'The watch has been running for a long time', 'Påminnelse om att bevakningen fortfarande är igång.': 'A reminder that the watch is still running.',
  'efter (s)': 'after (s)', 'minst (s)': 'at least (s)', 'stannat i (s)': 'stopped for (s)', 'kvar i bild i (s)': 'in the picture for (s)', 'efter (min)': 'after (min)',
  'Ignorera fordon (när AI:n känner igen dem)': 'Ignore vehicles (when the AI recognises them)', 'Bara när zonen är upptagen': 'Only when the zone is occupied',
  'Tyst efter händelsen (s)': 'Quiet after the event (s)', 'Egen text (tom = standardtexten)': 'Own text (empty = the default text)',
  'Skicka till (inga valda = alla notifieringar som gäller kameran)': 'Send to (none selected = all notifications that apply to the camera)',
  'Stoppa bevakningen när detta händer': 'Stop the watch when this happens',
  'Starta och stoppa med webhook': 'Start and stop with a webhook',
  'Anropa adressen från t.ex. Homey. Lägg till &occupied=1 på startadressen om zonen redan är upptagen när bevakningen startar.': 'Call the address from e.g. Homey. Add &occupied=1 to the start address if the zone is already occupied when the watch starts.',
  'Starta': 'Start', 'Stoppa': 'Stop', 'Ta bort bevakningen': 'Remove the watch', 'Ta bort bevakningen för {cam}?': 'Remove the watch for {cam}?',
  'I notifieringar kan du använda %händelse% (texten) och %händelse_id% (t.ex. leave_toward).': 'In notifications you can use %event% (the text) and %event_id% (e.g. leave_toward).',
  'Rita en zon först.': 'Draw a zone first.', 'Bevakning pågår': 'Watch running',
});

const WATCH_EVENTS = [
  ['arrive', 'Ankomst till zonen', 'Någon rör sig fram till zonen och stannar där, eller zonen blir aktiv.', []],
  ['quiet', 'Aktivitet upphör', 'Zonen är stilla utan att någon har lämnat den.', [['seconds', 'efter (s)', 5, 3600]]],
  ['resume', 'Aktivitet återupptas', 'Rörelse i zonen igen efter att den varit stilla.', []],
  ['leave_toward', 'Lämnar zonen, mot kameran', 'Någon går från zonen och kommer närmare (nedåt i bilden eller växer).', []],
  ['leave_other', 'Lämnar zonen, åt annat håll', 'Någon går från zonen åt något annat håll.', []],
  ['enter', 'Någon kommer in i bild', 'Rörelse som inte började vid zonen, t.ex. någon som går förbi.', [['seconds', 'minst (s)', 1, 60]]],
  ['linger', 'Dröjer kvar', 'Den som kom in i bild stannar vid zonen eller blir kvar i bilden.', [['seconds', 'stannat i (s)', 3, 600], ['stay_seconds', 'kvar i bild i (s)', 10, 3600]]],
  ['timeout', 'Bevakningen har pågått länge', 'Påminnelse om att bevakningen fortfarande är igång.', [['minutes', 'efter (min)', 1, 1440]]],
];

async function renderWatch() {
  const cams = Object.keys(S.cfg.cameras || {});
  if (!cams.length) { main.innerHTML = `<h2>${t('Bevakning')}</h2><p class="muted">${t('Lägg till en kamera under Inställningar > Kameror först.')}</p>`; return; }
  if (!cams.includes(S.wcam)) S.wcam = cams[0];
  main.innerHTML = `<h2>${t('Bevakning')} <span class="tag">${t('experimentell')}</span></h2><p class="muted">${t('Laddar…')}</p>`;
  let data;
  try { data = await api('/api/watches'); } catch (e) { main.innerHTML = `<p class="err">${esc(e.message)}</p>`; return; }
  if (S.tab !== 'settings' || S.sub !== 'watch') return;
  const cam = S.wcam, enc = encodeURIComponent(cam);
  const saved = data.watches[cam];
  const Wt = JSON.parse(JSON.stringify(saved || data.defaults));
  let status = data.status, calibrating = data.calibration, timer = null, alive = true;
  stoppers.add(() => { alive = false; clearTimeout(timer); window.onresize = null; });
  const notis = S.cfg.notifiers || [];

  const evHtml = ([key, title, desc, params]) => {
    const e = Wt.events[key];
    return `<div class="wev" data-ev="${key}">
      <label class="check"><input type="checkbox" data-f="on" ${e.on ? 'checked' : ''}> <b>${t(title)}</b></label>
      <div class="muted small">${t(desc)}</div>
      <div class="wev-body" ${e.on ? '' : 'hidden'}>
        <div class="grid">
          ${params.map(([f, label, lo, hi]) => `<label class="f">${t(label)}<input type="number" data-f="${f}" min="${lo}" max="${hi}" value="${e[f]}"></label>`).join('')}
          <label class="f">${t('Tyst efter händelsen (s)')}<input type="number" data-f="cooldown" min="0" max="3600" value="${e.cooldown || 0}"></label>
          <label class="f" style="grid-column:1/-1">${t('Egen text (tom = standardtexten)')}<input data-f="text" maxlength="300" value="${esc(e.text || '')}" placeholder="${esc(t(title))}"></label>
        </div>
        ${key === 'enter' ? `<label class="check"><input type="checkbox" data-f="only_occupied" ${e.only_occupied ? 'checked' : ''}> ${t('Bara när zonen är upptagen')}</label>
          <label class="check"><input type="checkbox" data-f="ignore_vehicles" ${e.ignore_vehicles ? 'checked' : ''}> ${t('Ignorera fordon (när AI:n känner igen dem)')}</label>` : ''}
        ${key !== 'timeout' ? `<label class="check"><input type="checkbox" data-stop ${Wt.stop_on.includes(key) ? 'checked' : ''}> ${t('Stoppa bevakningen när detta händer')}</label>` : ''}
        ${notis.length ? `<div class="muted small" style="margin-top:6px">${t('Skicka till (inga valda = alla notifieringar som gäller kameran)')}</div>
          <div class="chips">${notis.map(n => `<button type="button" class="chip ${e.notifiers.includes(n.id) ? 'on' : ''}" data-n="${esc(n.id)}">${esc(n.name || n.type)}</button>`).join('')}</div>` : ''}
      </div></div>`;
  };
  const url = a => `${data.base}/api/watch?token=${data.token}&camera=${enc}&action=${a}`;

  main.innerHTML = `
  <h2>${t('Bevakning')} <span class="tag">${t('experimentell')}</span></h2>
  <p class="muted" style="max-width:820px">${t('Bevakningen håller koll på en zon i bilden och säger till när något avviker: någon kommer fram, rörelsen i zonen upphör, någon lämnar zonen eller någon annan kommer in i bild. Den bygger på rörelse, inte på AI, och fungerar därför även i mörker och på långt håll. Starta den för hand eller med en webhook.')}</p>
  <div class="chips camlist">${cams.map(c => `<button class="chip ${c === cam ? 'on' : ''}" data-cam="${esc(c)}">${esc(c)}${status.active === c ? ' ●' : ''}</button>`).join('')}</div>
  <div class="panel" id="wStatus"></div>
  <div class="panel">
    <div class="row" style="justify-content:space-between"><h3>${t('Zon')}</h3><button class="btn" id="wSnap">${t('Hämta bild')}</button></div>
    <p class="muted small" style="margin-top:0">${t('Tryck Hämta bild och dra en ruta runt det som ska bevakas. Ta med lite marginal. En ny ruta ersätter den gamla.')}</p>
    <div class="zonebox" id="wBox" hidden><img id="wImg" alt=""><canvas id="wCanvas"></canvas></div>
    <div class="small" id="wZoneInfo"></div>
    <div class="grid" style="margin-top:12px">
      <label class="f">${t('Bilder per sekund')}<select id="wFps">${[2, 3, 4].map(f => `<option ${Wt.fps === f ? 'selected' : ''}>${f}</option>`).join('')}</select></label>
      <label class="f">${t('Stoppa automatiskt efter (min, 0 = aldrig)')}<input type="number" id="wAuto" min="0" max="1440" value="${Wt.auto_stop_min}"></label>
    </div>
    <label class="check"><input type="checkbox" id="wTest" ${Wt.test ? 'checked' : ''}> ${t('Testläge (logga bara, skicka inget)')}</label>
    <label class="check"><input type="checkbox" id="wExcl" ${Wt.use_exclusion_zones ? 'checked' : ''}> ${t('Räkna inte rörelse i kamerans uteslutningszoner')}</label>
  </div>
  <div class="panel"><h3>${t('Vad ska ge en händelse?')}</h3>
    <div id="wEvents">${WATCH_EVENTS.map(evHtml).join('')}</div>
    <p class="hint-box" style="margin:10px 0 0">${t('I notifieringar kan du använda %händelse% (texten) och %händelse_id% (t.ex. leave_toward).')}</p>
  </div>
  <div class="panel"><h3>${t('Starta och stoppa med webhook')}</h3>
    <p class="muted small" style="margin-top:0">${t('Anropa adressen från t.ex. Homey. Lägg till &occupied=1 på startadressen om zonen redan är upptagen när bevakningen startar.')}</p>
    <div class="small"><b>${t('Starta')}</b></div>${copyRow('wUrlStart', url('start'))}
    <div class="small" style="margin-top:6px"><b>${t('Stoppa')}</b></div>${copyRow('wUrlStop', url('stop'))}
    <div class="small" style="margin-top:6px"><b>Status</b></div>${copyRow('wUrlStatus', url('status'))}
  </div>
  <div class="row"><button class="btn primary" id="wSave">${t('Spara')}</button>
    ${saved ? `<button class="btn danger" id="wDel">${t('Ta bort bevakningen')}</button>` : ''}</div>`;

  $$('.camlist .chip').forEach(b => b.onclick = () => { if (b.dataset.cam === S.wcam || !confirmLeave()) return; S.wcam = b.dataset.cam; render(); });

  // ---- samla in och osparat
  const clampNum = (el) => { const v = Number(el.value); return Number.isFinite(v) ? v : 0; };
  const collect = () => {
    Wt.fps = Number($('#wFps').value); Wt.auto_stop_min = clampNum($('#wAuto')); Wt.test = $('#wTest').checked; Wt.use_exclusion_zones = $('#wExcl').checked;
    Wt.stop_on = [];
    $$('#wEvents .wev').forEach(box => {
      const e = Wt.events[box.dataset.ev];
      box.querySelectorAll('[data-f]').forEach(el => { e[el.dataset.f] = el.type === 'checkbox' ? el.checked : el.type === 'number' ? clampNum(el) : el.value; });
      const st = box.querySelector('[data-stop]'); if (st && st.checked) Wt.stop_on.push(box.dataset.ev);
    });
    return Wt;
  };
  let snap = JSON.stringify(collect());
  S.dirty = () => !!$('#wSave') && JSON.stringify(collect()) !== snap;
  $('#wEvents').addEventListener('change', e => {
    const box = e.target.closest('.wev'); if (box && e.target.dataset.f === 'on') box.querySelector('.wev-body').hidden = !e.target.checked;
  });
  $('#wEvents').addEventListener('click', e => {
    const id = e.target.dataset.n; if (!id) return;
    const ev = Wt.events[e.target.closest('.wev').dataset.ev];
    ev.notifiers = ev.notifiers.includes(id) ? ev.notifiers.filter(x => x !== id) : [...ev.notifiers, id];
    e.target.classList.toggle('on');
  });

  // ---- zon
  const canvas = $('#wCanvas'), img = $('#wImg');
  const zoneInfo = () => {
    const z = Wt.zone;
    $('#wZoneInfo').innerHTML = z ? esc(t('Zon: {w} × {h} % av bilden', { w: Math.round((z.x2 - z.x1) * 100), h: Math.round((z.y2 - z.y1) * 100) })) : `<span class="muted">${t('Ingen zon ritad ännu.')}</span>`;
  };
  const draw = temp => {
    if ($('#wBox').hidden) return;
    canvas.width = img.clientWidth; canvas.height = img.clientHeight;
    const g = canvas.getContext('2d'), Wd = canvas.width, Hd = canvas.height;
    g.clearRect(0, 0, Wd, Hd);
    if ($('#wExcl').checked) (S.cfg.cameras[cam].zones || []).forEach(z => { g.fillStyle = 'rgba(120,120,120,.35)'; g.fillRect(z.x1 * Wd, z.y1 * Hd, (z.x2 - z.x1) * Wd, (z.y2 - z.y1) * Hd); });
    const z = temp || Wt.zone; if (!z) return;
    const x = Math.min(z.x1, z.x2) * Wd, y = Math.min(z.y1, z.y2) * Hd, w = Math.abs(z.x2 - z.x1) * Wd, h = Math.abs(z.y2 - z.y1) * Hd;
    g.fillStyle = 'rgba(64,156,255,.2)'; g.fillRect(x, y, w, h); g.strokeStyle = '#409cff'; g.lineWidth = 2; g.strokeRect(x, y, w, h);
  };
  let start = null;
  const pos = e => { const r = canvas.getBoundingClientRect(); return { x: Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)), y: Math.min(1, Math.max(0, (e.clientY - r.top) / r.height)) }; };
  canvas.addEventListener('pointerdown', e => { start = pos(e); canvas.setPointerCapture(e.pointerId); });
  canvas.addEventListener('pointermove', e => { if (start) { const p = pos(e); draw({ x1: start.x, y1: start.y, x2: p.x, y2: p.y }); } });
  canvas.addEventListener('pointerup', e => {
    if (!start) return; const p = pos(e);
    const z = { x1: +Math.min(start.x, p.x).toFixed(4), y1: +Math.min(start.y, p.y).toFixed(4), x2: +Math.max(start.x, p.x).toFixed(4), y2: +Math.max(start.y, p.y).toFixed(4) };
    start = null;
    if (z.x2 - z.x1 >= 0.02 && z.y2 - z.y1 >= 0.02) Wt.zone = z;
    draw(); zoneInfo();
  });
  window.onresize = () => draw();
  $('#wExcl').onchange = () => draw();
  const loadSnap = async () => {
    $('#wSnap').disabled = true;
    try {
      const r = await fetch(`/api/cameras/${enc}/snapshot?_=${Date.now()}`);
      if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
      const u = URL.createObjectURL(await r.blob());
      img.onload = () => { $('#wBox').hidden = false; draw(); };
      img.src = u;
    } catch (e) { toast(e.message, true); }
    $('#wSnap').disabled = false;
  };
  $('#wSnap').onclick = loadSnap;
  zoneInfo();
  if (Wt.zone) loadSnap();

  // ---- status och logg
  const hhmm = ts => new Date(ts * 1000).toLocaleTimeString(S.lang === 'en' ? 'en-GB' : 'sv-SE');
  const drawStatus = () => {
    const box = $('#wStatus'); if (!box) return;
    const mine = status.active === cam, other = status.active && !mine ? status.active : null;
    let head;
    if (mine) {
      const st = status.state;
      head = `<div class="row"><span class="tag ok">● ${esc(t('Pågår sedan {t} ({m} min)', { t: hhmm(status.since), m: Math.floor(status.elapsed / 60) }))}</span>
          <button class="btn danger" data-w="stop">${t('Stoppa bevakning')}</button></div>
        ${status.test ? `<p class="warnbox">${t('Testläge: händelser loggas här men inget skickas')}</p>` : ''}
        ${status.error ? `<p class="warnbox">⚠ ${esc(t('Kan inte hämta bilder: {e}', { e: status.error }))}</p>` : ''}
        ${st ? `<p class="small" style="margin:8px 0 0">${esc(t('Zonen: {o} · {a}', { o: st.occupied ? t('upptagen') : t('tom'), a: st.zone_active ? t('rörelse') : t('stilla') }))}
          <span class="muted"> · ${esc(t('{f} bilder/s · {ms} ms per bild · hämtning {s} ms', { f: status.fps, ms: status.ms, s: status.snapshot_ms }))}</span></p>` : ''}`;
    } else {
      const block = other ? t('En bevakning pågår redan på {cam}. Stoppa den först.', { cam: other })
        : calibrating ? t('En kalibrering pågår på {cam}. Bevakning och kalibrering kan inte köras samtidigt.', { cam: calibrating }) : '';
      head = `<div class="row"><span class="tag">${t('Inte igång')}</span>
          <button class="btn primary" data-w="start" ${block ? 'disabled' : ''}>▶ ${t('Starta bevakning')}</button>
          <button class="btn" data-w="start-occ" ${block ? 'disabled' : ''}>${t('Starta – zonen är redan upptagen')}</button></div>
        ${block ? `<p class="warnbox">⚠ ${esc(block)}</p>` : ''}`;
    }
    const log = (status.log || []).filter(l => l.camera === cam).slice(0, 15);
    box.innerHTML = `${head}
      <h3 style="margin-top:14px">${t('Senaste händelser')}</h3>
      <div class="wlog">${log.map(l => `<div class="small"><span class="muted">${hhmm(l.ts)}</span> ${esc(l.text)}
        ${l.test ? `<span class="tag">${t('test')}</span>` : ''}${l.ignored ? `<span class="tag">${t('ignorerad')}</span>` : ''}
        ${(l.sent || []).map(s => `<span class="tag ${s.ok ? 'ok' : 'err'}" title="${esc(s.error || '')}">${s.ok ? '✓' : '✗'} ${esc(s.name)}</span>`).join(' ')}</div>`).join('') || `<span class="muted small">${t('Inga händelser ännu.')}</span>`}</div>`;
    $$('.camlist .chip').forEach(b => { b.textContent = b.dataset.cam + (status.active === b.dataset.cam ? ' ●' : ''); });
    setWatchPill(status.active);
  };
  const poll = async () => {
    if (!alive) return;
    try { status = await api('/api/watches/status'); drawStatus(); } catch (e) { /* nästa gång */ }
    timer = setTimeout(poll, status.active ? 2000 : 10000);
  };
  $('#wStatus').addEventListener('click', async e => {
    const a = e.target.dataset.w; if (!a) return;
    if (a !== 'stop' && ((S.dirty && S.dirty()) || !saved)) { toast(t(Wt.zone ? 'Spara bevakningen innan du startar den.' : 'Rita en zon först.'), true); return; }
    e.target.disabled = true;
    try { status = await api(`/api/watches/${enc}/action`, { method: 'POST', body: { action: a === 'stop' ? 'stop' : 'start', occupied: a === 'start-occ' } }); }
    catch (err) { toast(err.message, true); }
    drawStatus(); clearTimeout(timer); timer = setTimeout(poll, 1500);
  });
  drawStatus();
  timer = setTimeout(poll, status.active ? 2000 : 10000);

  // ---- spara och ta bort
  $('#wSave').onclick = async () => {
    const body = collect();
    if (!body.zone) { toast(t('Rita en zon först.'), true); return; }
    try { await api(`/api/watches/${enc}`, { method: 'PUT', body }); S.dirty = null; toast(t('Sparat')); render(); }
    catch (e) { toast(e.message, true); }
  };
  if ($('#wDel')) $('#wDel').onclick = async () => {
    if (!confirm(t('Ta bort bevakningen för {cam}?', { cam }))) return;
    S.dirty = null;
    try { await api(`/api/watches/${enc}`, { method: 'DELETE' }); render(); } catch (e) { toast(e.message, true); }
  };
}

function setWatchPill(cam) {
  const pill = $('#watchPill'); if (!pill) return;
  if (S.state) S.state.watch = cam || null;     // etiketten leder till den kamera som bevakas
  pill.hidden = !(S.state && S.state.logged_in && cam);
  if (cam) { pill.innerHTML = `👁<span class="n"> ${esc(cam)}</span>`; pill.title = t('Bevakning pågår') + ': ' + cam; }
}
