/* SynoArgus webbgränssnitt */
'use strict';

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const sleep = ms => new Promise(r => setTimeout(r, ms));
const main = $('#main');
let S = { state: null, cfg: null, types: null, models: [], triggerBase: '', tab: 'events', cam: null, lang: 'sv', update: null };
const stoppers = new Set();  // livebild, rörelsemätare m.m. som ska stoppas när man byter vy
function stopAll() { stoppers.forEach(f => { try { f(); } catch (e) { /* */ } }); stoppers.clear(); }

/* ---------------------------------------------------------------- språk */
const EN = {
  'Händelser': 'Events', 'Kameror': 'Cameras', 'Notifierare': 'Notifiers', 'Inställningar': 'Settings', 'Status': 'Status',
  'Logga ut': 'Log out', 'Laddar…': 'Loading…', 'Kan inte nå SynoArgus: {e}': 'Cannot reach SynoArgus: {e}',
  'Kopierat': 'Copied', 'Adressen är markerad – tryck Ctrl+C': 'The address is selected – press Ctrl+C', 'Kopiera': 'Copy',
  'Sparat': 'Saved', 'Spara': 'Save', 'Ta bort': 'Remove', 'Aktiv': 'Active', 'Namn': 'Name', 'Lösenord': 'Password',
  'Användarnamn': 'Username', 'Användare': 'User', 'Port': 'Port', 'Metod': 'Method', 'Adress': 'Address', 'Token': 'Token',
  'Ingen': 'None', 'Engångskod': 'One-time code', 'Logga in': 'Log in', 'av': 'off',
  // installation
  'Installation': 'Setup', 'SynoArgus är inte installerat ännu. Öppna sidan från hemnätet för att göra installationen.': 'SynoArgus is not set up yet. Open the page from your local network to run the setup.',
  'Välkommen till SynoArgus': 'Welcome to SynoArgus',
  'Anslut till Surveillance Station. Använd ett eget konto för SynoArgus utan tvåstegsverifiering, med behörighet till Surveillance Station.': 'Connect to Surveillance Station. Use a dedicated account for SynoArgus without 2-step verification, with access to Surveillance Station.',
  'NAS-adress': 'NAS address', 'Användare för Surveillance Station': 'Surveillance Station user', 'Kontrollera HTTPS-certifikat': 'Verify HTTPS certificate',
  'Vem får logga in i SynoArgus?': 'Who may log in to SynoArgus?',
  'Ange ditt eget DSM-konto. Det blir det enda kontot som får logga in (fler kan läggas till under Inställningar > Inloggning). Lämnar du fältet tomt blir tjänstekontot ovan det enda som får logga in.': 'Enter your own DSM account. It becomes the only account allowed to log in (more can be added under Settings > Login). If you leave it empty, the service account above becomes the only one allowed.',
  'Ditt DSM-konto': 'Your DSM account', 'Engångskod (om tvåstegsverifiering)': 'One-time code (if 2-step verification)',
  'Anslut och starta': 'Connect and start', 'Ansluter…': 'Connecting…', 'Klart! {n} kameror hittades.': 'Done! {n} cameras found.', 'Språk': 'Language',
  // inloggning
  'SSO-inloggningen misslyckades.': 'SSO login failed.', 'Kontot har inte behörighet till SynoArgus.': 'This account is not allowed to use SynoArgus.',
  'Inloggningen misslyckades.': 'Login failed.', 'Upplåst läge: alla DSM-konton kan logga in. Ta bort SYNOARGUS_UNLOCK i docker-compose.yml när du är klar.': 'Unlocked mode: all DSM accounts can log in. Remove SYNOARGUS_UNLOCK from docker-compose.yml when done.',
  'Logga in med Synology SSO': 'Log in with Synology SSO', 'eller med DSM-konto': 'or with a DSM account', 'Logga in med ditt DSM-konto.': 'Log in with your DSM account.', 'Ange engångskoden.': 'Enter the one-time code.',
  // händelser
  'Alla kameror': 'All cameras', 'Visa även utan larm': 'Also show without alarm', 'Visa fler': 'Show more',
  'Inga händelser ännu. När Surveillance Station larmar och AI:n hittar något hamnar det här.': 'No events yet. When Surveillance Station triggers and the AI finds something, it shows up here.',
  'Inget av intresse': 'Nothing of interest', 'Stäng': 'Close',
  // kameror
  'Hämta från Surveillance Station': 'Fetch from Surveillance Station', 'Inga kameror. Hämta dem från Surveillance Station.': 'No cameras. Fetch them from Surveillance Station.',
  '{n} kameror lades till': '{n} cameras added', 'Inga nya kameror': 'No new cameras',
  'Adress till Action Rule i Surveillance Station (Webhook, metod GET):': 'Address for the Action Rule in Surveillance Station (Webhook, method GET):',
  'Vad ska larma?': 'What should trigger an alarm?', 'Lägg till annan typ…': 'Add another type…',
  'Säkerhet minst': 'Minimum confidence', 'Standard {v} %': 'Default {v} %', 'Minsta bredd (px)': 'Minimum width (px)', 'Minsta höjd (px)': 'Minimum height (px)',
  'Tyst efter larm (s)': 'Quiet after alarm (s)', 'Minsta tid mellan analyser (s)': 'Minimum time between analyses (s)', 'Antal bilder vid rörelse': 'Snapshots per motion event',
  'Vänta innan första bild (ms)': 'Wait before first snapshot (ms)', 'Uteslutningszoner': 'Exclusion zones', 'Hämta bild': 'Get image',
  'Dra en ruta i bilden. Träffar i en zon larmar inte. "Helt inom" ignorerar bara föremål som ligger helt i zonen, "Berör" ignorerar allt som rör vid den.': 'Drag a box in the image. Detections in a zone do not trigger. "Fully inside" only ignores objects entirely inside the zone, "Touches" ignores anything touching it.',
  'Zon {n}': 'Zone {n}', 'Helt inom': 'Fully inside', 'Berör': 'Touches', 'Inga zoner.': 'No zones.', 'Kunde inte hämta bild': 'Could not get image',
  'Testa': 'Test', 'Ta bild och analysera': 'Take snapshot and analyse', 'Live': 'Live', 'Stoppa': 'Stop', 'Fullskärm': 'Full screen', 'Visa AI': 'Show AI',
  'Kör AI:n med inställningarna ovan (även osparade) utan att skicka larm. Gröna rutor är zoner, röda godkända träffar, grå övriga.': 'Runs the AI with the settings above (including unsaved) without sending alarms. Green boxes are zones, red are accepted detections, grey the rest.',
  'Analyserar…': 'Analysing…', 'Skulle larma': 'Would alarm', 'Skulle inte larma': 'Would not alarm', 'AI {ms} ms · bild {w}×{h}': 'AI {ms} ms · image {w}×{h}',
  'Typ': 'Type', 'Säkerhet': 'Confidence', 'Storlek': 'Size', 'larm': 'alarm', 'AI:n hittade inget.': 'The AI found nothing.',
  'fel typ': 'wrong type', 'för låg säkerhet': 'confidence too low', 'för liten': 'too small', 'i zon': 'in zone',
  'Ta bort kameran': 'Remove camera', 'Ta bort {name} från SynoArgus? (Kameran i Surveillance Station påverkas inte.)': 'Remove {name} from SynoArgus? (The camera in Surveillance Station is not affected.)',
  '{fps} bilder/s': '{fps} frames/s', 'AI {ms} ms': 'AI {ms} ms',
  // rörelse
  'Rörelsedetektering i Surveillance Station': 'Motion detection in Surveillance Station',
  'Justera känslighet och tröskel, gå framför kameran och se direkt hur ofta Surveillance Station utlöser SynoArgus. Högre känslighet och lägre tröskel = utlöser lättare.': 'Adjust sensitivity and threshold, walk in front of the camera and see right away how often Surveillance Station triggers SynoArgus. Higher sensitivity and lower threshold = triggers more easily.',
  'Känslighet (Sensitivity)': 'Sensitivity', 'Tröskel (Threshold)': 'Threshold', 'Spara till Surveillance Station': 'Save to Surveillance Station', 'Läs om': 'Reload',
  'Sparat i Surveillance Station': 'Saved in Surveillance Station', 'Hämtar värden…': 'Loading values…',
  'Kunde inte läsa värdena: {e}': 'Could not read the values: {e}',
  'Surveillance Station gav inga värden för den här kameran. Rörelsedetekteringen sköts kanske av kameran själv (välj "By Surveillance Station" i kamerans inställningar).': 'Surveillance Station returned no values for this camera. Motion detection may be handled by the camera itself (choose "By Surveillance Station" in the camera settings).',
  'Rörelsemätare': 'Motion meter', 'Starta mätning': 'Start measuring', 'Stoppa mätning': 'Stop measuring',
  'Utlösningar senaste minuten': 'Triggers last minute', 'Inga utlösningar ännu. Gå framför kameran.': 'No triggers yet. Walk in front of the camera.',
  'analyseras': 'analysing', 'larm': 'alarm', 'inget': 'nothing', 'fel': 'error', 'tyst period': 'quiet period', 'för tätt': 'too frequent', 'upptagen': 'busy', 'avstängd': 'disabled',
  'Kräver en Action Rule för kameran (se adressen överst).': 'Requires an Action Rule for the camera (see the address at the top).',
  // notifierare
  'Lägg till': 'Add', 'Inga notifierare ännu.': 'No notifiers yet.', 'Bara för kameror (inga valda = alla)': 'Only for cameras (none selected = all)',
  'Bara för typer (inga valda = alla)': 'Only for types (none selected = all)', 'Skicka test': 'Send test', 'Spara först': 'Save first', 'Testlarm skickat': 'Test alarm sent',
  'Ta bort notifieraren?': 'Remove the notifier?', 'Spara innan du testar en ny notifierare.': 'Save before testing a new notifier.',
  'Access Token (från pushbullet.com > Settings)': 'Access Token (from pushbullet.com > Settings)', 'Enhets-id (tomt = alla enheter)': 'Device id (empty = all devices)',
  'Enhets-id är <b>inte</b> telefonens modellnamn. Gå till pushbullet.com &gt; <b>Devices</b> och klicka på enheten. Id:t är det som står efter <code>#devices/</code> i adressfältet.': 'The device id is <b>not</b> the phone model name. Go to pushbullet.com &gt; <b>Devices</b> and click the device. The id is what follows <code>#devices/</code> in the address bar.',
  'Rubrik (tomt = standard)': 'Title (empty = default)', 'Text (tomt = standard)': 'Text (empty = default)', 'Ämne (tomt = standard)': 'Subject (empty = default)',
  'Skicka bild': 'Send image', 'Autentisering': 'Authentication', 'Bearer-token': 'Bearer token', 'Användarnamn/lösenord': 'Username/password',
  'Skicka bild (multipart, fältet "image" + JSON i "payload")': 'Send image (multipart, field "image" + JSON in "payload")',
  'Broker (t.ex. Homeys IP)': 'Broker (e.g. Homey\'s IP)', 'Bas-topic': 'Base topic', 'Publiceras på <code>{t}/&lt;kamera&gt;/notification</code> som JSON.': 'Published to <code>{t}/&lt;camera&gt;/notification</code> as JSON.',
  'Skicka bild (base64 i fältet "image")': 'Send image (base64 in field "image")', 'Retain': 'Retain',
  'SMTP-server': 'SMTP server', 'Kryptering': 'Encryption', 'Avsändare (tomt = användarnamnet)': 'From (empty = username)', 'Mottagare (kommaseparerat)': 'To (comma separated)',
  'Gmail: smtp.gmail.com, port 587, STARTTLS och ett <i>applösenord</i> (Google-konto &gt; Säkerhet &gt; Applösenord).': 'Gmail: smtp.gmail.com, port 587, STARTTLS and an <i>app password</i> (Google account &gt; Security &gt; App passwords).',
  'Bot-token': 'Bot token', 'Chatt-id': 'Chat id', 'Tyst avisering': 'Silent notification',
  'Skapa en bot med <b>@BotFather</b> i Telegram och kopiera token. Skicka ett meddelande till boten, öppna <code>https://api.telegram.org/bot&lt;token&gt;/getUpdates</code> och ta värdet <code>chat.id</code>. För en grupp: lägg till boten i gruppen (id börjar då med -).': 'Create a bot with <b>@BotFather</b> in Telegram and copy the token. Send a message to the bot, open <code>https://api.telegram.org/bot&lt;token&gt;/getUpdates</code> and take the <code>chat.id</code> value. For a group: add the bot to the group (the id then starts with -).',
  'Server': 'Server', 'Ämne (topic)': 'Topic', 'Prioritet': 'Priority', 'Taggar (kommaseparerat, t.ex. rotating_light)': 'Tags (comma separated, e.g. rotating_light)',
  'Installera ntfy från Google Play och prenumerera på samma ämne. Välj ett svårgissat ämnesnamn – på ntfy.sh kan alla som känner till namnet läsa meddelandena. Du kan också köra en egen ntfy-server.': 'Install ntfy from Google Play and subscribe to the same topic. Choose a hard-to-guess topic name – on ntfy.sh anyone who knows the name can read the messages. You can also run your own ntfy server.',
  '1 – min': '1 – min', '2 – låg': '2 – low', '3 – normal': '3 – default', '4 – hög': '4 – high', '5 – max (bryter igenom Stör ej)': '5 – max (breaks through Do Not Disturb)',
  // platshållare
  'Platshållare för {where} – klicka på en för att lägga in den där markören står': 'Placeholders for {where} – click one to insert it at the cursor',
  'Platshållarna byts mot värden när larmet skickas.': 'Placeholders are replaced with values when the alarm is sent.',
  'adressen': 'the address', 'rubrik och text': 'title and text', 'ämne och text': 'subject and text', 'texten': 'the text',
  'Kamerans namn': 'Camera name', 'Vad som hittades': 'What was found', 'Vad som hittades (engelska)': 'What was found (English)', 'Antal träffar': 'Number of detections',
  'Hela meddelandet': 'The full message', 'Högsta säkerhet i %': 'Highest confidence in %', 'Klockslag': 'Time', 'Datum': 'Date', 'Länk till bilden i SynoArgus': 'Link to the image in SynoArgus',
  'Exempel: rubrik <code>%kamera%</code>, text <code>%vad% kl %tid%</code>.': 'Example: title <code>%camera%</code>, text <code>%what% at %time%</code>.',
  'WEBHOOKHELP': 'Values are URL-encoded automatically. Example for Homey: <code>https://webhook.homey.app/&lt;homey-id&gt;/synoargus?tag=%camera%;%what%</code> – the Homey flow then gets <i>OutDoor2-Backyard;Person</i> as tag. With GET and no placeholders, <code>camera</code>, <code>types</code> and <code>message</code> are sent as parameters. With POST/PUT, JSON is always sent.',
  // inställningar
  'Språk och tidszon': 'Language and time zone', 'Tidszon': 'Time zone', 'Används för klockslag i larm och filnamn.': 'Used for times in alarms and file names.',
  'Bildkvalitet': 'Image quality', 'Hög': 'High', 'Balanserad': 'Balanced', 'Låg bandbredd': 'Low bandwidth', 'Motsvarar strömprofilerna i Surveillance Station.': 'Matches the stream profiles in Surveillance Station.',
  'AI': 'AI', 'Modell': 'Model', 'Beräkning': 'Compute', 'Automatiskt (grafikkrets om den finns)': 'Automatic (GPU if available)', 'Grafikkrets': 'GPU', 'Processor': 'CPU',
  'inbyggd': 'built-in', 'egen': 'own', 'Egna modeller (t.ex. YOLO26) läggs till med konverteraren, se README.': 'Own models (e.g. YOLO26) are added with the converter, see the README.',
  'Standardvärden för kameror': 'Camera defaults', 'Säkerhet minst (%)': 'Minimum confidence (%)', 'Tid mellan bilder (ms)': 'Time between snapshots (ms)',
  'Lagring': 'Storage', 'Spara bilder i (dagar)': 'Keep images for (days)', '0 = spara för alltid': '0 = keep forever', 'Spara även analyser utan larm': 'Also save analyses without alarm',
  'SynoArgus adress (för länkar i larm)': 'SynoArgus address (for links in alarms)', 'Rensa alla händelser': 'Delete all events',
  'Radera alla händelser och bilder? Det går inte att ångra.': 'Delete all events and images? This cannot be undone.', '{n} händelser raderades': '{n} events deleted',
  'Styr kameror (webhook)': 'Control cameras (webhook)', 'Slå på eller av analysen per kamera, t.ex. från Homey. Surveillance Station påverkas inte.': 'Turn analysis on or off per camera, e.g. from Homey. Surveillance Station is not affected.',
  'Slå på': 'Turn on', 'Slå av': 'Turn off', 'Växla': 'Toggle', 'Visa läge': 'Show state', 'Kamera': 'Camera', 'Åtgärd': 'Action',
  'Säkerhetskopia': 'Backup', 'Exportera': 'Export', 'Importera': 'Import', 'Ta med lösenord och nycklar': 'Include passwords and keys',
  'Filen innehåller då lösenord i klartext. Förvara den säkert.': 'The file will then contain passwords in plain text. Keep it safe.',
  'Importera inställningar? Alla nuvarande inställningar ersätts.': 'Import settings? All current settings will be replaced.', 'Importerat: {c} kameror, {n} notifierare': 'Imported: {c} cameras, {n} notifiers',
  'Filen kunde inte läsas': 'The file could not be read',
  'Inloggning': 'Login', 'Logga in med DSM-konto': 'Log in with DSM account', 'Tillåtna DSM-konton (kommaseparerat, tomt = alla)': 'Allowed DSM accounts (comma separated, empty = all)',
  'Installera SSO Server i DSM, aktivera OIDC och lägg till SynoArgus som app med omdirigerings-URI nedan.': 'Install SSO Server in DSM, enable OIDC and add SynoArgus as an application with the redirect URI below.',
  'Aktivera SSO': 'Enable SSO', 'Issuer / Well-known-adress': 'Issuer / Well-known URL', 'Klient-id (Application ID)': 'Client ID (Application ID)',
  'Klienthemlighet (Application Secret)': 'Client secret (Application Secret)', 'Omdirigerings-URI': 'Redirect URI',
  'Kontrollerar regler i Surveillance Station…': 'Checking rules in Surveillance Station…', 'Kunde inte läsa reglerna: {e}': 'Could not read the rules: {e}',
  'Visa rådata från Surveillance Station': 'Show raw data from Surveillance Station', 'Regel finns i Surveillance Station: {n}': 'Rule exists in Surveillance Station: {n}',
  'Regeln {n} pekar på en gammal adress.': 'The rule {n} points to an old address.', 'Uppdatera adressen': 'Update the address',
  'Ingen regel för kameran i Surveillance Station.': 'No rule for this camera in Surveillance Station.', 'Skapa regel': 'Create rule',
  'Skapa först en regel med webhook för valfri kamera i Surveillance Station. Den används som mall.': 'First create a rule with a webhook for any camera in Surveillance Station. It is used as a template.',
  'Regeln skapades': 'The rule was created', 'Adressen uppdaterades': 'The address was updated',
  // status
  'Hämtar…': 'Loading…', 'Modell <b>{m}</b> på <b>{d}</b> ({s} px)': 'Model <b>{m}</b> on <b>{d}</b> ({s} px)', 'grafikkretsen': 'the GPU', 'processorn': 'the CPU',
  ' · senaste analys {ms} ms': ' · last analysis {ms} ms', 'Tillgängliga modeller: {m}': 'Available models: {m}', 'inga': 'none',
  'Senaste dygnet': 'Last 24 hours', '{a} analyser sparade · {b} larm': '{a} analyses saved · {b} alarms', 'Senast': 'Last', 'Senaste larm': 'Last alarm',
  'analyserar': 'analysing', 'Logg': 'Log', 'Inget har hänt sedan start.': 'Nothing has happened since start.', '{app} {v} (bygge {b}, {d})': '{app} {v} (build {b}, {d})',
  'Uppdatering': 'Update', 'Sök efter uppdatering': 'Check for update', 'Din version: {v}': 'Your version: {v}', 'Senaste version: {v}': 'Latest version: {v}',
  'Ny version finns!': 'A new version is available!', 'Du har senaste versionen.': 'You have the latest version.', 'Kunde inte kontrollera: {e}': 'Could not check: {e}',
  'Vad är nytt': 'What\'s new', 'Uppdatera i Container Manager: <b>Projekt</b> &gt; synoargus &gt; <b>Åtgärd</b> &gt; <b>Bygg</b> (hämtar den nya imagen).': 'Update in Container Manager: <b>Project</b> &gt; synoargus &gt; <b>Action</b> &gt; <b>Build</b> (pulls the new image).',
};
const t = (s, v) => { let r = (S.lang === 'en' && EN[s] !== undefined) ? EN[s] : (s === 'WEBHOOKHELP' ? WEBHOOKHELP_SV : s); if (v) for (const k in v) r = r.split('{' + k + '}').join(v[k]); return r; };
const WEBHOOKHELP_SV = 'Värdena kodas automatiskt för adresser (mellanslag, å/ä/ö). Exempel för Homey: <code>https://webhook.homey.app/&lt;homey-id&gt;/synoargus?tag=%kamera%;%vad%</code> – i Homey-flödet får du då <i>OutDoor2-Backyard;Person</i> i taggen. Med GET och utan platshållare skickas <code>camera</code>, <code>types</code> och <code>message</code> som parametrar. Med POST/PUT skickas alltid JSON.';

const tname = l => S.lang === 'en' ? (l.charAt(0).toUpperCase() + l.slice(1)) : ((S.types?.names?.[l]) || l);
const fmtTime = ts => new Date(ts * 1000).toLocaleString(S.lang === 'en' ? 'en-GB' : 'sv-SE', { dateStyle: 'short', timeStyle: 'medium' });
const fmtClock = ts => new Date(ts * 1000).toLocaleTimeString(S.lang === 'en' ? 'en-GB' : 'sv-SE');
const num = v => (v === '' || v === null || v === undefined) ? null : Number(v);

async function api(path, opts = {}) {
  const o = { credentials: 'same-origin', headers: {}, ...opts };
  if (o.body && typeof o.body !== 'string') { o.body = JSON.stringify(o.body); o.headers['Content-Type'] = 'application/json'; }
  const r = await fetch(path, o);
  let j = null;
  try { j = await r.json(); } catch (e) { /* tomt svar */ }
  if (r.status === 401 && S.state?.logged_in) { S.state.logged_in = false; render(); }
  if (!r.ok) { const err = new Error((j && (typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail))) || `HTTP ${r.status}`); err.status = r.status; throw err; }
  return j;
}

function toast(msg, bad = false) {
  const el = $('#toast');
  el.textContent = msg; el.className = 'show' + (bad ? ' bad' : '');
  clearTimeout(toast._t); toast._t = setTimeout(() => (el.className = ''), bad ? 5000 : 2500);
}

/* Kopiering som fungerar även över http (navigator.clipboard kräver https). */
function copyText(text, el) {
  const fallback = () => {
    const ta = document.createElement('textarea');
    ta.value = text; ta.setAttribute('readonly', '');
    ta.style.cssText = 'position:fixed;top:0;left:0;opacity:0';
    document.body.appendChild(ta); ta.select(); ta.setSelectionRange(0, text.length);
    let ok = false;
    try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
    ta.remove();
    if (ok) return toast(t('Kopierat'));
    if (el) { const r = document.createRange(); r.selectNodeContents(el); const s = getSelection(); s.removeAllRanges(); s.addRange(r); }
    toast(t('Adressen är markerad – tryck Ctrl+C'), true);
  };
  if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(text).then(() => toast(t('Kopierat')), fallback);
  else fallback();
}

function copyRow(id, text) {
  return `<div class="copy"><code id="${id}">${esc(text)}</code><button type="button" class="btn" data-copy="${id}">${t('Kopiera')}</button></div>`;
}
document.addEventListener('click', e => {
  const b = e.target.closest('[data-copy]');
  if (b) { const el = document.getElementById(b.dataset.copy); if (el) copyText(el.textContent, el); }
});

/* ---------------------------------------------------------------- platshållare */
function placeholders() {
  const en = S.lang === 'en';
  return [
    [en ? '%camera%' : '%kamera%', t('Kamerans namn'), 'OutDoor2-Backyard'],
    [en ? '%what%' : '%vad%', t('Vad som hittades'), en ? 'Person, Cat' : 'Person, Katt'],
    [en ? '%what_en%' : '%vad_en%', t('Vad som hittades (engelska)'), 'person, cat'],
    [en ? '%count%' : '%antal%', t('Antal träffar'), '3'],
    [en ? '%message%' : '%meddelande%', t('Hela meddelandet'), en ? 'OutDoor2-Backyard: 2 people, Cat' : 'OutDoor2-Backyard: 2 personer, Katt'],
    [en ? '%confidence%' : '%säkerhet%', t('Högsta säkerhet i %'), '87'],
    [en ? '%time%' : '%tid%', t('Klockslag'), '22:58:14'],
    [en ? '%date%' : '%datum%', t('Datum'), '2026-11-08'],
    [en ? '%image%' : '%bild%', t('Länk till bilden i SynoArgus'), 'http://…/captures/…jpg'],
  ];
}

function phHelp(where, example) {
  return `<details class="ph" style="grid-column:1/-1"><summary>${t('Platshållare för {where} – klicka på en för att lägga in den där markören står', { where: t(where) })}</summary>
    <p class="small muted" style="margin:8px 0 0">${t('Platshållarna byts mot värden när larmet skickas.')}${example ? ' ' + example : ''}</p>
    <table>${placeholders().map(([k, d, e]) => `<tr><td><button type="button" class="chip" data-ph="${k}">${k}</button></td><td>${d}</td><td class="muted">${esc(e)}</td></tr>`).join('')}</table>
  </details>`;
}

/* ---------------------------------------------------------------- start */
async function boot() {
  try { S.state = await api('/api/state'); } catch (e) { main.innerHTML = `<p class="err center">${esc(t('Kan inte nå SynoArgus: {e}', { e: e.message }))}</p>`; return; }
  S.lang = S.state.language || 'sv';
  document.documentElement.lang = S.lang;
  translateChrome();
  if (S.state.logged_in) { await loadConfig(); checkUpdateBadge(); }
  render();
}

function translateChrome() {
  $$('#nav button').forEach(b => { b.textContent = t(b.dataset.label); });
  $('#logoutBtn').textContent = t('Logga ut');
  $('#viewerClose').textContent = t('Stäng');
}

async function loadConfig() {
  const j = await api('/api/config');
  S.cfg = j.config; S.types = j.types; S.models = j.models || []; S.triggerBase = j.trigger_base;
}

async function checkUpdateBadge() {
  try { S.update = await api('/api/update'); } catch (e) { S.update = null; }
  $('#nav button[data-tab=status]').classList.toggle('badge', !!S.update?.newer);
}

function render() {
  stopAll();
  const st = S.state;
  $('#nav').hidden = !st.logged_in;
  $('#who').hidden = !st.logged_in;
  if (st.logged_in) $('#whoName').textContent = st.user;
  if (!st.setup_done) return renderSetup();
  if (!st.logged_in) return renderLogin();
  $$('#nav button').forEach(b => b.classList.toggle('active', b.dataset.tab === S.tab));
  ({ events: renderEvents, cameras: renderCameras, notifiers: renderNotifiers, settings: renderSettings, status: renderStatus })[S.tab]();
}

$$('#nav button').forEach(b => b.addEventListener('click', () => { S.tab = b.dataset.tab; render(); window.scrollTo(0, 0); }));
$('#logoutBtn').addEventListener('click', async () => { await api('/api/logout', { method: 'POST' }); S.state.logged_in = false; render(); });

function langSwitch() {
  return `<div class="row" style="justify-content:flex-end;gap:6px"><span class="muted small">${t('Språk')}</span>
    <button type="button" class="chip ${S.lang === 'sv' ? 'on' : ''}" data-lang="sv">Svenska</button>
    <button type="button" class="chip ${S.lang === 'en' ? 'on' : ''}" data-lang="en">English</button></div>`;
}
document.addEventListener('click', async e => {
  const b = e.target.closest('[data-lang]');
  if (!b || b.dataset.lang === S.lang) return;
  try { await api('/api/language', { method: 'POST', body: { language: b.dataset.lang } }); location.reload(); }
  catch (err) { toast(err.message, true); }
});

/* ---------------------------------------------------------------- installation */
function renderSetup() {
  if (!S.state.setup_allowed) {
    main.innerHTML = `<div class="panel auth">${langSwitch()}<h2>${t('Installation')}</h2><p>${t('SynoArgus är inte installerat ännu. Öppna sidan från hemnätet för att göra installationen.')}</p></div>`;
    return;
  }
  main.innerHTML = `
  <div class="panel auth">
    ${langSwitch()}
    <h2>${t('Välkommen till SynoArgus')}</h2>
    <p class="muted small">${t('Anslut till Surveillance Station. Använd ett eget konto för SynoArgus utan tvåstegsverifiering, med behörighet till Surveillance Station.')}</p>
    <form id="setupForm" class="grid" style="grid-template-columns:1fr">
      <label class="f">${t('NAS-adress')}<input name="url" placeholder="http://192.168.1.10:5000" required></label>
      <label class="f">${t('Användare för Surveillance Station')}<input name="user" autocomplete="off" required></label>
      <label class="f">${t('Lösenord')}<input name="password" type="password" autocomplete="new-password" required></label>
      <label class="check"><input type="checkbox" name="verify_tls"> ${t('Kontrollera HTTPS-certifikat')}</label>
      <hr style="border:0;border-top:1px solid var(--line);width:100%">
      <p class="small" style="margin:0"><b>${t('Vem får logga in i SynoArgus?')}</b></p>
      <p class="muted small" style="margin:0">${t('Ange ditt eget DSM-konto. Det blir det enda kontot som får logga in (fler kan läggas till under Inställningar > Inloggning). Lämnar du fältet tomt blir tjänstekontot ovan det enda som får logga in.')}</p>
      <label class="f">${t('Ditt DSM-konto')}<input name="login_user" autocomplete="username"></label>
      <label class="f">${t('Lösenord')}<input name="login_password" type="password" autocomplete="current-password"></label>
      <label class="f">${t('Engångskod (om tvåstegsverifiering)')}<input name="login_otp" inputmode="numeric" autocomplete="one-time-code"></label>
      <button class="btn primary">${t('Anslut och starta')}</button>
      <p id="setupMsg" class="small"></p>
    </form>
  </div>`;
  $('#setupForm').addEventListener('submit', async e => {
    e.preventDefault();
    const f = new FormData(e.target); const btn = e.target.querySelector('button.primary');
    btn.disabled = true; $('#setupMsg').textContent = t('Ansluter…'); $('#setupMsg').className = 'small muted';
    let tz = ''; try { tz = Intl.DateTimeFormat().resolvedOptions().timeZone || ''; } catch (err) { /* */ }
    try {
      const r = await api('/api/setup', { method: 'POST', body: {
        synology: { url: f.get('url'), user: f.get('user'), password: f.get('password'), verify_tls: !!f.get('verify_tls') },
        login_user: f.get('login_user'), login_password: f.get('login_password'), login_otp: f.get('login_otp'), timezone: tz } });
      toast(t('Klart! {n} kameror hittades.', { n: r.cameras }));
      S.tab = 'cameras';
      await boot();
    } catch (err) { $('#setupMsg').textContent = err.message; $('#setupMsg').className = 'small err'; btn.disabled = false; }
  });
}

/* ---------------------------------------------------------------- inloggning */
function renderLogin() {
  const p = new URLSearchParams(location.search);
  const fel = { sso: t('SSO-inloggningen misslyckades.'), behorighet: t('Kontot har inte behörighet till SynoArgus.') }[p.get('fel')] || (p.get('fel') ? t('Inloggningen misslyckades.') : '');
  main.innerHTML = `
  <div class="panel auth">
    ${langSwitch()}
    <h2>${t('Logga in')}</h2>
    ${fel ? `<p class="err small">${esc(fel)}</p>` : ''}
    ${S.state.unlocked ? `<p class="small err">${t('Upplåst läge: alla DSM-konton kan logga in. Ta bort SYNOARGUS_UNLOCK i docker-compose.yml när du är klar.')}</p>` : ''}
    ${S.state.sso ? `<p><a class="btn primary" style="display:block;text-align:center;text-decoration:none;padding:10px" href="/auth/sso">${t('Logga in med Synology SSO')}</a></p>` : ''}
    ${S.state.dsm_login ? `
    ${S.state.sso ? `<p class="muted small center">${t('eller med DSM-konto')}</p>` : `<p class="muted small">${t('Logga in med ditt DSM-konto.')}</p>`}
    <form id="loginForm" class="grid" style="grid-template-columns:1fr">
      <label class="f">${t('Användarnamn')}<input name="user" autocomplete="username" required></label>
      <label class="f">${t('Lösenord')}<input name="password" type="password" autocomplete="current-password" required></label>
      <label class="f" id="otpRow" hidden>${t('Engångskod')}<input name="otp" inputmode="numeric" autocomplete="one-time-code"></label>
      <button class="btn ${S.state.sso ? '' : 'primary'}">${t('Logga in')}</button>
      <p id="loginMsg" class="small err"></p>
    </form>` : ''}
  </div>`;
  const form = $('#loginForm');
  if (!form) return;
  form.addEventListener('submit', async e => {
    e.preventDefault();
    const f = new FormData(form);
    try {
      await api('/api/login', { method: 'POST', body: { user: f.get('user'), password: f.get('password'), otp: f.get('otp') } });
      history.replaceState(null, '', '/');
      await boot();
    } catch (err) {
      if (err.status === 428) { $('#otpRow').hidden = false; $('#loginMsg').textContent = t('Ange engångskoden.'); $('[name=otp]').focus(); }
      else $('#loginMsg').textContent = err.message;
    }
  });
}

/* ---------------------------------------------------------------- händelser */
async function renderEvents() {
  const cams = Object.keys(S.cfg.cameras || {});
  main.innerHTML = `
  <div class="row" style="justify-content:space-between;margin-bottom:12px">
    <h2 style="margin:0">${t('Händelser')}</h2>
    <div class="row">
      <select id="evCam" style="width:auto"><option value="">${t('Alla kameror')}</option>${cams.map(c => `<option>${esc(c)}</option>`).join('')}</select>
      <label class="check small"><input type="checkbox" id="evAll"> ${t('Visa även utan larm')}</label>
    </div>
  </div>
  <div id="evList" class="events"></div>
  <p class="center"><button class="btn" id="evMore" hidden>${t('Visa fler')}</button></p>`;
  let last = 0;
  const load = async (reset) => {
    if (reset) { last = 0; $('#evList').innerHTML = ''; }
    const q = new URLSearchParams({ camera: $('#evCam').value, alarms: $('#evAll').checked ? 0 : 1, limit: 40 });
    if (last) q.set('before', last);
    const { events } = await api('/api/events?' + q);
    if (reset && !events.length) $('#evList').innerHTML = `<p class="muted">${t('Inga händelser ännu. När Surveillance Station larmar och AI:n hittar något hamnar det här.')}</p>`;
    $('#evList').insertAdjacentHTML('beforeend', events.map(ev => `
      <div class="ev">
        ${ev.image ? `<img loading="lazy" src="/captures/${esc(ev.image)}" alt="">` : ''}
        <div class="meta">
          <div class="row" style="justify-content:space-between"><strong>${esc(ev.camera)}</strong><span class="muted">${fmtTime(ev.ts)}</span></div>
          <div>${ev.alarm ? ev.types.map(x => `<span class="tag">${esc(tname(x))}</span>`).join(' ') : `<span class="muted">${t('Inget av intresse')}</span>`}</div>
          <div class="muted small">${ev.ms ?? '?'} ms${ev.notified?.length ? ' · ' + ev.notified.map(n => `<span class="${n.ok ? 'okc' : 'err'}" title="${esc(n.error || '')}">${esc(n.name)} ${n.ok ? '✓' : '✗'}</span>`).join(' ') : ''}</div>
        </div>
      </div>`).join(''));
    if (events.length) last = events[events.length - 1].id;
    $('#evMore').hidden = events.length < 40;
  };
  $('#evCam').onchange = () => load(true);
  $('#evAll').onchange = () => load(true);
  $('#evMore').onclick = () => load(false);
  $('#evList').addEventListener('click', e => {
    if (e.target.tagName === 'IMG') { $('#viewerImg').src = e.target.src; $('#viewer').showModal(); }
  });
  try { await load(true); } catch (e) { toast(e.message, true); }
}

/* ---------------------------------------------------------------- kameror */
function renderCameras() {
  const cams = S.cfg.cameras || {};
  const names = Object.keys(cams);
  if (!S.cam || !cams[S.cam]) S.cam = names[0] || null;
  main.innerHTML = `
  <div class="row" style="justify-content:space-between"><h2>${t('Kameror')}</h2><button class="btn" id="fetchCams">${t('Hämta från Surveillance Station')}</button></div>
  <div class="camlist">${names.map(n => `<button class="chip ${n === S.cam ? 'on' : ''}" data-cam="${esc(n)}">${esc(n)}${cams[n].enabled ? '' : ` (${t('av')})`}</button>`).join('') || `<span class="muted">${t('Inga kameror. Hämta dem från Surveillance Station.')}</span>`}</div>
  <div id="camEdit"></div>`;
  $$('.camlist .chip').forEach(b => b.onclick = () => { S.cam = b.dataset.cam; render(); });
  $('#fetchCams').onclick = async () => {
    try {
      const { cameras } = await api('/api/ss/cameras');
      let added = 0;
      for (const c of cameras) {
        if (!S.cfg.cameras[c.name]) { await api('/api/cameras/' + encodeURIComponent(c.name), { method: 'PUT', body: { ss_id: c.id } }); added++; }
      }
      await loadConfig();
      toast(added ? t('{n} kameror lades till', { n: added }) : t('Inga nya kameror'));
      render();
    } catch (e) { toast(e.message, true); }
  };
  if (S.cam) renderCamEditor(JSON.parse(JSON.stringify(cams[S.cam])));
}

function renderCamEditor(cam) {
  const d = S.cfg.defaults;
  const enc = encodeURIComponent(cam.name);
  const url = `${S.triggerBase}/api/trigger/${enc}?token=${encodeURIComponent(S.cfg.trigger_token)}`;
  const common = S.types.common;
  const others = S.types.all.filter(x => !common.includes(x));
  const el = $('#camEdit');
  el.innerHTML = `
  <div class="panel">
    <div class="row" style="justify-content:space-between"><h3>${esc(cam.name)}</h3><label class="check"><input type="checkbox" id="cEnabled" ${cam.enabled ? 'checked' : ''}> ${t('Aktiv')}</label></div>
    <p class="muted small" style="margin:0 0 4px">${t('Adress till Action Rule i Surveillance Station (Webhook, metod GET):')}</p>
    ${copyRow('trigUrl', url)}
    <div id="arBox" class="arbox small muted">${t('Kontrollerar regler i Surveillance Station…')}</div>
  </div>
  <div class="panel">
    <h3>${t('Vad ska larma?')}</h3>
    <div class="chips" id="cTypes">${common.map(x => `<button class="chip ${cam.types.includes(x) ? 'on' : ''}" data-t="${x}">${esc(tname(x))}</button>`).join('')}</div>
    <div class="row" style="margin-top:8px"><select id="cOther" style="width:auto"><option value="">${t('Lägg till annan typ…')}</option>${others.map(x => `<option value="${x}">${esc(tname(x))}</option>`).join('')}</select>
      <span id="cOtherList"></span></div>
    <div class="grid" style="margin-top:14px">
      <label class="f">${t('Säkerhet minst')} <b id="thrV">${cam.threshold ?? d.threshold} %</b><input type="range" id="cThr" min="10" max="95" value="${cam.threshold ?? d.threshold}"><span class="hint">${t('Standard {v} %', { v: d.threshold })}</span></label>
      <label class="f">${t('Minsta bredd (px)')}<input type="number" id="cMinW" min="0" value="${cam.min_width ?? ''}" placeholder="${d.min_width}"></label>
      <label class="f">${t('Minsta höjd (px)')}<input type="number" id="cMinH" min="0" value="${cam.min_height ?? ''}" placeholder="${d.min_height}"></label>
      <label class="f">${t('Tyst efter larm (s)')}<input type="number" id="cCool" min="0" value="${cam.cooldown_s ?? ''}" placeholder="${d.cooldown_s}"></label>
      <label class="f">${t('Minsta tid mellan analyser (s)')}<input type="number" id="cDelay" min="0" value="${cam.delay_s ?? ''}" placeholder="${d.delay_s}"></label>
      <label class="f">${t('Antal bilder vid rörelse')}<input type="number" id="cMax" min="1" max="10" value="${cam.max_snapshots ?? ''}" placeholder="${d.max_snapshots}"></label>
      <label class="f">${t('Vänta innan första bild (ms)')}<input type="number" id="cWait" min="0" step="100" value="${cam.wait_ms || 0}"></label>
    </div>
  </div>
  <div class="panel">
    <div class="row" style="justify-content:space-between"><h3>${t('Uteslutningszoner')}</h3><button class="btn" id="loadSnap">${t('Hämta bild')}</button></div>
    <p class="muted small" style="margin-top:0">${t('Dra en ruta i bilden. Träffar i en zon larmar inte. "Helt inom" ignorerar bara föremål som ligger helt i zonen, "Berör" ignorerar allt som rör vid den.')}</p>
    <div class="zonebox" id="zoneBox" hidden><img id="snapImg" alt=""><canvas id="zoneCanvas"></canvas></div>
    <div class="zones-list" id="zonesList"></div>
  </div>
  <div class="panel">
    <div class="row" style="justify-content:space-between"><h3>${t('Testa')}</h3>
      <div class="row"><button class="btn" id="testCam">${t('Ta bild och analysera')}</button><button class="btn" id="liveBtn">▶ ${t('Live')}</button></div></div>
    <p class="muted small" style="margin-top:0">${t('Kör AI:n med inställningarna ovan (även osparade) utan att skicka larm. Gröna rutor är zoner, röda godkända träffar, grå övriga.')}</p>
    <div id="liveBox" class="livebox" hidden>
      <img id="liveImg" alt="">
      <div class="livebar">
        <label class="check small"><input type="checkbox" id="liveAi"> ${t('Visa AI')}</label>
        <span id="liveInfo" class="small"></span>
        <span style="flex:1"></span>
        <button class="btn" id="liveFull">⛶ ${t('Fullskärm')}</button>
        <button class="btn" id="liveStop">■ ${t('Stoppa')}</button>
      </div>
    </div>
    <div id="testOut"></div>
  </div>
  <div class="panel" id="mdPanel">
    <h3>${t('Rörelsedetektering i Surveillance Station')}</h3>
    <p class="muted small" style="margin-top:0">${t('Justera känslighet och tröskel, gå framför kameran och se direkt hur ofta Surveillance Station utlöser SynoArgus. Högre känslighet och lägre tröskel = utlöser lättare.')}</p>
    <div id="mdValues" class="muted small">${t('Hämtar värden…')}</div>
    <h3 style="margin-top:16px">${t('Rörelsemätare')}</h3>
    <p class="muted small" style="margin-top:0">${t('Kräver en Action Rule för kameran (se adressen överst).')}</p>
    <div class="meter">
      <div class="meter-count"><span id="mCount">–</span><small>${t('Utlösningar senaste minuten')}</small></div>
      <button class="btn" id="mToggle">${t('Starta mätning')}</button>
    </div>
    <div id="mList" class="small"></div>
  </div>
  <div class="row"><button class="btn primary" id="saveCam">${t('Spara')}</button><button class="btn danger" id="delCam">${t('Ta bort kameran')}</button></div>`;

  const toggleType = x => { cam.types = cam.types.includes(x) ? cam.types.filter(y => y !== x) : [...cam.types, x]; };
  const drawOther = () => { $('#cOtherList').innerHTML = cam.types.filter(x => !common.includes(x)).map(x => `<button class="chip on" data-t="${x}">${esc(tname(x))} ✕</button>`).join(' '); };
  drawOther();
  $('#cTypes').onclick = e => { const x = e.target.dataset.t; if (!x) return; toggleType(x); e.target.classList.toggle('on'); };
  $('#cOther').onchange = e => { const x = e.target.value; if (x && !cam.types.includes(x)) { cam.types.push(x); drawOther(); } e.target.value = ''; };
  $('#cOtherList').onclick = e => { const x = e.target.dataset.t; if (x) { toggleType(x); drawOther(); } };
  $('#cThr').oninput = e => { $('#thrV').textContent = e.target.value + ' %'; };

  const collect = () => {
    const thr = Number($('#cThr').value);
    return {
      enabled: $('#cEnabled').checked, types: cam.types,
      threshold: thr === d.threshold && cam.threshold == null ? null : thr,
      min_width: num($('#cMinW').value), min_height: num($('#cMinH').value),
      cooldown_s: num($('#cCool').value), delay_s: num($('#cDelay').value),
      max_snapshots: num($('#cMax').value), wait_ms: num($('#cWait').value) || 0, zones: cam.zones,
    };
  };

  // ---- zoner
  const canvas = $('#zoneCanvas'); const img = $('#snapImg');
  const drawZones = (temp) => {
    const box = $('#zoneBox');
    if (!box || box.hidden) return;
    canvas.width = img.clientWidth; canvas.height = img.clientHeight;
    const g = canvas.getContext('2d'); g.clearRect(0, 0, canvas.width, canvas.height);
    const W = canvas.width, H = canvas.height;
    [...cam.zones, ...(temp ? [temp] : [])].forEach((z, i) => {
      const x = Math.min(z.x1, z.x2) * W, y = Math.min(z.y1, z.y2) * H, w = Math.abs(z.x2 - z.x1) * W, h = Math.abs(z.y2 - z.y1) * H;
      g.fillStyle = 'rgba(80,200,120,.22)'; g.fillRect(x, y, w, h);
      g.strokeStyle = '#50c878'; g.lineWidth = 2; g.strokeRect(x, y, w, h);
      if (z !== temp) { g.fillStyle = '#50c878'; g.font = 'bold 14px system-ui'; g.fillText(String(i + 1), x + 5, y + 16); }
    });
  };
  const listZones = () => {
    $('#zonesList').innerHTML = cam.zones.map((z, i) => `
      <div class="row small"><b>${t('Zon {n}', { n: i + 1 })}</b>
        <select data-i="${i}" class="zMode" style="width:auto"><option value="contains" ${z.mode !== 'intersect' ? 'selected' : ''}>${t('Helt inom')}</option><option value="intersect" ${z.mode === 'intersect' ? 'selected' : ''}>${t('Berör')}</option></select>
        <button class="link" data-del="${i}">${t('Ta bort')}</button></div>`).join('') || `<span class="muted small">${t('Inga zoner.')}</span>`;
    drawZones();
  };
  $('#zonesList').onclick = e => { if (e.target.dataset.del) { cam.zones.splice(Number(e.target.dataset.del), 1); listZones(); } };
  $('#zonesList').onchange = e => { if (e.target.classList.contains('zMode')) cam.zones[Number(e.target.dataset.i)].mode = e.target.value; };
  listZones();
  let start = null;
  const pos = e => { const r = canvas.getBoundingClientRect(); return { x: Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)), y: Math.min(1, Math.max(0, (e.clientY - r.top) / r.height)) }; };
  canvas.addEventListener('pointerdown', e => { start = pos(e); canvas.setPointerCapture(e.pointerId); });
  canvas.addEventListener('pointermove', e => { if (!start) return; const p = pos(e); drawZones({ x1: start.x, y1: start.y, x2: p.x, y2: p.y }); });
  canvas.addEventListener('pointerup', e => {
    if (!start) return; const p = pos(e);
    const z = { x1: +Math.min(start.x, p.x).toFixed(4), y1: +Math.min(start.y, p.y).toFixed(4), x2: +Math.max(start.x, p.x).toFixed(4), y2: +Math.max(start.y, p.y).toFixed(4), mode: 'contains' };
    start = null;
    if (z.x2 - z.x1 > 0.01 && z.y2 - z.y1 > 0.01) cam.zones.push(z);
    listZones();
  });
  window.onresize = () => drawZones();
  $('#loadSnap').onclick = async () => {
    $('#loadSnap').disabled = true;
    img.onload = () => { $('#zoneBox').hidden = false; drawZones(); $('#loadSnap').disabled = false; };
    img.onerror = () => { toast(t('Kunde inte hämta bild'), true); $('#loadSnap').disabled = false; };
    img.src = `/api/cameras/${enc}/snapshot?_=${Date.now()}`;
  };

  // ---- test
  $('#testCam').onclick = async () => {
    const b = $('#testCam'); b.disabled = true; $('#testOut').innerHTML = `<p class="muted">${t('Analyserar…')}</p>`;
    try {
      const r = await api(`/api/cameras/${enc}/test`, { method: 'POST', body: collect() });
      const why = { 'typ': t('fel typ'), 'säkerhet': t('för låg säkerhet'), 'storlek': t('för liten'), 'zon': t('i zon') };
      $('#testOut').innerHTML = `
        <p><b class="${r.alarm ? 'okc' : ''}">${r.alarm ? t('Skulle larma') : t('Skulle inte larma')}</b> <span class="muted small">· ${t('AI {ms} ms · bild {w}×{h}', { ms: r.ms, w: r.width, h: r.height })}</span></p>
        <img src="${r.image}" style="max-width:100%;border-radius:8px" alt="">
        ${r.detections.length ? `<table><tr><th>${t('Typ')}</th><th>${t('Säkerhet')}</th><th>${t('Storlek')}</th><th></th></tr>${r.detections.map(x => `
          <tr><td>${esc(tname(x.label))}</td><td>${x.confidence} %</td><td>${x.x2 - x.x1}×${x.y2 - x.y1}</td><td>${x.valid ? `<span class="tag ok">${t('larm')}</span>` : `<span class="tag">${why[x.reason] || x.reason}</span>`}</td></tr>`).join('')}</table>` : `<p class="muted small">${t('AI:n hittade inget.')}</p>`}`;
    } catch (e) { $('#testOut').innerHTML = `<p class="err">${esc(e.message)}</p>`; }
    b.disabled = false;
  };

  // ---- livebild
  let live = null;
  const stopLive = () => { if (live) { live.running = false; live = null; } $('#liveBox') && ($('#liveBox').hidden = true); if (document.fullscreenElement) document.exitFullscreen().catch(() => {}); };
  $('#liveBtn').onclick = () => {
    if (live) return stopLive();
    const box = $('#liveBox'), limg = $('#liveImg'); box.hidden = false;
    live = { running: true }; const me = live; stoppers.add(stopLive);
    let lastUrl = null, frames = [];
    (async () => {
      while (me.running && document.body.contains(limg)) {
        const t0 = performance.now();
        try {
          const r = await fetch(`/api/cameras/${enc}/live?ai=${$('#liveAi').checked ? 1 : 0}&_=${Date.now()}`, { credentials: 'same-origin' });
          if (!r.ok) { let m = `HTTP ${r.status}`; try { m = (await r.json()).detail || m; } catch (e) { /* */ } throw new Error(m); }
          const blob = await r.blob(); if (!me.running) break;
          const u = URL.createObjectURL(blob); limg.src = u; if (lastUrl) URL.revokeObjectURL(lastUrl); lastUrl = u;
          frames.push(performance.now()); frames = frames.filter(x => performance.now() - x < 5000);
          const fps = (frames.length / 5).toFixed(1);
          const aims = r.headers.get('X-AI-ms');
          $('#liveInfo').textContent = t('{fps} bilder/s', { fps }) + ($('#liveAi').checked && aims ? ' · ' + t('AI {ms} ms', { ms: aims }) : '');
        } catch (e) { $('#liveInfo').textContent = e.message; await sleep(2000); }
        const dt = performance.now() - t0; if (dt < 350) await sleep(350 - dt);
      }
      if (lastUrl) URL.revokeObjectURL(lastUrl);
    })();
  };
  $('#liveStop').onclick = stopLive;
  $('#liveFull').onclick = () => {
    const box = $('#liveBox');
    if (document.fullscreenElement) return document.exitFullscreen();
    (box.requestFullscreen || box.webkitRequestFullscreen || (() => box.classList.toggle('fake-full'))).call(box);
  };

  // ---- action rule i Surveillance Station
  const loadAr = async () => {
    const box = $('#arBox'); if (!box) return;
    box.className = 'arbox small muted'; box.textContent = t('Kontrollerar regler i Surveillance Station…');
    let r;
    try { r = await api(`/api/cameras/${enc}/actionrule`); }
    catch (e) { box.innerHTML = `<span class="err">${esc(t('Kunde inte läsa reglerna: {e}', { e: e.message }))}</span>`; return; }
    const raw = `<details class="small"><summary class="muted">${t('Visa rådata från Surveillance Station')}</summary><pre class="notes">${esc(JSON.stringify(r.raw, null, 2))}</pre></details>`;
    const ok = r.rules.filter(x => x.current), old = r.rules.filter(x => !x.current);
    const st = x => x.enabled === false || x.enabled === 0 ? ` <span class="tag">${t('avstängd')}</span>` : '';
    let html = '';
    if (ok.length) html = `<span class="okc">✓ ${t('Regel finns i Surveillance Station: {n}', { n: esc(ok.map(x => x.name).join(', ')) })}</span>${ok.map(st).join('')}`;
    else if (old.length) html = `<span class="err">${t('Regeln {n} pekar på en gammal adress.', { n: esc(old.map(x => x.name).join(', ')) })}</span> <button class="btn" id="arUpdate">${t('Uppdatera adressen')}</button>`;
    else html = `<span>${t('Ingen regel för kameran i Surveillance Station.')}</span> <button class="btn" id="arCreate">${t('Skapa regel')}</button>${r.template ? '' : `<br><span class="muted">${t('Skapa först en regel med webhook för valfri kamera i Surveillance Station. Den används som mall.')}</span>`}`;
    box.className = 'arbox small'; box.innerHTML = html + raw;
    const run = async (action, btn) => {
      btn.disabled = true;
      try { await api(`/api/cameras/${enc}/actionrule`, { method: 'POST', body: { action } }); toast(action === 'create' ? t('Regeln skapades') : t('Adressen uppdaterades')); }
      catch (e) { toast(e.message, true); }
      loadAr();
    };
    $('#arUpdate') && ($('#arUpdate').onclick = e => run('update', e.target));
    $('#arCreate') && ($('#arCreate').onclick = e => run('create', e.target));
  };
  loadAr();

  // ---- rörelsedetektering i SS
  const md = { s: null, th: null, min: 1, max: 99 };
  const drawMd = (msg) => {
    if (msg) { $('#mdValues').innerHTML = msg; return; }
    $('#mdValues').className = '';
    $('#mdValues').innerHTML = `
      <div class="steppers">
        <div class="stepper"><span>${t('Känslighet (Sensitivity)')}</span><div><button class="btn" data-md="s" data-d="-5">−</button><b id="mdS">${md.s}</b><button class="btn" data-md="s" data-d="5">+</button></div></div>
        <div class="stepper"><span>${t('Tröskel (Threshold)')}</span><div><button class="btn" data-md="th" data-d="-5">−</button><b id="mdT">${md.th}</b><button class="btn" data-md="th" data-d="5">+</button></div></div>
      </div>
      <div class="row" style="margin-top:10px"><button class="btn primary" id="mdSave">${t('Spara till Surveillance Station')}</button><button class="btn" id="mdReload">${t('Läs om')}</button></div>`;
    $$('[data-md]').forEach(b => b.onclick = () => {
      const k = b.dataset.md; md[k] = Math.max(md.min, Math.min(md.max, Number(md[k]) + Number(b.dataset.d)));
      $('#mdS').textContent = md.s; $('#mdT').textContent = md.th;
    });
    $('#mdReload').onclick = loadMd;
    $('#mdSave').onclick = async () => {
      try { const r = await api(`/api/cameras/${enc}/motion`, { method: 'PUT', body: { sensitivity: md.s, threshold: md.th } }); md.s = r.sensitivity ?? md.s; md.th = r.threshold ?? md.th; drawMd(); toast(t('Sparat i Surveillance Station')); }
      catch (e) { toast(e.message, true); }
    };
  };
  const loadMd = async () => {
    $('#mdValues').className = 'muted small'; $('#mdValues').textContent = t('Hämtar värden…');
    try {
      const r = await api(`/api/cameras/${enc}/motion`);
      if (!r.supported || r.ss_cap === false || typeof r.sensitivity !== 'number') return drawMd(`<span class="muted">${t('Surveillance Station gav inga värden för den här kameran. Rörelsedetekteringen sköts kanske av kameran själv (välj "By Surveillance Station" i kamerans inställningar).')}</span>`);
      md.s = r.sensitivity; md.th = r.threshold; md.min = r.min ?? 1; md.max = r.max ?? 99; drawMd();
    } catch (e) { drawMd(`<span class="err">${esc(t('Kunde inte läsa värdena: {e}', { e: e.message }))}</span>`); }
  };
  loadMd();

  // ---- rörelsemätare
  let meter = null;
  const resLabel = x => {
    if (x.result === 'accepted') return x.outcome === 'alarm' ? `<span class="tag ok">${t('larm')}${x.types?.length ? ': ' + x.types.map(tname).join(', ') : ''}</span>` : x.outcome === 'none' ? `<span class="tag">${t('inget')}</span>` : x.outcome === 'error' ? `<span class="tag err">${t('fel')}</span>` : `<span class="tag">${t('analyseras')}</span>`;
    return `<span class="tag">${t({ cooldown: 'tyst period', delay: 'för tätt', busy: 'upptagen', disabled: 'avstängd' }[x.result] || x.result)}</span>`;
  };
  const stopMeter = () => { if (meter) { meter.running = false; meter = null; } const b = $('#mToggle'); if (b) b.textContent = t('Starta mätning'); };
  $('#mToggle').onclick = () => {
    if (meter) return stopMeter();
    meter = { running: true }; const me = meter; stoppers.add(stopMeter);
    $('#mToggle').textContent = t('Stoppa mätning');
    let seen = 0, list = [];
    (async () => {
      while (me.running && document.body.contains($('#mList'))) {
        try {
          const r = await api(`/api/cameras/${enc}/triggers?since=${Math.max(0, (Date.now() / 1000) - 600)}`);
          list = r.triggers;
          const newest = list.length ? list[list.length - 1].ts : 0;
          if (newest > seen && seen) { const c = $('.meter-count'); c.classList.remove('flash'); void c.offsetWidth; c.classList.add('flash'); }
          seen = Math.max(seen, newest) || r.now;
          $('#mCount').textContent = list.filter(x => r.now - x.ts < 60).length;
          $('#mList').innerHTML = list.length ? `<table>${list.slice(-12).reverse().map(x => `<tr><td class="muted">${fmtClock(x.ts)}</td><td>${resLabel(x)}</td></tr>`).join('')}</table>` : `<p class="muted">${t('Inga utlösningar ännu. Gå framför kameran.')}</p>`;
        } catch (e) { $('#mList').innerHTML = `<p class="err">${esc(e.message)}</p>`; }
        await sleep(1000);
      }
    })();
  };

  $('#saveCam').onclick = async () => {
    try { await api('/api/cameras/' + enc, { method: 'PUT', body: collect() }); await loadConfig(); toast(t('Sparat')); }
    catch (e) { toast(e.message, true); }
  };
  $('#delCam').onclick = async () => {
    if (!confirm(t('Ta bort {name} från SynoArgus? (Kameran i Surveillance Station påverkas inte.)', { name: cam.name }))) return;
    await api('/api/cameras/' + enc, { method: 'DELETE' }); await loadConfig(); S.cam = null; render();
  };
}

/* ---------------------------------------------------------------- notifierare */
const KIND_NAMES = { pushbullet: 'Pushbullet', webhook: 'Webhook', mqtt: 'MQTT', email: 'Email', telegram: 'Telegram', ntfy: 'ntfy' };
const KIND_DEFAULTS = {
  pushbullet: { api_key: '', device_iden: '', send_image: true, title: '', body: '' },
  webhook: { url: '', method: 'POST', auth: 'none', username: '', password: '', token: '', send_image: false, verify_tls: true },
  mqtt: { host: '', port: 1883, username: '', password: '', base_topic: 'synoargus', send_image: false, retain: false, qos: 0 },
  email: { host: '', port: 587, security: 'starttls', username: '', password: '', from_addr: '', to: '', subject: '', body: '', send_image: true },
  telegram: { bot_token: '', chat_id: '', text: '', send_image: true, silent: false },
  ntfy: { server: 'https://ntfy.sh', topic: '', auth: 'none', token: '', username: '', password: '', title: '', body: '', priority: 3, tags: '', send_image: true },
};
let NOTI = null;

function renderNotifiers() {
  NOTI = JSON.parse(JSON.stringify(S.cfg.notifiers || []));
  drawNotifiers();
}

function drawNotifiers() {
  const cams = Object.keys(S.cfg.cameras || {});
  const types = [...new Set([...S.types.common, ...Object.values(S.cfg.cameras || {}).flatMap(c => c.types)])];
  main.innerHTML = `
  <div class="row" style="justify-content:space-between"><h2>${t('Notifierare')}</h2>
    <div class="row"><select id="newKind" style="width:auto">${Object.entries(KIND_NAMES).map(([k, v]) => `<option value="${k}">${v}</option>`).join('')}</select><button class="btn" id="addN">${t('Lägg till')}</button></div></div>
  ${NOTI.length ? '' : `<p class="muted">${t('Inga notifierare ännu.')}</p>`}
  ${NOTI.map((n, i) => `
  <div class="panel" data-i="${i}">
    <div class="row" style="justify-content:space-between"><h3>${KIND_NAMES[n.type]}${n.name ? ': ' + esc(n.name) : ''}</h3>
      <label class="check"><input type="checkbox" data-k="enabled" ${n.enabled ? 'checked' : ''}> ${t('Aktiv')}</label></div>
    <div class="grid">
      <label class="f">${t('Namn')}<input data-k="name" value="${esc(n.name)}" placeholder="${KIND_NAMES[n.type]}"></label>
      ${fieldsFor(n)}
    </div>
    <div class="grid" style="margin-top:12px">
      <div><div class="muted small">${t('Bara för kameror (inga valda = alla)')}</div><div class="chips" data-list="cameras">${cams.map(c => `<button class="chip ${n.cameras.includes(c) ? 'on' : ''}" data-v="${esc(c)}">${esc(c)}</button>`).join('')}</div></div>
      <div><div class="muted small">${t('Bara för typer (inga valda = alla)')}</div><div class="chips" data-list="types">${types.map(x => `<button class="chip ${n.types.includes(x) ? 'on' : ''}" data-v="${x}">${esc(tname(x))}</button>`).join('')}</div></div>
    </div>
    <div class="row" style="margin-top:12px"><button class="btn" data-act="test">${t('Skicka test')}</button><button class="btn danger" data-act="del">${t('Ta bort')}</button></div>
  </div>`).join('')}
  <div class="row"><button class="btn primary" id="saveN">${t('Spara')}</button><span class="muted small">${t('Spara innan du testar en ny notifierare.')}</span></div>`;

  $('#addN').onclick = () => {
    const k = $('#newKind').value;
    NOTI.push({ type: k, name: '', enabled: true, cameras: [], types: [], ...JSON.parse(JSON.stringify(KIND_DEFAULTS[k])) });
    drawNotifiers();
  };
  $$('[data-i]', main).forEach(p => {
    const n = NOTI[Number(p.dataset.i)];
    p.addEventListener('input', e => {
      const k = e.target.dataset.k; if (!k) return;
      n[k] = e.target.type === 'checkbox' ? e.target.checked : (e.target.type === 'number' ? Number(e.target.value) : e.target.value);
    });
    p.addEventListener('change', e => {
      const k = e.target.dataset.k;
      if (k === 'priority') n.priority = Number(e.target.value);
      if (k === 'auth' || k === 'method' || k === 'security') { n[k] = e.target.value; drawNotifiers(); }
    });
    p.addEventListener('focusin', e => { if (e.target.matches('input[type=text][data-k]') && e.target.dataset.k !== 'name') p._last = e.target; });
    p.addEventListener('click', async e => {
      const el = e.target;
      if (el.dataset.ph) {
        const field = p._last || p.querySelector('input[data-k=url]') || p.querySelector('input[data-k=body]') || p.querySelector('input[data-k=text]');
        if (!field) return;
        const s = field.selectionStart ?? field.value.length, en = field.selectionEnd ?? field.value.length;
        field.value = field.value.slice(0, s) + el.dataset.ph + field.value.slice(en);
        n[field.dataset.k] = field.value;
        field.focus(); field.setSelectionRange(s + el.dataset.ph.length, s + el.dataset.ph.length);
        return;
      }
      if (el.classList.contains('chip') && el.parentElement.dataset.list) {
        const list = el.parentElement.dataset.list; const v = el.dataset.v;
        n[list] = n[list].includes(v) ? n[list].filter(x => x !== v) : [...n[list], v];
        el.classList.toggle('on');
      } else if (el.dataset.act === 'del') {
        if (confirm(t('Ta bort notifieraren?'))) { NOTI.splice(Number(p.dataset.i), 1); drawNotifiers(); }
      } else if (el.dataset.act === 'test') {
        if (!n.id) return toast(t('Spara först'), true);
        el.disabled = true;
        try { await api(`/api/notifiers/${n.id}/test`, { method: 'POST' }); toast(t('Testlarm skickat')); }
        catch (err) { toast(err.message, true); }
        el.disabled = false;
      }
    });
  });
  $('#saveN').onclick = async () => {
    try { await api('/api/notifiers', { method: 'PUT', body: NOTI }); await loadConfig(); toast(t('Sparat')); renderNotifiers(); }
    catch (e) { toast(e.message, true); }
  };
}

function fieldsFor(n) {
  const inp = (k, label, type = 'text', extra = '') => `<label class="f">${label}<input data-k="${k}" type="${type}" value="${esc(n[k])}" ${extra}></label>`;
  const chk = (k, label) => `<label class="check"><input type="checkbox" data-k="${k}" ${n[k] ? 'checked' : ''}> ${label}</label>`;
  const sel = (k, label, opts) => `<label class="f">${label}<select data-k="${k}">${opts.map(([v, l]) => `<option value="${v}" ${String(n[k]) === String(v) ? 'selected' : ''}>${l}</option>`).join('')}</select></label>`;
  const hint = h => `<p class="hint-box">${h}</p>`;
  const en = S.lang === 'en';
  const P = (sv, eng) => en ? eng : sv;
  if (n.type === 'pushbullet') return `
    ${inp('api_key', t('Access Token (från pushbullet.com > Settings)'), 'password', 'autocomplete="off"')}
    ${inp('device_iden', t('Enhets-id (tomt = alla enheter)'), 'text', 'placeholder="ujpah72o0sjAoRtnM0jc"')}
    ${hint(t('Enhets-id är <b>inte</b> telefonens modellnamn. Gå till pushbullet.com &gt; <b>Devices</b> och klicka på enheten. Id:t är det som står efter <code>#devices/</code> i adressfältet.'))}
    ${inp('title', t('Rubrik (tomt = standard)'), 'text', `placeholder="SynoArgus: ${P('%kamera%', '%camera%')}"`)}
    ${inp('body', t('Text (tomt = standard)'), 'text', `placeholder="${P('%meddelande%', '%message%')}"`)}
    ${phHelp('rubrik och text', t('Exempel: rubrik <code>%kamera%</code>, text <code>%vad% kl %tid%</code>.'))}
    ${chk('send_image', t('Skicka bild'))}`;
  if (n.type === 'webhook') return `
    <label class="f" style="grid-column:1/-1">${t('Adress')}<input data-k="url" type="text" value="${esc(n.url)}" placeholder="https://webhook.homey.app/<homey-id>/synoargus?tag=${P('%kamera%;%vad%', '%camera%;%what%')}"></label>
    ${phHelp('adressen', t('WEBHOOKHELP'))}
    ${sel('method', t('Metod'), ['POST', 'PUT', 'PATCH', 'GET'].map(m => [m, m]))}
    ${sel('auth', t('Autentisering'), [['none', t('Ingen')], ['bearer', t('Bearer-token')], ['basic', t('Användarnamn/lösenord')]])}
    ${n.auth === 'bearer' ? inp('token', t('Token'), 'password', 'autocomplete="off"') : ''}
    ${n.auth === 'basic' ? inp('username', t('Användarnamn')) + inp('password', t('Lösenord'), 'password', 'autocomplete="new-password"') : ''}
    ${n.method !== 'GET' ? chk('send_image', t('Skicka bild (multipart, fältet "image" + JSON i "payload")')) : ''}
    ${chk('verify_tls', t('Kontrollera HTTPS-certifikat'))}`;
  if (n.type === 'mqtt') return `
    ${inp('host', t('Broker (t.ex. Homeys IP)'))}
    ${inp('port', t('Port'), 'number')}
    ${inp('username', t('Användarnamn'))}
    ${inp('password', t('Lösenord'), 'password', 'autocomplete="new-password"')}
    ${inp('base_topic', t('Bas-topic'))}
    ${hint(t('Publiceras på <code>{t}/&lt;kamera&gt;/notification</code> som JSON.', { t: esc(n.base_topic || 'synoargus') }))}
    ${chk('send_image', t('Skicka bild (base64 i fältet "image")'))}
    ${chk('retain', t('Retain'))}`;
  if (n.type === 'email') return `
    ${inp('host', t('SMTP-server'), 'text', 'placeholder="smtp.gmail.com"')}
    ${inp('port', t('Port'), 'number')}
    ${sel('security', t('Kryptering'), [['starttls', 'STARTTLS'], ['ssl', 'SSL/TLS'], ['none', t('Ingen')]])}
    ${inp('username', t('Användarnamn'))}
    ${inp('password', t('Lösenord'), 'password', 'autocomplete="new-password"')}
    ${inp('from_addr', t('Avsändare (tomt = användarnamnet)'))}
    ${inp('to', t('Mottagare (kommaseparerat)'))}
    ${hint(t('Gmail: smtp.gmail.com, port 587, STARTTLS och ett <i>applösenord</i> (Google-konto &gt; Säkerhet &gt; Applösenord).'))}
    ${inp('subject', t('Ämne (tomt = standard)'), 'text', `placeholder="SynoArgus: ${P('%kamera%', '%camera%')}"`)}
    ${inp('body', t('Text (tomt = standard)'), 'text', `placeholder="${P('%meddelande%', '%message%')}"`)}
    ${phHelp('ämne och text')}
    ${chk('send_image', t('Skicka bild'))}`;
  if (n.type === 'telegram') return `
    ${inp('bot_token', t('Bot-token'), 'password', 'autocomplete="off"')}
    ${inp('chat_id', t('Chatt-id'), 'text', 'placeholder="123456789"')}
    ${hint(t('Skapa en bot med <b>@BotFather</b> i Telegram och kopiera token. Skicka ett meddelande till boten, öppna <code>https://api.telegram.org/bot&lt;token&gt;/getUpdates</code> och ta värdet <code>chat.id</code>. För en grupp: lägg till boten i gruppen (id börjar då med -).'))}
    ${inp('text', t('Text (tomt = standard)'), 'text', `placeholder="${P('%meddelande%', '%message%')}"`)}
    ${phHelp('texten')}
    ${chk('send_image', t('Skicka bild'))}
    ${chk('silent', t('Tyst avisering'))}`;
  if (n.type === 'ntfy') return `
    ${inp('server', t('Server'), 'text', 'placeholder="https://ntfy.sh"')}
    ${inp('topic', t('Ämne (topic)'), 'text', 'placeholder="synoargus-x7k2q9"')}
    ${hint(t('Installera ntfy från Google Play och prenumerera på samma ämne. Välj ett svårgissat ämnesnamn – på ntfy.sh kan alla som känner till namnet läsa meddelandena. Du kan också köra en egen ntfy-server.'))}
    ${sel('auth', t('Autentisering'), [['none', t('Ingen')], ['token', t('Token')], ['basic', t('Användarnamn/lösenord')]])}
    ${n.auth === 'token' ? inp('token', t('Token'), 'password', 'autocomplete="off"') : ''}
    ${n.auth === 'basic' ? inp('username', t('Användarnamn')) + inp('password', t('Lösenord'), 'password', 'autocomplete="new-password"') : ''}
    ${sel('priority', t('Prioritet'), [[1, t('1 – min')], [2, t('2 – låg')], [3, t('3 – normal')], [4, t('4 – hög')], [5, t('5 – max (bryter igenom Stör ej)')]])}
    ${inp('tags', t('Taggar (kommaseparerat, t.ex. rotating_light)'))}
    ${inp('title', t('Rubrik (tomt = standard)'), 'text', `placeholder="SynoArgus: ${P('%kamera%', '%camera%')}"`)}
    ${inp('body', t('Text (tomt = standard)'), 'text', `placeholder="${P('%meddelande%', '%message%')}"`)}
    ${phHelp('rubrik och text')}
    ${chk('send_image', t('Skicka bild'))}`;
  return '';
}

/* ---------------------------------------------------------------- inställningar */
function renderSettings() {
  const c = S.cfg; const sso = c.auth.sso;
  const cams = Object.keys(c.cameras || {});
  let zones = [];
  try { zones = Intl.supportedValuesOf('timeZone'); } catch (e) { zones = ['UTC', 'Europe/Stockholm', 'Europe/London', 'America/New_York']; }
  const models = S.models.length ? S.models : [{ name: c.detector.model, source: 'builtin' }];
  main.innerHTML = `
  <h2>${t('Inställningar')}</h2>
  <form id="setForm">
  <div class="panel"><h3>${t('Språk och tidszon')}</h3><div class="grid">
    <label class="f">${t('Språk')}<select name="language"><option value="sv" ${S.lang === 'sv' ? 'selected' : ''}>Svenska</option><option value="en" ${S.lang === 'en' ? 'selected' : ''}>English</option></select></label>
    <label class="f">${t('Tidszon')}<input name="timezone" list="tzList" value="${esc(c.timezone || 'UTC')}"><span class="hint">${t('Används för klockslag i larm och filnamn.')}</span></label>
    <datalist id="tzList">${zones.map(z => `<option value="${esc(z)}">`).join('')}</datalist>
  </div></div>

  <div class="panel"><h3>Surveillance Station</h3><div class="grid">
    <label class="f">${t('NAS-adress')}<input name="syn.url" value="${esc(c.synology.url)}"></label>
    <label class="f">${t('Användare')}<input name="syn.user" value="${esc(c.synology.user)}" autocomplete="off"></label>
    <label class="f">${t('Lösenord')}<input name="syn.password" type="password" value="${esc(c.synology.password)}" autocomplete="new-password"></label>
    <label class="f">${t('Bildkvalitet')}<select name="syn.quality">${[['high', t('Hög')], ['balanced', t('Balanserad')], ['low', t('Låg bandbredd')]].map(([v, l]) => `<option value="${v}" ${c.synology.quality === v ? 'selected' : ''}>${l}</option>`).join('')}</select><span class="hint">${t('Motsvarar strömprofilerna i Surveillance Station.')}</span></label>
    <label class="check"><input type="checkbox" name="syn.verify_tls" ${c.synology.verify_tls ? 'checked' : ''}> ${t('Kontrollera HTTPS-certifikat')}</label>
  </div></div>

  <div class="panel"><h3>${t('AI')}</h3><div class="grid">
    <label class="f">${t('Modell')}<select name="det.model">${models.map(m => `<option value="${esc(m.name)}" ${c.detector.model === m.name ? 'selected' : ''}>${esc(m.name)} (${m.source === 'user' ? t('egen') : t('inbyggd')})</option>`).join('')}</select><span class="hint">${t('Egna modeller (t.ex. YOLO26) läggs till med konverteraren, se README.')}</span></label>
    <label class="f">${t('Beräkning')}<select name="det.device">${[['AUTO', t('Automatiskt (grafikkrets om den finns)')], ['GPU', t('Grafikkrets')], ['CPU', t('Processor')]].map(([v, l]) => `<option value="${v}" ${c.detector.device === v ? 'selected' : ''}>${l}</option>`).join('')}</select></label>
  </div></div>

  <div class="panel"><h3>${t('Standardvärden för kameror')}</h3><div class="grid">
    <label class="f">${t('Säkerhet minst (%)')}<input type="number" name="def.threshold" min="10" max="95" value="${c.defaults.threshold}"></label>
    <label class="f">${t('Minsta bredd (px)')}<input type="number" name="def.min_width" min="0" value="${c.defaults.min_width}"></label>
    <label class="f">${t('Minsta höjd (px)')}<input type="number" name="def.min_height" min="0" value="${c.defaults.min_height}"></label>
    <label class="f">${t('Tyst efter larm (s)')}<input type="number" name="def.cooldown_s" min="0" value="${c.defaults.cooldown_s}"></label>
    <label class="f">${t('Minsta tid mellan analyser (s)')}<input type="number" name="def.delay_s" min="0" value="${c.defaults.delay_s}"></label>
    <label class="f">${t('Antal bilder vid rörelse')}<input type="number" name="def.max_snapshots" min="1" max="10" value="${c.defaults.max_snapshots}"></label>
    <label class="f">${t('Tid mellan bilder (ms)')}<input type="number" name="def.snapshot_interval_ms" min="100" step="100" value="${c.defaults.snapshot_interval_ms}"></label>
  </div></div>

  <div class="panel"><h3>${t('Lagring')}</h3><div class="grid">
    <label class="f">${t('Spara bilder i (dagar)')}<input type="number" name="sto.days_to_keep" min="0" value="${c.storage.days_to_keep}"><span class="hint">${t('0 = spara för alltid')}</span></label>
    <label class="check"><input type="checkbox" name="sto.save_empty" ${c.storage.save_empty ? 'checked' : ''}> ${t('Spara även analyser utan larm')}</label>
    <label class="f">${t('SynoArgus adress (för länkar i larm)')}<input name="public_url" value="${esc(c.public_url)}" placeholder="http://192.168.1.10:8686"></label>
  </div>
  <div class="row" style="margin-top:12px"><button type="button" class="btn danger" id="clearEvents">${t('Rensa alla händelser')}</button></div></div>

  <div class="panel"><h3>${t('Inloggning')}</h3><div class="grid">
    <label class="check"><input type="checkbox" name="auth.dsm_login" ${c.auth.dsm_login ? 'checked' : ''}> ${t('Logga in med DSM-konto')}</label>
    <label class="f">${t('Tillåtna DSM-konton (kommaseparerat, tomt = alla)')}<input name="auth.allowed_users" value="${esc((c.auth.allowed_users || []).join(', '))}"></label>
  </div>
  <h3 style="margin-top:16px">Synology SSO</h3>
  <p class="muted small" style="margin-top:0">${t('Installera SSO Server i DSM, aktivera OIDC och lägg till SynoArgus som app med omdirigerings-URI nedan.')}</p>
  <div class="grid">
    <label class="check"><input type="checkbox" name="sso.enabled" ${sso.enabled ? 'checked' : ''}> ${t('Aktivera SSO')}</label>
    <label class="f">${t('Issuer / Well-known-adress')}<input name="sso.issuer" value="${esc(sso.issuer)}" placeholder="https://nas:5001/webman/sso"></label>
    <label class="f">${t('Klient-id (Application ID)')}<input name="sso.client_id" value="${esc(sso.client_id)}"></label>
    <label class="f">${t('Klienthemlighet (Application Secret)')}<input name="sso.client_secret" type="password" value="${esc(sso.client_secret)}" autocomplete="new-password"></label>
    <label class="f">${t('Omdirigerings-URI')}<input name="sso.redirect_url" value="${esc(sso.redirect_url || (S.triggerBase + '/auth/sso/callback'))}"></label>
  </div></div>
  <div class="row" style="margin-bottom:14px"><button class="btn primary">${t('Spara')}</button></div>
  </form>

  <div class="panel"><h3>${t('Styr kameror (webhook)')}</h3>
    <p class="muted small" style="margin-top:0">${t('Slå på eller av analysen per kamera, t.ex. från Homey. Surveillance Station påverkas inte.')}</p>
    <div class="grid">
      <label class="f">${t('Kamera')}<select id="ctlCam"><option value="all">${t('Alla kameror')}</option>${cams.map(x => `<option value="${esc(x)}">${esc(x)}</option>`).join('')}</select></label>
      <label class="f">${t('Åtgärd')}<select id="ctlAct"><option value="off">${t('Slå av')} (off)</option><option value="on">${t('Slå på')} (on)</option><option value="toggle">${t('Växla')} (toggle)</option><option value="status">${t('Visa läge')} (status)</option></select></label>
    </div>
    <div style="margin-top:10px" id="ctlUrlBox"></div>
  </div>

  <div class="panel"><h3>${t('Säkerhetskopia')}</h3>
    <label class="check"><input type="checkbox" id="expSecrets" checked> ${t('Ta med lösenord och nycklar')}</label>
    <p class="hint-box" style="margin:6px 0 10px">${t('Filen innehåller då lösenord i klartext. Förvara den säkert.')}</p>
    <div class="row"><button type="button" class="btn" id="expBtn">⬇ ${t('Exportera')}</button>
      <label class="btn" style="display:inline-block">⬆ ${t('Importera')}<input type="file" id="impFile" accept="application/json,.json" hidden></label></div>
  </div>`;

  const ctlUrl = () => {
    const u = `${S.triggerBase}/api/control?token=${encodeURIComponent(c.trigger_token)}&camera=${encodeURIComponent($('#ctlCam').value)}&action=${$('#ctlAct').value}`;
    $('#ctlUrlBox').innerHTML = copyRow('ctlUrl', u);
  };
  $('#ctlCam').onchange = ctlUrl; $('#ctlAct').onchange = ctlUrl; ctlUrl();

  $('#clearEvents').onclick = async () => {
    if (!confirm(t('Radera alla händelser och bilder? Det går inte att ångra.'))) return;
    try { const r = await api('/api/events', { method: 'DELETE' }); toast(t('{n} händelser raderades', { n: r.deleted })); }
    catch (e) { toast(e.message, true); }
  };
  $('#expBtn').onclick = () => { location.href = `/api/export?secrets=${$('#expSecrets').checked ? 1 : 0}`; };
  $('#impFile').onchange = async e => {
    const f = e.target.files[0]; e.target.value = '';
    if (!f) return;
    let data;
    try { data = JSON.parse(await f.text()); } catch (err) { return toast(t('Filen kunde inte läsas'), true); }
    if (!confirm(t('Importera inställningar? Alla nuvarande inställningar ersätts.'))) return;
    try {
      const r = await api('/api/import', { method: 'POST', body: data });
      toast(t('Importerat: {c} kameror, {n} notifierare', { c: r.cameras, n: r.notifiers }));
      await sleep(800); location.reload();
    } catch (err) { toast(err.message, true); }
  };

  $('#setForm').addEventListener('submit', async e => {
    e.preventDefault();
    const f = e.target; const v = n => f.elements[n]; const val = n => v(n).value; const chk = n => v(n).checked;
    const issuer = val('sso.issuer').trim().replace(/\/\.well-known\/openid-configuration$/, '');
    const newLang = val('language');
    const body = {
      language: newLang, timezone: val('timezone').trim() || 'UTC',
      synology: { url: val('syn.url').trim(), user: val('syn.user').trim(), password: val('syn.password'), quality: val('syn.quality'), verify_tls: chk('syn.verify_tls') },
      detector: { model: val('det.model'), device: val('det.device') },
      defaults: Object.fromEntries(['threshold', 'min_width', 'min_height', 'cooldown_s', 'delay_s', 'max_snapshots', 'snapshot_interval_ms'].map(k => [k, Number(val('def.' + k))])),
      storage: { days_to_keep: Number(val('sto.days_to_keep')), save_empty: chk('sto.save_empty') },
      public_url: val('public_url').trim(),
      auth: { dsm_login: chk('auth.dsm_login'), allowed_users: val('auth.allowed_users'),
        sso: { enabled: chk('sso.enabled'), issuer, client_id: val('sso.client_id').trim(), client_secret: val('sso.client_secret'), redirect_url: val('sso.redirect_url').trim() } },
    };
    const btn = f.querySelector('button.primary'); btn.disabled = true;
    try {
      await api('/api/settings', { method: 'PUT', body });
      if (newLang !== S.lang) { location.reload(); return; }
      await loadConfig(); toast(t('Sparat'));
    } catch (err) { toast(err.message, true); }
    btn.disabled = false;
  });
}

/* ---------------------------------------------------------------- status */
function updateHtml(u) {
  if (!u) return '';
  return `
    <p class="small">${t('Din version: {v}', { v: esc(u.current) })}${u.latest ? ' · ' + t('Senaste version: {v}', { v: esc(u.latest) }) : ''}</p>
    ${u.error ? `<p class="err small">${esc(t('Kunde inte kontrollera: {e}', { e: u.error }))}</p>` : u.newer ? `
      <p><b class="okc">${t('Ny version finns!')}</b> ${u.url ? `<a href="${esc(u.url)}" target="_blank" rel="noopener">${t('Vad är nytt')} ↗</a>` : ''}</p>
      <p class="small">${t('Uppdatera i Container Manager: <b>Projekt</b> &gt; synoargus &gt; <b>Åtgärd</b> &gt; <b>Bygg</b> (hämtar den nya imagen).')}</p>
      ${u.notes ? `<details><summary class="small">${t('Vad är nytt')}</summary><pre class="notes">${esc(u.notes)}</pre></details>` : ''}`
      : u.latest ? `<p class="small muted">${t('Du har senaste versionen.')}</p>` : ''}`;
}

async function renderStatus() {
  main.innerHTML = `<h2>${t('Status')}</h2><div id="stOut" class="muted">${t('Hämtar…')}</div>`;
  try {
    const s = await api('/api/status');
    const d = s.detector;
    $('#stOut').className = '';
    $('#stOut').innerHTML = `
      <div class="panel"><div class="row" style="justify-content:space-between"><h3>${t('Uppdatering')}</h3><button class="btn" id="updBtn">${t('Sök efter uppdatering')}</button></div>
        <div id="updOut">${updateHtml(s.update || S.update)}</div></div>
      <div class="panel"><h3>${t('AI')}</h3>
        <p>${t('Modell <b>{m}</b> på <b>{d}</b> ({s} px)', { m: esc(d.model || '–'), d: d.device === 'GPU' ? t('grafikkretsen') : d.device === 'CPU' ? t('processorn') : '–', s: d.size })}${d.last_ms != null ? t(' · senaste analys {ms} ms', { ms: d.last_ms }) : ''}</p>
        ${d.warning ? `<p class="err small">${esc(d.warning)}</p>` : ''}
        ${d.error ? `<p class="err">${esc(d.error)}</p>` : ''}
        <p class="muted small">${t('Tillgängliga modeller: {m}', { m: d.available.map(m => esc(m.name) + ' (' + (m.source === 'user' ? t('egen') : t('inbyggd')) + ')').join(', ') || t('inga') })}</p></div>
      <div class="panel"><h3>${t('Senaste dygnet')}</h3><p>${t('{a} analyser sparade · {b} larm', { a: s.analyses_24h, b: s.alarms_24h })}</p></div>
      <div class="panel"><h3>${t('Kameror')}</h3><table><tr><th>${t('Kamera')}</th><th>${t('Senast')}</th><th>${t('Senaste larm')}</th></tr>
        ${Object.entries(s.cameras).map(([n, c]) => `<tr><td>${esc(n)}${c.busy ? ` <span class="tag">${t('analyserar')}</span>` : ''}</td><td>${c.last ? fmtTime(c.last.ts) + ` (${c.last.ms} ms)` : '–'}</td><td>${c.last_alarm ? fmtTime(c.last_alarm) : '–'}</td></tr>`).join('')}</table></div>
      <div class="panel"><h3>${t('Logg')}</h3>${s.recent.length ? `<table>${s.recent.map(r => `<tr><td class="muted small">${fmtTime(r.ts)}</td><td>${esc(r.camera)}</td><td>${esc(r.text)}</td></tr>`).join('')}</table>` : `<p class="muted">${t('Inget har hänt sedan start.')}</p>`}</div>
      <p class="muted small center">${t('{app} {v} (bygge {b}, {d})', { app: esc(S.state.app), v: esc(S.state.version), b: S.state.build, d: esc(S.state.build_date) })}</p>`;
    $('#updBtn').onclick = async () => {
      $('#updBtn').disabled = true;
      try { S.update = await api('/api/update?force=1'); $('#updOut').innerHTML = updateHtml(S.update); $('#nav button[data-tab=status]').classList.toggle('badge', !!S.update.newer); }
      catch (e) { toast(e.message, true); }
      $('#updBtn').disabled = false;
    };
  } catch (e) { $('#stOut').innerHTML = `<p class="err">${esc(e.message)}</p>`; }
}

boot();
