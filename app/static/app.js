/* SynoArgus webbgränssnitt */
'use strict';

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const sleep = ms => new Promise(r => setTimeout(r, ms));
const main = $('#main');
let S = { state: null, cfg: null, types: null, models: [], triggerBase: '', tab: 'events', sub: 'cameras', cam: null, lang: 'sv', update: null, dirty: null, prio: 0 };
try { const v = localStorage.getItem('synoargus.sub'); if (['cameras', 'notifiers', 'watch', 'modes', 'other'].includes(v)) S.sub = v; } catch (e) { /* */ }
const stoppers = new Set();  // livebild, rörelsemätare m.m. som ska stoppas när man byter vy
function stopAll() { stoppers.forEach(f => { try { f(); } catch (e) { /* */ } }); stoppers.clear(); }

/* ---------------------------------------------------------------- språk */
const EN = {
  'Händelser': 'Events', 'Kameror': 'Cameras', 'Notifiering': 'Notifications', 'Inställningar': 'Settings', 'Status': 'Status', 'Guide': 'Guide', 'Övrigt': 'Other',
  'Du har ändringar som inte är sparade. Lämna ändå?': 'You have unsaved changes. Leave anyway?',
  'Kalibrerar – larm fördröjs {s} s': 'Calibrating – alarms delayed {s} s',
  'Logga ut': 'Log out', 'Laddar…': 'Loading…', 'Kan inte nå SynoArgus: {e}': 'Cannot reach SynoArgus: {e}',
  'Bevakning: händelsens text': 'Watch: the text of the event', 'Bevakning: händelsens id': 'Watch: the id of the event',
  'Installera som app': 'Install as an app', 'SynoArgus är installerad som app.': 'SynoArgus is installed as an app.',
  'Lägg SynoArgus på hemskärmen eller skrivbordet, med egen ikon och eget fönster.': 'Put SynoArgus on the home screen or desktop, with its own icon and its own window.',
  'Installation kräver en säker anslutning (https). Du använder http nu. Lägg SynoArgus bakom en omvänd proxy med certifikat i DSM – se Guide > Övrigt.': 'Installing requires a secure connection (https). You are using http now. Put SynoArgus behind a reverse proxy with a certificate in DSM – see Guide > Other.',
  'På iPhone och iPad: tryck på Dela i Safari och välj Lägg till på hemskärmen.': 'On iPhone and iPad: tap Share in Safari and choose Add to Home Screen.',
  'Öppna webbläsarens meny och välj Installera app eller Lägg till på startskärmen.': 'Open the browser menu and choose Install app or Add to Home screen.',
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
  'Ange ditt eget DSM-konto. Det blir det enda kontot som får logga in (fler kan läggas till under Inställningar > Övrigt > Inloggning). Lämnar du fältet tomt blir tjänstekontot ovan det enda som får logga in.': 'Enter your own DSM account. It becomes the only account allowed to log in (more can be added under Settings > Other > Login). If you leave it empty, the service account above becomes the only one allowed.',
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
  'Vad ska registreras som händelse?': 'What should be registered as an event?', 'Säkerhet minst (%)': 'Minimum confidence (%)', 'Lägg till annan typ…': 'Add another type…',
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
  'Justera känslighet och tröskel, gå framför kameran och se direkt hur ofta Surveillance Station reagerar och anropar SynoArgus. Högre känslighet och lägre tröskel = reagerar lättare.': 'Adjust sensitivity and threshold, walk in front of the camera and see right away how often Surveillance Station reacts and calls SynoArgus. Higher sensitivity and lower threshold = reacts more easily.',
  'Känslighet (Sensitivity)': 'Sensitivity', 'Tröskel (Threshold)': 'Threshold', 'Spara till Surveillance Station': 'Save to Surveillance Station', 'Läs om': 'Reload',
  'Sparat i Surveillance Station': 'Saved in Surveillance Station', 'Hämtar värden…': 'Loading values…',
  'Kunde inte läsa värdena: {e}': 'Could not read the values: {e}',
  'Surveillance Station gav inga värden för den här kameran. Rörelsedetekteringen sköts kanske av kameran själv (välj "By Surveillance Station" i kamerans inställningar).': 'Surveillance Station returned no values for this camera. Motion detection may be handled by the camera itself (choose "By Surveillance Station" in the camera settings).',
  'Rörelsemätare': 'Motion meter', 'Starta mätning': 'Start measuring', 'Stoppa mätning': 'Stop measuring',
  'Reaktioner senaste minuten': 'Reactions last minute', 'Inga reaktioner ännu. Gå framför kameran.': 'No reactions yet. Walk in front of the camera.',
  'analyseras': 'analysing', 'larm': 'alarm', 'inget': 'nothing', 'fel': 'error', 'tyst period': 'quiet period', 'för tätt': 'too frequent', 'upptagen': 'busy', 'avstängd': 'disabled',
  'Kräver en Action Rule för kameran (se adressen överst).': 'Requires an Action Rule for the camera (see the address at the top).',
  // notifierare
  'Lägg till': 'Add', 'Inga notifieringar ännu.': 'No notifications yet.', 'Bara för kameror (inga valda = alla)': 'Only for cameras (none selected = all)',
  'Bara för typer (inga valda = alla)': 'Only for types (none selected = all)', 'Skicka test': 'Send test', 'Spara först': 'Save first', 'Testlarm skickat': 'Test alarm sent',
  'Ta bort notifieringen?': 'Remove the notification?', 'Spara innan du testar en ny notifiering.': 'Save before testing a new notification.',
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
  'Importera inställningar? Alla nuvarande inställningar ersätts.': 'Import settings? All current settings will be replaced.', 'Importerat: {c} kameror, {n} notifieringar': 'Imported: {c} cameras, {n} notifications',
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
  'Regeln {n} skapades {d}': 'The rule {n} was created {d}', 'men kan inte bekräftas.': 'but cannot be confirmed.',
  'Kopiera rådata': 'Copy raw data', 'Regeln {n} reagerar inte på rörelse för den här kameran.': 'The rule {n} does not react to motion for this camera.', 'Regeln {n} är inte aktiv i Home Mode. SynoArgus styr själv via lägen, så regeln bör alltid vara aktiv.': 'The rule {n} is not active in Home Mode. SynoArgus decides via modes, so the rule should always be active.',
  'Rätta regeln': 'Fix the rule', 'Regeln skapades men kan inte bekräftas': 'The rule was created but cannot be confirmed', 'Regeln uppdaterades': 'The rule was updated',
  'Börja med en s-modell. Jämför med Ta bild och analysera under Kameror – under 1 s per bild är bra. Egna modeller (t.ex. YOLO26) läggs till med konverteraren, se README.': 'Start with an s model. Compare using Take snapshot and analyse under Cameras – under 1 s per image is good. Own models (e.g. YOLO26) are added with the converter, see the README.',
  'snabbast, lägst träffsäkerhet': 'fastest, lowest accuracy', 'noggrannast, 2–3 ggr långsammare': 'most accurate, 2–3× slower', 'balanserad (rekommenderas)': 'balanced (recommended)',
  'mycket tung för en NAS': 'very heavy for a NAS', 'egen modell': 'own model',
  'Uppdatera i Container Manager: <b>Projekt</b> &gt; synoargus &gt; <b>Åtgärd</b> &gt; <b>Stoppa</b>, sedan <b>Åtgärd</b> &gt; <b>Bygg</b> (hämtar den nya imagen). Städa till sist under <b>Image</b> &gt; <b>Remove Unused Images</b>.': 'Update in Container Manager: <b>Project</b> &gt; synoargus &gt; <b>Action</b> &gt; <b>Stop</b>, then <b>Action</b> &gt; <b>Build</b> (pulls the new image). Finally clean up under <b>Image</b> &gt; <b>Remove Unused Images</b>.',
  'Aktiv i läge (inga valda = alla)': 'Active in mode (none selected = all)', 'Typer': 'Types', 'Bara i läge (inga valda = alla)': 'Only in mode (none selected = all)',
  'läge {m} – inget larm': 'mode {m} – no alarm', 'Läge': 'Mode', 'Läge: {m}': 'Mode: {m}', 'Hemma': 'Home', 'Natt': 'Night', 'Borta': 'Away',
  'Filtret {t} matchar ingen av kamerorna {c} – de letar inte efter {t}. Den här notifieringen kommer aldrig att skicka något för dem.': 'The filter {t} matches none of the cameras {c} – they do not look for {t}. This notification will never send anything for them.',
  'Filtret {t} gäller inte {c} – de letar inte efter {t}.': 'The filter {t} does not apply to {c} – they do not look for {t}.',
  'I läget {m} larmar ingen av kamerorna {c}.': 'In mode {m} none of the cameras {c} alarm.',
  'Senast ändrat: {d} ({s})': 'Last changed: {d} ({s})', 'manuellt': 'manually', 'schema': 'schedule', 'på': 'on', 'av': 'off', 'okänt': 'unknown',
  'Lägen': 'Modes', 'Läget avgör vilka kameror som larmar och vilka notifieringar som skickas (väljs under Kameror och Notifiering). Det senaste som ändrar läget gäller: manuellt, webhook, schema eller Home Mode.': 'The mode decides which cameras alarm and which notifications are sent (chosen under Cameras and Notifications). Whatever changes the mode last wins: manually, webhook, schedule or Home Mode.',
  'Nytt läge': 'New mode', '(ändra inte)': '(do not change)', 'Följ Home Mode i Surveillance Station': 'Follow Home Mode in Surveillance Station',
  'Byt läge när Home Mode slås på eller av': 'Change mode when Home Mode is turned on or off', 'Home Mode på →': 'Home Mode on →', 'Home Mode av →': 'Home Mode off →',
  'Schema': 'Schedule', 'Byt läge vid en viss tid, t.ex. Natt 01:00 och ↩ Följ Home Mode 06:00.': 'Change mode at a certain time, e.g. Night 01:00 and ↩ Follow Home Mode 06:00.',
  '↩ Följ Home Mode': '↩ Follow Home Mode', '↩ Föregående läge': '↩ Previous mode',
  'Från ett schemabyte till återgången väntar Home Mode-ändringar. ↩ Följ Home Mode går till det läge Home Mode anger just då (annars till läget före schemat), ↩ Föregående läge går tillbaka till läget före schemat. Ändrar du läget för hand eller via webhook gäller det direkt och väntan upphör.': 'From a schedule change until the return, Home Mode changes wait. ↩ Follow Home Mode goes to the mode Home Mode indicates right then (otherwise to the mode before the schedule), ↩ Previous mode goes back to the mode before the schedule. If you change the mode by hand or via webhook it applies immediately and the waiting ends.',
  'Schemat håller läget – Home Mode väntar till återgången.': 'The schedule holds the mode – Home Mode waits until the return.', 'Inget schema.': 'No schedule.',
  'Ny tid': 'New time', 'Byt läge via webhook': 'Change mode via webhook', 'Spara lägen': 'Save modes',
  'Kalibrering': 'Calibration',
  'SynoArgus mäter under en period hur kameran beter sig och föreslår känslighet och tröskel. Var 30:e sekund tas två bilder med en sekunds mellanrum: SynoArgus mäter själv hur mycket som ändras i detekteringsområdet, och AI:n avgör om något av intresse syns. Varje reaktion från Surveillance Station loggas också. Inga bilder sparas, bara statistik. Larm fungerar som vanligt under tiden.': 'SynoArgus measures over a period how the camera behaves and proposes sensitivity and threshold. Every 30 seconds two images are taken one second apart: SynoArgus measures how much changes in the detection area, and the AI decides whether anything of interest is visible. Every reaction from Surveillance Station is logged too. No images are stored, only statistics. Alarms work as usual meanwhile.',
  'Kör under ett vanligt dygn och gå gärna förbi kameran 2–3 gånger (knappen Jag går förbi nu). Ett tomt hus ger bara brus. En kamera kalibreras åt gången.': 'Run it during a normal day and walk past the camera 2–3 times (the I am walking past now button). An empty house only gives noise. One camera is calibrated at a time.',
  'Jag går förbi nu tar 3 bilder per sekund i 90 sekunder – gå genom bilden under tiden. Rörelsen mäts mellan bilder som ligger 1 sekund isär och AI:n analyserar så många bilder den hinner. Under de 90 sekunderna går kalibreringen före larm: larm från alla kameror kan komma upp till 90 sekunder sent.': 'I am walking past now takes 3 images per second for 90 seconds – walk through the picture meanwhile. Motion is measured between images 1 second apart and the AI analyses as many images as it can keep up with. During those 90 seconds the calibration goes before alarms: alarms from all cameras can arrive up to 90 seconds late.',
  'Under 90 sekunder går kalibreringen före larm. Larm från alla kameror kan komma upp till 90 sekunder sent. Starta?': 'For 90 seconds the calibration goes before alarms. Alarms from all cameras can arrive up to 90 seconds late. Start?',
  'En kalibrering pågår redan på {cam}. Stoppa den eller vänta tills den är klar.': 'A calibration is already running on {cam}. Stop it or wait until it has finished.',
  'Gå förbi kameran nu – {s} s kvar · {f} bilder, {a} analyserade': 'Walk past the camera now – {s} s left · {f} images, {a} analysed',
  'Starta kalibrering': 'Start calibration', 'Pågår: {a} – {b}': 'Running: {a} – {b}', '(analysen är långsam – bildparen glesas ut)': '(analysis is slow – image pairs are spaced out)',
'Jag går förbi nu': 'I am walking past now', 'Avbryt': 'Cancel',
  'Preliminärt resultat hittills:': 'Preliminary result so far:', 'Klar': 'Finished', 'Avbruten': 'Cancelled',
  'För lite data – låt kalibreringen gå längre eller gå förbi kameran några gånger. Krävs: minst {r} reaktioner eller {n} bildpar, och {t} med mål i rörelse för ett fullständigt förslag.': 'Not enough data – let the calibration run longer or walk past the camera a few times. Required: at least {r} reactions or {n} image pairs, and {t} with a moving target for a full proposal.',
  'Inget förslag – värdena från Surveillance Station saknas.': 'No proposal – the values from Surveillance Station are missing.', 'Nuvarande värden ser bra ut – inget att ändra.': 'The current values look good – nothing to change.',
  'Förslag': 'Proposal', 'Känslighet': 'Sensitivity', 'Tröskel': 'Threshold', 'Uppskattat: brus {a} → {b}, mål som reagerar {c} → {d}.': 'Estimated: noise {a} → {b}, targets that react {c} → {d}.',
  'Inga mål i rörelse uppmättes – förslaget bygger bara på brus och går därför bara ett steg mot mindre känsligt.': 'No moving targets were measured – the proposal is based on noise only and therefore goes just one step towards less sensitive.',
  'Få mål uppmätta – förslaget är osäkert.': 'Few targets measured – the proposal is uncertain.',
  'Dag och natt drar åt olika håll. Surveillance Station har bara ett värde för hela dygnet – förslaget väger samman båda.': 'Day and night pull in different directions. Surveillance Station has a single value for the whole day – the proposal weighs both.',
  'Uppskattning: Synology beskriver inte sin algoritm. Kontrollera med rörelsemätaren efteråt och kör gärna en ny kalibrering.': 'Estimate: Synology does not document its algorithm. Check with the motion meter afterwards and feel free to run another calibration.',
  'Använt {d}': 'Applied {d}', 'Ångra': 'Undo', 'Använd förslaget': 'Apply the proposal', 'reaktioner': 'reactions', 'med mål': 'with target', 'brus': 'noise',
  'missade mål': 'missed targets', 'bildpar': 'image pairs', 'mål i rörelse': 'moving targets', 'Reaktioner per timme': 'Reactions per hour',
  'Bildpar': 'Image pairs', 'Mål': 'Targets', 'Reaktioner': 'Reactions', 'Brus': 'Noise', 'Dag': 'Day', 'Ny kalibrering': 'New calibration',
  'Avbryta kalibreringen? Rapporten byggs på det som hunnit samlas in.': 'Cancel the calibration? The report is built from what has been collected.',
  'Spara de föreslagna värdena i Surveillance Station?': 'Save the proposed values in Surveillance Station?', 'Tidigare värden återställda': 'Previous values restored',
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
    [en ? '%camera%' : '%kamera%', t('Kamerans namn'), en ? 'Backyard' : 'Baksidan'],
    [en ? '%what%' : '%vad%', t('Vad som hittades'), en ? 'Person, Cat' : 'Person, Katt'],
    [en ? '%what_en%' : '%vad_en%', t('Vad som hittades (engelska)'), 'person, cat'],
    [en ? '%count%' : '%antal%', t('Antal träffar'), '3'],
    [en ? '%message%' : '%meddelande%', t('Hela meddelandet'), en ? 'Backyard: 2 people, Cat' : 'Baksidan: 2 personer, Katt'],
    [en ? '%confidence%' : '%säkerhet%', t('Högsta säkerhet i %'), '87'],
    [en ? '%time%' : '%tid%', t('Klockslag'), '22:58:14'],
    [en ? '%date%' : '%datum%', t('Datum'), '2026-11-08'],
    [en ? '%image%' : '%bild%', t('Länk till bilden i SynoArgus'), 'http://…/captures/…jpg'],
    [en ? '%event%' : '%händelse%', t('Bevakning: händelsens text'), en ? 'Leaving the zone, towards the camera' : 'Lämnar zonen, mot kameran'],
    [en ? '%event_id%' : '%händelse_id%', t('Bevakning: händelsens id'), 'leave_toward'],
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
  setPriority(S.state.priority?.until);
  setWatchPill(S.state.watch);
  render();
}

function translateChrome() {
  $$('#nav button, #subnav button').forEach(b => { b.textContent = t(b.dataset.label); });
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

/* ---------------------------------------------------------------- osparade ändringar */
function isDirty() { try { return !!(S.dirty && S.dirty()); } catch (e) { return false; } }
function confirmLeave() {
  if (!isDirty()) return true;
  if (!confirm(t('Du har ändringar som inte är sparade. Lämna ändå?'))) return false;
  S.dirty = null; return true;
}
window.addEventListener('beforeunload', e => { if (isDirty()) { e.preventDefault(); e.returnValue = ''; } });
function go(tab, sub) {
  if (!confirmLeave()) return;
  S.tab = tab;
  if (sub) { S.sub = sub; try { localStorage.setItem('synoargus.sub', sub); } catch (e) { /* */ } }
  render(); window.scrollTo(0, 0);
}

/* ---------------------------------------------------------------- "Jag går förbi nu" i headern */
function setPriority(until) { S.prio = until || 0; tickPriority(); }
function tickPriority() {
  const pill = $('#prioPill'); if (!pill) return;
  const left = Math.round(S.prio - Date.now() / 1000);
  pill.hidden = !(S.state?.logged_in && left > 0);
  if (left > 0) {
    pill.innerHTML = `<span class="l">${esc(t('Kalibrerar – larm fördröjs {s} s', { s: left }))}</span><span class="s">⏳ ${left} s</span>`;
    pill.title = t('Kalibrerar – larm fördröjs {s} s', { s: left });
  }
}
setInterval(tickPriority, 1000);

function placeSubnav() { const h = $('header.top'); if (h) $('#subnav').style.top = h.offsetHeight + 'px'; }
window.addEventListener('resize', placeSubnav);

function render() {
  stopAll();
  S.dirty = null;
  const st = S.state;
  $('#nav').hidden = !st.logged_in;
  $('#subnav').hidden = !(st.logged_in && st.setup_done && S.tab === 'settings');
  placeSubnav();
  $('#who').hidden = !st.logged_in;
  if (st.logged_in) $('#whoName').textContent = st.user;
  updateModePill(st.logged_in ? (S.cfg?.mode || st.mode) : null);
  if (!st.setup_done) return renderSetup();
  if (!st.logged_in) return renderLogin();
  $$('#nav button').forEach(b => b.classList.toggle('active', b.dataset.tab === S.tab));
  $$('#subnav button').forEach(b => b.classList.toggle('active', b.dataset.sub === S.sub));
  if (S.tab === 'settings') return ({ cameras: renderCameras, notifiers: renderNotifiers, watch: renderWatch, modes: renderModes, other: renderSettings })[S.sub]();
  ({ events: renderEvents, status: renderStatus, guide: renderGuide })[S.tab]();
}

$$('#nav button').forEach(b => b.addEventListener('click', () => go(b.dataset.tab)));
$$('#subnav button').forEach(b => b.addEventListener('click', () => go('settings', b.dataset.sub)));
$('#modePill').addEventListener('click', () => go('status'));
$('#watchPill').addEventListener('click', () => { S.wcam = S.state.watch || S.wcam; go('settings', 'watch'); });
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
      <p class="muted small" style="margin:0">${t('Ange ditt eget DSM-konto. Det blir det enda kontot som får logga in (fler kan läggas till under Inställningar > Övrigt > Inloggning). Lämnar du fältet tomt blir tjänstekontot ovan det enda som får logga in.')}</p>
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
      S.tab = 'settings'; S.sub = 'cameras';
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
          <div class="muted small">${[ev.ms ? ev.ms + ' ms' : '', ev.notified?.length ? ev.notified.map(n => `<span class="${n.ok ? 'okc' : 'err'}" title="${esc(n.error || '')}">${esc(n.name)} ${n.ok ? '✓' : '✗'}</span>`).join(' ') : ''].filter(Boolean).join(' · ')}</div>
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
  $$('.camlist .chip').forEach(b => b.onclick = () => { if (b.dataset.cam === S.cam || !confirmLeave()) return; S.cam = b.dataset.cam; render(); });
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
    <h3>${t('Vad ska registreras som händelse?')}</h3>
    <div class="muted small" style="margin-bottom:4px">${t('Aktiv i läge (inga valda = alla)')}</div>
    <div class="chips" id="cModes" style="margin-bottom:12px">${modeList().map(m => `<button class="chip ${(cam.modes || []).includes(m.id) ? 'on' : ''}" data-m="${esc(m.id)}">${esc(m.name)}</button>`).join('')}</div>
    <div class="muted small" style="margin-bottom:4px">${t('Typer')}</div>
    <div class="chips" id="cTypes">${common.map(x => `<button class="chip ${cam.types.includes(x) ? 'on' : ''}" data-t="${x}">${esc(tname(x))}</button>`).join('')}</div>
    <div class="row" style="margin-top:8px"><select id="cOther" style="width:auto"><option value="">${t('Lägg till annan typ…')}</option>${others.map(x => `<option value="${x}">${esc(tname(x))}</option>`).join('')}</select>
      <span id="cOtherList"></span></div>
    <div class="grid" style="margin-top:14px">
      <label class="f">${t('Säkerhet minst (%)')}<input type="number" id="cThr" min="10" max="95" value="${cam.threshold ?? ''}" placeholder="${d.threshold}"></label>
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
    <p class="muted small" style="margin-top:0">${t('Justera känslighet och tröskel, gå framför kameran och se direkt hur ofta Surveillance Station reagerar och anropar SynoArgus. Högre känslighet och lägre tröskel = reagerar lättare.')}</p>
    <div id="mdValues" class="muted small">${t('Hämtar värden…')}</div>
    <h3 style="margin-top:16px">${t('Rörelsemätare')}</h3>
    <p class="muted small" style="margin-top:0">${t('Kräver en Action Rule för kameran (se adressen överst).')}</p>
    <div class="meter">
      <div class="meter-count"><span id="mCount">–</span><small>${t('Reaktioner senaste minuten')}</small></div>
      <button class="btn" id="mToggle">${t('Starta mätning')}</button>
    </div>
    <div id="mList" class="small"></div>
  </div>
  <div class="panel" id="calPanel"><h3>${t('Kalibrering')}</h3><div id="calBody" class="muted small">${t('Hämtar…')}</div></div>
  <div class="row"><button class="btn primary" id="saveCam">${t('Spara')}</button><button class="btn danger" id="delCam">${t('Ta bort kameran')}</button></div>`;

  const toggleType = x => { cam.types = cam.types.includes(x) ? cam.types.filter(y => y !== x) : [...cam.types, x]; };
  const drawOther = () => { $('#cOtherList').innerHTML = cam.types.filter(x => !common.includes(x)).map(x => `<button class="chip on" data-t="${x}">${esc(tname(x))} ✕</button>`).join(' '); };
  drawOther();
  $('#cTypes').onclick = e => { const x = e.target.dataset.t; if (!x) return; toggleType(x); e.target.classList.toggle('on'); };
  $('#cOther').onchange = e => { const x = e.target.value; if (x && !cam.types.includes(x)) { cam.types.push(x); drawOther(); } e.target.value = ''; };
  $('#cOtherList').onclick = e => { const x = e.target.dataset.t; if (x) { toggleType(x); drawOther(); } };

  cam.modes = cam.modes || [];
  $('#cModes').onclick = e => { const m = e.target.dataset.m; if (!m) return; cam.modes = cam.modes.includes(m) ? cam.modes.filter(x => x !== m) : [...cam.modes, m]; e.target.classList.toggle('on'); };
  const collect = () => {
    return {
      enabled: $('#cEnabled').checked, types: cam.types,
      threshold: num($('#cThr').value),
      min_width: num($('#cMinW').value), min_height: num($('#cMinH').value),
      cooldown_s: num($('#cCool').value), delay_s: num($('#cDelay').value),
      max_snapshots: num($('#cMax').value), wait_ms: num($('#cWait').value) || 0, zones: cam.zones, modes: cam.modes,
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
    const storedTxt = r.stored ? t('Regeln {n} skapades {d}', { n: esc(r.stored.name), d: fmtTime(r.stored.created) }) : '';
    if (r.error) {
      box.className = 'arbox small';
      box.innerHTML = (storedTxt ? `<span>${storedTxt}${r.stored.confirmed ? '' : ' – ' + t('men kan inte bekräftas.')}</span><br>` : '') + `<span class="err">${esc(r.error)}</span>`;
      return;
    }
    const rawId = 'arRaw' + Math.random().toString(36).slice(2, 8);
    const raw = `<details class="small rawbox"><summary class="muted">${t('Visa rådata från Surveillance Station')}</summary>
      <div class="row" style="margin:6px 0"><button type="button" class="btn" data-copy="${rawId}">${t('Kopiera rådata')}</button></div>
      <pre class="notes raw" id="${rawId}">${esc(JSON.stringify(r.raw, null, 2))}</pre></details>`;
    const good = r.rules.filter(x => x.current && x.event_ok && x.home_ok !== false);
    const badEvt = r.rules.filter(x => !x.event_ok);
    const badHome = r.rules.filter(x => x.event_ok && x.home_ok === false);
    const oldUrl = r.rules.filter(x => !x.current && x.event_ok && x.home_ok !== false);
    const st = x => x.enabled === false || x.enabled === 0 ? ` <span class="tag">${t('avstängd')}</span>` : '';
    let html = '';
    if (badEvt.length) html = `<span class="err">${t('Regeln {n} reagerar inte på rörelse för den här kameran.', { n: esc(badEvt.map(x => x.name).join(', ')) })}</span> <button class="btn" id="arFix">${t('Rätta regeln')}</button>`;
    else if (badHome.length) html = `<span class="warn">${t('Regeln {n} är inte aktiv i Home Mode. SynoArgus styr själv via lägen, så regeln bör alltid vara aktiv.', { n: esc(badHome.map(x => x.name).join(', ')) })}</span> <button class="btn" id="arFix">${t('Rätta regeln')}</button>`;
    else if (good.length) html = `<span class="okc">✓ ${t('Regel finns i Surveillance Station: {n}', { n: esc(good.map(x => x.name).join(', ')) })}</span>${good.map(st).join('')}`;
    else if (oldUrl.length) html = `<span class="err">${t('Regeln {n} pekar på en gammal adress.', { n: esc(oldUrl.map(x => x.name).join(', ')) })}</span> <button class="btn" id="arUpdate">${t('Uppdatera adressen')}</button>`;
    else html = `<span>${t('Ingen regel för kameran i Surveillance Station.')}</span> <button class="btn" id="arCreate">${t('Skapa regel')}</button>`;
    box.className = 'arbox small'; box.innerHTML = html + raw;
    const run = async (action, btn) => {
      btn.disabled = true;
      try {
        const res = await api(`/api/cameras/${enc}/actionrule`, { method: 'POST', body: { action } });
        if (action === 'create') toast(res.confirmed ? t('Regeln skapades') : t('Regeln skapades men kan inte bekräftas'));
        else toast(t('Regeln uppdaterades'));
      } catch (e) { toast(e.message, true); }
      loadAr();
    };
    $('#arUpdate') && ($('#arUpdate').onclick = e => run('update', e.target));
    $('#arFix') && ($('#arFix').onclick = e => run('fix', e.target));
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

  // ---- kalibrering
  let calTimer = null;
  const stopCal = () => { if (calTimer) { clearTimeout(calTimer); calTimer = null; } };
  stoppers.add(stopCal);
  const loadCal = async () => {
    stopCal();
    const body = $('#calBody'); if (!body) return;
    let r, active;
    try { ({ run: r, active } = await api(`/api/cameras/${enc}/calibration`)); }
    catch (e) { body.innerHTML = `<span class="err">${esc(e.message)}</span>`; return; }
    if (!$('#calBody')) return;
    body.className = 'small';
    body.innerHTML = calHtml(r, active, cam.name);
    if (r?.walk) setPriority(r.walk.until);
    body.onclick = async e => {
      const a = e.target.dataset.cal; if (!a) return;
      if (a === 'stop' && !confirm(t('Avbryta kalibreringen? Rapporten byggs på det som hunnit samlas in.'))) return;
      if (a === 'apply' && !confirm(t('Spara de föreslagna värdena i Surveillance Station?'))) return;
      if (a === 'walk' && !confirm(t('Under 90 sekunder går kalibreringen före larm. Larm från alla kameror kan komma upp till 90 sekunder sent. Starta?'))) return;
      e.target.disabled = true;
      try {
        await api(`/api/cameras/${enc}/calibration`, { method: 'POST', body: { action: a, hours: Number(($('#calHours') || {}).value || 24) } });
        if (a === 'apply') toast(t('Sparat i Surveillance Station')); if (a === 'undo') toast(t('Tidigare värden återställda'));
        if (a === 'apply' || a === 'undo') loadMd();
      } catch (err) { toast(err.message, true); }
      loadCal();
    };
    if (r && r.status === 'running') calTimer = setTimeout(loadCal, r.walk ? 2000 : 15000);
  };
  loadCal();

  // ---- rörelsemätare
  let meter = null;
  const resLabel = x => {
    if (x.result === 'accepted') return x.outcome === 'alarm' ? `<span class="tag ok">${t('larm')}${x.types?.length ? ': ' + x.types.map(tname).join(', ') : ''}</span>` : x.outcome === 'none' ? `<span class="tag">${t('inget')}</span>` : x.outcome === 'error' ? `<span class="tag err">${t('fel')}</span>` : `<span class="tag">${t('analyseras')}</span>`;
    if (x.result === 'mode') return `<span class="tag">${t('läge {m} – inget larm', { m: esc(x.mode || '') })}</span>`;
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
          $('#mList').innerHTML = list.length ? `<table>${list.slice(-12).reverse().map(x => `<tr><td class="muted">${fmtClock(x.ts)}</td><td>${resLabel(x)}</td></tr>`).join('')}</table>` : `<p class="muted">${t('Inga reaktioner ännu. Gå framför kameran.')}</p>`;
        } catch (e) { $('#mList').innerHTML = `<p class="err">${esc(e.message)}</p>`; }
        await sleep(1000);
      }
    })();
  };

  let snap = JSON.stringify(collect());
  S.dirty = () => !!$('#saveCam') && JSON.stringify(collect()) !== snap;
  $('#saveCam').onclick = async () => {
    try { const body = collect(); await api('/api/cameras/' + enc, { method: 'PUT', body }); snap = JSON.stringify(body); await loadConfig(); toast(t('Sparat')); }
    catch (e) { toast(e.message, true); }
  };
  $('#delCam').onclick = async () => {
    if (!confirm(t('Ta bort {name} från SynoArgus? (Kameran i Surveillance Station påverkas inte.)', { name: cam.name }))) return;
    S.dirty = null;
    await api('/api/cameras/' + enc, { method: 'DELETE' }); await loadConfig(); S.cam = null; render();
  };
}

/* ---------------------------------------------------------------- lägen */
const DEFAULT_MODE_NAMES = { home: 'Hemma', night: 'Natt', away: 'Borta' };
function modeName(id) {
  const m = (S.cfg?.modes || []).find(x => x.id === id);
  return (m && m.name) || (DEFAULT_MODE_NAMES[id] ? t(DEFAULT_MODE_NAMES[id]) : id);
}
function modeList() { return (S.cfg?.modes || []).map(m => ({ id: m.id, name: modeName(m.id) })); }
function updateModePill(info) {
  const pill = $('#modePill'); if (!pill) return;
  if (!info) { pill.hidden = true; return; }
  pill.hidden = false; pill.textContent = modeName(info.current);
  pill.title = t('Läge');
}
async function setMode(id) {
  try { const info = await api('/api/mode/set', { method: 'POST', body: { mode: id } }); S.cfg.mode = info; updateModePill(info); toast(t('Läge: {m}', { m: modeName(id) })); return info; }
  catch (e) { toast(e.message, true); }
}

function notifierWarnings(n) {
  const cams = S.cfg.cameras || {};
  const targets = (n.cameras && n.cameras.length ? n.cameras : Object.keys(cams)).filter(c => cams[c]);
  const out = [];
  for (const ty of n.types || []) {
    const miss = targets.filter(c => !(cams[c].types || []).includes(ty));
    if (targets.length && miss.length === targets.length) out.push(t('Filtret {t} matchar ingen av kamerorna {c} – de letar inte efter {t}. Den här notifieringen kommer aldrig att skicka något för dem.', { t: tname(ty), c: miss.join(', ') }));
    else if (miss.length) out.push(t('Filtret {t} gäller inte {c} – de letar inte efter {t}.', { t: tname(ty), c: miss.join(', ') }));
  }
  for (const m of n.modes || []) {
    const miss = targets.filter(c => (cams[c].modes || []).length && !cams[c].modes.includes(m));
    if (targets.length && miss.length === targets.length) out.push(t('I läget {m} larmar ingen av kamerorna {c}.', { m: modeName(m), c: miss.join(', ') }));
  }
  return out.map(x => `<p class="warnbox">⚠ ${esc(x)}</p>`).join('');
}

/* ---------------------------------------------------------------- kalibrering */
const pct = v => v == null ? '–' : Math.round(v * 100) + ' %';
function calHtml(r, active, camName) {
  const busy = active && active !== camName;
  if (!r || (busy && r.status !== 'running' && !r.report)) r = null;
  const startRow = busy
    ? `<p class="warnbox">⚠ ${esc(t('En kalibrering pågår redan på {cam}. Stoppa den eller vänta tills den är klar.', { cam: active }))}</p>
       <div class="row"><button class="btn primary" disabled>${t('Starta kalibrering')}</button></div>`
    : `<div class="row"><select id="calHours" style="width:auto">${[12, 24, 48, 72].map(h => `<option value="${h}" ${h === 24 ? 'selected' : ''}>${h} h</option>`).join('')}</select>
      <button class="btn primary" data-cal="start">${t('Starta kalibrering')}</button></div>`;
  if (!r) return `
    <p class="muted" style="margin-top:0">${t('SynoArgus mäter under en period hur kameran beter sig och föreslår känslighet och tröskel. Var 30:e sekund tas två bilder med en sekunds mellanrum: SynoArgus mäter själv hur mycket som ändras i detekteringsområdet, och AI:n avgör om något av intresse syns. Varje reaktion från Surveillance Station loggas också. Inga bilder sparas, bara statistik. Larm fungerar som vanligt under tiden.')}</p>
    <p class="muted">${t('Jag går förbi nu tar 3 bilder per sekund i 90 sekunder – gå genom bilden under tiden. Rörelsen mäts mellan bilder som ligger 1 sekund isär och AI:n analyserar så många bilder den hinner. Under de 90 sekunderna går kalibreringen före larm: larm från alla kameror kan komma upp till 90 sekunder sent.')}</p>
    <p class="muted">${t('Kör under ett vanligt dygn och gå gärna förbi kameran 2–3 gånger (knappen Jag går förbi nu). Ett tomt hus ger bara brus. En kamera kalibreras åt gången.')}</p>
    ${startRow}`;
  const rep = r.report || {};
  const now = Date.now() / 1000;
  let head = '';
  if (r.status === 'running') {
    const prog = Math.min(1, (now - r.started) / (r.ends - r.started));
    const walking = r.walk && r.walk.until > now;
    head = `
      <div class="progress"><div style="width:${Math.round(prog * 100)}%"></div></div>
      <p>${t('Pågår: {a} – {b}', { a: fmtTime(r.started), b: fmtTime(r.ends) })}${r.slow ? ` <span class="warn">${t('(analysen är långsam – bildparen glesas ut)')}</span>` : ''}</p>
      <div class="row">${walking ? `<span class="tag ok">${t('Gå förbi kameran nu – {s} s kvar · {f} bilder, {a} analyserade', { s: Math.round(r.walk.until - now), f: r.walk.frames, a: r.walk.analysed })}</span>` : `<button class="btn" data-cal="walk">🚶 ${t('Jag går förbi nu')}</button>`}
        <button class="btn danger" data-cal="stop">${t('Avbryt')}</button></div>
      <p class="muted" style="margin:6px 0 0">${t('Jag går förbi nu tar 3 bilder per sekund i 90 sekunder – gå genom bilden under tiden. Rörelsen mäts mellan bilder som ligger 1 sekund isär och AI:n analyserar så många bilder den hinner. Under de 90 sekunderna går kalibreringen före larm: larm från alla kameror kan komma upp till 90 sekunder sent.')}</p>
      <p class="muted" style="margin-bottom:4px">${t('Preliminärt resultat hittills:')}</p>`;
  } else {
    head = `<p><b>${r.status === 'done' ? t('Klar') : t('Avbruten')}</b> · ${fmtTime(r.started)} – ${fmtTime(rep.ends && rep.ends < now ? rep.ends : now)}</p>`;
  }
  const maxH = Math.max(1, ...(rep.hours || [0]));
  const bars = (rep.hours || []).map((v, h) => `<div class="hbar" title="${String(h).padStart(2, '0')}:00 – ${v}"><div style="height:${Math.round(v / maxH * 100)}%"></div><span>${h % 6 === 0 ? h : ''}</span></div>`).join('');
  const dn = (lab, x) => x ? `<tr><td>${lab}</td><td>${x.pairs}</td><td>${x.targets}</td><td>${x.reactions}</td><td>${x.reactions ? Math.round(x.noise_reactions / x.reactions * 100) + ' %' : '–'}</td></tr>` : '';
  const p = rep.proposal;
  let prop = '';
  if (!rep.enough) prop = `<p class="warnbox">⚠ ${t('För lite data – låt kalibreringen gå längre eller gå förbi kameran några gånger. Krävs: minst {r} reaktioner eller {n} bildpar, och {t} med mål i rörelse för ett fullständigt förslag.', { r: rep.limits?.min_reactions, n: rep.limits?.min_noise, t: rep.limits?.min_targets })}</p>`;
  else if (!p) prop = `<p class="muted">${t('Inget förslag – värdena från Surveillance Station saknas.')}</p>`;
  else if (p.unchanged) prop = `<p class="okc">✓ ${t('Nuvarande värden ser bra ut – inget att ändra.')}</p>`;
  else {
    const cur = rep.current;
    prop = `
      <div class="proposal">
        <div><span class="muted">${t('Förslag')}</span><b>${t('Känslighet')} ${cur.sensitivity} → ${p.sensitivity} · ${t('Tröskel')} ${cur.threshold} → ${p.threshold}</b></div>
        <div class="muted">${t('Uppskattat: brus {a} → {b}, mål som reagerar {c} → {d}.', { a: pct(p.noise_now), b: pct(p.noise), c: pct(p.recall_now), d: pct(p.recall) })}</div>
        ${p.only_noise ? `<p class="warnbox">⚠ ${t('Inga mål i rörelse uppmättes – förslaget bygger bara på brus och går därför bara ett steg mot mindre känsligt.')}</p>` : ''}
        ${!rep.full && !p.only_noise ? `<p class="warnbox">⚠ ${t('Få mål uppmätta – förslaget är osäkert.')}</p>` : ''}
        ${rep.day_night_conflict ? `<p class="warnbox">⚠ ${t('Dag och natt drar åt olika håll. Surveillance Station har bara ett värde för hela dygnet – förslaget väger samman båda.')}</p>` : ''}
        <p class="muted small" style="margin:6px 0 0">${t('Uppskattning: Synology beskriver inte sin algoritm. Kontrollera med rörelsemätaren efteråt och kör gärna en ny kalibrering.')}</p>
        ${r.status !== 'running' ? `<div class="row" style="margin-top:8px">${r.applied ? `<span class="tag ok">${t('Använt {d}', { d: fmtTime(r.applied.ts) })}</span><button class="btn" data-cal="undo">${t('Ångra')}</button>` : `<button class="btn primary" data-cal="apply">${t('Använd förslaget')}</button>`}</div>` : ''}
      </div>`;
  }
  return head + `
    <div class="calstats">
      <div><b>${rep.reactions ?? 0}</b><span>${t('reaktioner')}</span></div>
      <div><b>${rep.reactions_target ?? 0}</b><span>${t('med mål')}</span></div>
      <div><b>${pct(rep.noise_share)}</b><span>${t('brus')}</span></div>
      <div><b>${rep.missed ?? 0}</b><span>${t('missade mål')}</span></div>
      <div><b>${rep.pairs ?? 0}</b><span>${t('bildpar')}</span></div>
      <div><b>${rep.target_pairs ?? 0}</b><span>${t('mål i rörelse')}</span></div>
    </div>
    <div class="muted small">${t('Reaktioner per timme')}</div>
    <div class="hbars">${bars}</div>
    <table class="small"><tr><th></th><th>${t('Bildpar')}</th><th>${t('Mål')}</th><th>${t('Reaktioner')}</th><th>${t('Brus')}</th></tr>${dn(t('Dag'), rep.day)}${dn(t('Natt'), rep.night)}</table>
    ${prop}
    ${r.status !== 'running' ? (busy ? startRow.replace('<div class="row">', '<div class="row" style="margin-top:10px">') : `<div class="row" style="margin-top:10px"><button class="btn" data-cal="clear">${t('Ny kalibrering')}</button></div>`) : ''}`;
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
  const snap = JSON.stringify(NOTI);
  drawNotifiers();
  S.dirty = () => !!$('#saveN') && JSON.stringify(NOTI) !== snap;
}

function drawNotifiers() {
  const cams = Object.keys(S.cfg.cameras || {});
  const types = [...new Set([...S.types.common, ...Object.values(S.cfg.cameras || {}).flatMap(c => c.types)])];
  main.innerHTML = `
  <div class="row" style="justify-content:space-between"><h2>${t('Notifiering')}</h2>
    <div class="row"><select id="newKind" style="width:auto">${Object.entries(KIND_NAMES).map(([k, v]) => `<option value="${k}">${v}</option>`).join('')}</select><button class="btn" id="addN">${t('Lägg till')}</button></div></div>
  ${NOTI.length ? '' : `<p class="muted">${t('Inga notifieringar ännu.')}</p>`}
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
      <div><div class="muted small">${t('Bara i läge (inga valda = alla)')}</div><div class="chips" data-list="modes">${modeList().map(m => `<button class="chip ${(n.modes || []).includes(m.id) ? 'on' : ''}" data-v="${esc(m.id)}">${esc(m.name)}</button>`).join('')}</div></div>
    </div>
    <div class="nwarn">${notifierWarnings(n)}
    </div>
    <div class="row" style="margin-top:12px"><button class="btn" data-act="test">${t('Skicka test')}</button><button class="btn danger" data-act="del">${t('Ta bort')}</button></div>
  </div>`).join('')}
  <div class="row"><button class="btn primary" id="saveN">${t('Spara')}</button><span class="muted small">${t('Spara innan du testar en ny notifiering.')}</span></div>`;

  $('#addN').onclick = () => {
    const k = $('#newKind').value;
    NOTI.push({ type: k, name: '', enabled: true, cameras: [], types: [], modes: [], ...JSON.parse(JSON.stringify(KIND_DEFAULTS[k])) });
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
        n[list] = n[list] || [];
        n[list] = n[list].includes(v) ? n[list].filter(x => x !== v) : [...n[list], v];
        el.classList.toggle('on');
        const w = p.querySelector('.nwarn'); if (w) w.innerHTML = notifierWarnings(n);
      } else if (el.dataset.act === 'del') {
        if (confirm(t('Ta bort notifieringen?'))) { NOTI.splice(Number(p.dataset.i), 1); drawNotifiers(); }
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
    try { await api('/api/notifiers', { method: 'PUT', body: NOTI }); await loadConfig(); toast(t('Sparat')); render(); }
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
function modelHint(name) {
  const n = name.toLowerCase();
  if (/(tiny|nano|[^a-z]n$|\dn$)/.test(n)) return t('snabbast, lägst träffsäkerhet');
  if (/(\dm$|_m$|medium)/.test(n)) return t('noggrannast, 2–3 ggr långsammare');
  if (/(\ds$|_s$|small)/.test(n)) return t('balanserad (rekommenderas)');
  if (/(\dl$|_l$|\dx$|_x$)/.test(n)) return t('mycket tung för en NAS');
  return t('egen modell');
}
function renderSettings() {
  const c = S.cfg; const sso = c.auth.sso;
  const cams = Object.keys(c.cameras || {});
  let zones = [];
  try { zones = Intl.supportedValuesOf('timeZone'); } catch (e) { zones = ['UTC', 'Europe/Stockholm', 'Europe/London', 'America/New_York']; }
  const models = S.models.length ? S.models : [{ name: c.detector.model, source: 'builtin' }];
  main.innerHTML = `
  <h2>${t('Övrigt')}</h2>
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
    <label class="f">${t('Modell')}<select name="det.model">${models.map(m => `<option value="${esc(m.name)}" ${c.detector.model === m.name ? 'selected' : ''}>${esc(m.name)} – ${modelHint(m.name)} (${m.source === 'user' ? t('egen') : t('inbyggd')})</option>`).join('')}</select><span class="hint">${t('Börja med en s-modell. Jämför med Ta bild och analysera under Kameror – under 1 s per bild är bra. Egna modeller (t.ex. YOLO26) läggs till med konverteraren, se README.')}</span></label>
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

  <div class="panel"><h3>${t('Installera som app')}</h3>
    <p class="muted small" style="margin-top:0">${t('Lägg SynoArgus på hemskärmen eller skrivbordet, med egen ikon och eget fönster.')}</p>
    <div id="pwaBox"></div>
  </div>

  <div class="panel"><h3>${t('Säkerhetskopia')}</h3>
    <label class="check"><input type="checkbox" id="expSecrets" checked> ${t('Ta med lösenord och nycklar')}</label>
    <p class="hint-box" style="margin:6px 0 10px">${t('Filen innehåller då lösenord i klartext. Förvara den säkert.')}</p>
    <div class="row"><button type="button" class="btn" id="expBtn">⬇ ${t('Exportera')}</button>
      <label class="btn" style="display:inline-block">⬆ ${t('Importera')}<input type="file" id="impFile" accept="application/json,.json" hidden></label></div>
  </div>`;

  drawPwa();
  const form = $('#setForm');
  const ser = () => [...form.elements].map(x => x.type === 'checkbox' ? x.checked : x.value).join('\u0001');
  let snap = ser();
  S.dirty = () => !!$('#setForm') && ser() !== snap;
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
    S.dirty = null;
    try {
      const r = await api('/api/import', { method: 'POST', body: data });
      toast(t('Importerat: {c} kameror, {n} notifieringar', { c: r.cameras, n: r.notifiers }));
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
      snap = ser();
      if (newLang !== S.lang) { S.dirty = null; location.reload(); return; }
      await loadConfig(); toast(t('Sparat'));
    } catch (err) { toast(err.message, true); }
    btn.disabled = false;
  });
}

function renderModes() {
  main.innerHTML = `<h2>${t('Lägen')}</h2><div class="panel" id="modesPanel"></div>`;
  drawModesPanel();
}

function drawModesPanel() {
  const c = S.cfg;
  const M = JSON.parse(JSON.stringify(c.modes || []));
  const A = JSON.parse(JSON.stringify(c.mode_auto || { homemode: {}, schedule: [] }));
  A.homemode = A.homemode || {}; A.schedule = A.schedule || [];
  const DAYS = S.lang === 'en' ? ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'] : ['Mån', 'Tis', 'Ons', 'Tor', 'Fre', 'Lör', 'Sön'];
  const box = $('#modesPanel');
  const nm = m => m.name || (DEFAULT_MODE_NAMES[m.id] ? t(DEFAULT_MODE_NAMES[m.id]) : m.id);
  const opts = (sel, empty, special) => (empty ? `<option value="">${t('(ändra inte)')}</option>` : '') + M.map(m => `<option value="${esc(m.id)}" ${sel === m.id ? 'selected' : ''}>${esc(nm(m))}</option>`).join('')
    + (special ? [['@homemode', t('↩ Följ Home Mode')], ['@previous', t('↩ Föregående läge')]].map(([v, l]) => `<option value="${v}" ${sel === v ? 'selected' : ''}>${l}</option>`).join('') : '');
  const snap = JSON.stringify([M, A]);
  S.dirty = () => !!$('#mSave') && JSON.stringify([M, A]) !== snap;
  const draw = () => {
    box.innerHTML = `
    <p class="muted small" style="margin-top:0">${t('Läget avgör vilka kameror som larmar och vilka notifieringar som skickas (väljs under Kameror och Notifiering). Det senaste som ändrar läget gäller: manuellt, webhook, schema eller Home Mode.')}</p>
    <div class="modelist">${M.map((m, i) => `<div class="row"><input data-mi="${i}" value="${esc(m.name)}" placeholder="${esc(nm({ id: m.id }))}" style="max-width:240px"><span class="muted small">id: ${esc(m.id)}</span>${M.length > 1 ? `<button type="button" class="link" data-mdel="${i}">${t('Ta bort')}</button>` : ''}</div>`).join('')}</div>
    <button type="button" class="btn" id="mAdd" style="margin-top:8px">+ ${t('Nytt läge')}</button>

    <h3 style="margin-top:18px">${t('Följ Home Mode i Surveillance Station')}</h3>
    <label class="check"><input type="checkbox" id="hmOn" ${A.homemode.enabled ? 'checked' : ''}> ${t('Byt läge när Home Mode slås på eller av')}</label>
    <div class="grid" style="margin-top:8px">
      <label class="f">${t('Home Mode på →')}<select id="hmTo">${opts(A.homemode.on, true)}</select></label>
      <label class="f">${t('Home Mode av →')}<select id="hmFrom">${opts(A.homemode.off, true)}</select></label>
    </div>

    <h3 style="margin-top:18px">${t('Schema')}</h3>
    <p class="muted small" style="margin-top:0">${t('Byt läge vid en viss tid, t.ex. Natt 01:00 och ↩ Följ Home Mode 06:00.')}</p>
    <p class="hint-box" style="margin:0 0 8px">${t('Från ett schemabyte till återgången väntar Home Mode-ändringar. ↩ Följ Home Mode går till det läge Home Mode anger just då (annars till läget före schemat), ↩ Föregående läge går tillbaka till läget före schemat. Ändrar du läget för hand eller via webhook gäller det direkt och väntan upphör.')}</p>
    <div class="schedlist">${A.schedule.map((e, i) => `<div class="row sched"><input type="time" data-st="${i}" value="${esc(e.time || '23:00')}" style="width:auto">
      <div class="chips">${DAYS.map((d, di) => `<button type="button" class="chip ${(e.days || [0, 1, 2, 3, 4, 5, 6]).includes(di) ? 'on' : ''}" data-sd="${i}" data-day="${di}">${d}</button>`).join('')}</div>
      <select data-sm="${i}" style="width:auto">${opts(e.mode, false, true)}</select><button type="button" class="link" data-sdel="${i}">${t('Ta bort')}</button></div>`).join('') || `<p class="muted small">${t('Inget schema.')}</p>`}</div>
    <button type="button" class="btn" id="sAdd" style="margin-top:8px">+ ${t('Ny tid')}</button>

    <h3 style="margin-top:18px">${t('Byt läge via webhook')}</h3>
    <div class="grid"><label class="f">${t('Läge')}<select id="mwSel">${opts('')}<option value="status">status</option></select></label></div>
    <div id="mwUrl" style="margin-top:8px"></div>
    <div class="row" style="margin-top:14px"><button type="button" class="btn primary" id="mSave">${t('Spara lägen')}</button></div>`;
    const mw = () => { $('#mwUrl').innerHTML = copyRow('mwCode', `${S.triggerBase}/api/mode?token=${encodeURIComponent(c.trigger_token)}&mode=${encodeURIComponent($('#mwSel').value)}`); };
    $('#mwSel').onchange = mw; mw();
  };
  draw();
  box.addEventListener('input', e => {
    const d = e.target.dataset;
    if (d.mi !== undefined) M[+d.mi].name = e.target.value;
    if (d.st !== undefined) A.schedule[+d.st].time = e.target.value;
  });
  box.addEventListener('change', e => {
    const d = e.target.dataset;
    if (d.sm !== undefined) A.schedule[+d.sm].mode = e.target.value;
    if (e.target.id === 'hmOn') A.homemode.enabled = e.target.checked;
    if (e.target.id === 'hmTo') A.homemode.on = e.target.value;
    if (e.target.id === 'hmFrom') A.homemode.off = e.target.value;
  });
  box.addEventListener('click', async e => {
    const d = e.target.dataset;
    if (e.target.id === 'mAdd') { M.push({ id: 'm' + Math.random().toString(36).slice(2, 7), name: t('Nytt läge') }); draw(); }
    else if (d.mdel !== undefined) { M.splice(+d.mdel, 1); draw(); }
    else if (e.target.id === 'sAdd') { A.schedule.push({ time: '23:00', days: [0, 1, 2, 3, 4, 5, 6], mode: M[0].id }); draw(); }
    else if (d.sdel !== undefined) { A.schedule.splice(+d.sdel, 1); draw(); }
    else if (d.sd !== undefined) {
      const ev = A.schedule[+d.sd]; ev.days = ev.days || [0, 1, 2, 3, 4, 5, 6]; const day = +d.day;
      ev.days = ev.days.includes(day) ? ev.days.filter(x => x !== day) : [...ev.days, day].sort(); e.target.classList.toggle('on');
    } else if (e.target.id === 'mSave') {
      e.target.disabled = true;
      try { await api('/api/settings', { method: 'PUT', body: { modes: M, mode_auto: A } }); await loadConfig(); updateModePill(S.cfg.mode); toast(t('Sparat')); render(); }
      catch (err) { toast(err.message, true); e.target.disabled = false; }
    }
  });
}

/* ---------------------------------------------------------------- installera som app (PWA) */
let pwaPrompt = null;
window.addEventListener('beforeinstallprompt', e => { e.preventDefault(); pwaPrompt = e; drawPwa(); });
window.addEventListener('appinstalled', () => { pwaPrompt = null; drawPwa(); });
if ('serviceWorker' in navigator && window.isSecureContext) navigator.serviceWorker.register('/sw.js', { updateViaCache: 'none' }).catch(() => { /* appen fungerar ändå */ });
function drawPwa() {
  const box = $('#pwaBox'); if (!box) return;
  const standalone = matchMedia('(display-mode: standalone)').matches || navigator.standalone;
  const ios = /iPad|iPhone|iPod/.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  if (standalone) box.innerHTML = `<span class="tag ok">✓ ${t('SynoArgus är installerad som app.')}</span>`;
  else if (!window.isSecureContext) box.innerHTML = `<button type="button" class="btn" disabled>${t('Installera som app')}</button>
    <p class="warnbox">${t('Installation kräver en säker anslutning (https). Du använder http nu. Lägg SynoArgus bakom en omvänd proxy med certifikat i DSM – se Guide > Övrigt.')}</p>`;
  else if (pwaPrompt) {
    box.innerHTML = `<button type="button" class="btn primary" id="pwaBtn">⬇ ${t('Installera som app')}</button>`;
    $('#pwaBtn').onclick = async () => { const p = pwaPrompt; pwaPrompt = null; try { p.prompt(); await p.userChoice; } catch (e) { /* */ } drawPwa(); };
  } else box.innerHTML = `<p class="small" style="margin:0">${t(ios ? 'På iPhone och iPad: tryck på Dela i Safari och välj Lägg till på hemskärmen.' : 'Öppna webbläsarens meny och välj Installera app eller Lägg till på startskärmen.')}</p>`;
}

/* ---------------------------------------------------------------- guide */
const GUIDE_SHOTS = { start: 'events', cam: 'camera', noti: 'notifications', modes: 'modes', watch: 'watch', other: 'status' };
function renderGuide() {
  const g = (window.GUIDE || {})[S.lang] || (window.GUIDE || {}).sv;
  if (!g) { main.innerHTML = `<p class="muted">–</p>`; return; }
  main.innerHTML = `<div class="guide">
    <h2>${esc(g.title)}</h2>
    <p class="muted">${esc(g.intro)}</p>
    <div class="toc">${g.sections.map(([id, title]) => `<a class="chip" href="#g-${id}">${esc(title)}</a>`).join('')}</div>
    ${g.sections.map(([id, title, html]) => `<div class="panel" id="g-${id}"><h3>${esc(title)}</h3>
      ${GUIDE_SHOTS[id] ? `<img class="shot" loading="lazy" src="/static/guide/${S.lang === 'en' ? 'en' : 'sv'}-${GUIDE_SHOTS[id]}.png" alt="">` : ''}${html}</div>`).join('')}
  </div>`;
  main.querySelectorAll('img.shot').forEach(im => { im.onclick = () => { $('#viewerImg').src = im.src; $('#viewer').showModal(); }; });
  main.querySelectorAll('a[href^="#g-"]').forEach(a => a.addEventListener('click', e => {
    const el = document.getElementById(a.getAttribute('href').slice(1));
    if (el) { e.preventDefault(); el.scrollIntoView({ behavior: 'smooth', block: 'start' }); }
  }));
}

/* ---------------------------------------------------------------- status */
function updateHtml(u) {
  if (!u) return '';
  return `
    <p class="small">${t('Din version: {v}', { v: esc(u.current) })}${u.latest ? ' · ' + t('Senaste version: {v}', { v: esc(u.latest) }) : ''}</p>
    ${u.error ? `<p class="err small">${esc(t('Kunde inte kontrollera: {e}', { e: u.error }))}</p>` : u.newer ? `
      <p><b class="okc">${t('Ny version finns!')}</b> ${u.url ? `<a href="${esc(u.url)}" target="_blank" rel="noopener">${t('Vad är nytt')} ↗</a>` : ''}</p>
      <p class="small">${t('Uppdatera i Container Manager: <b>Projekt</b> &gt; synoargus &gt; <b>Åtgärd</b> &gt; <b>Stoppa</b>, sedan <b>Åtgärd</b> &gt; <b>Bygg</b> (hämtar den nya imagen). Städa till sist under <b>Image</b> &gt; <b>Remove Unused Images</b>.')}</p>
      ${u.notes ? `<details><summary class="small">${t('Vad är nytt')}</summary><pre class="notes">${esc(u.notes)}</pre></details>` : ''}`
      : u.latest ? `<p class="small muted">${t('Du har senaste versionen.')}</p>` : ''}`;
}

async function renderStatus() {
  main.innerHTML = `<h2>${t('Status')}</h2><div id="stOut" class="muted">${t('Hämtar…')}</div>`;
  try {
    const s = await api('/api/status');
    const d = s.detector;
    $('#stOut').className = '';
    S.cfg.mode = s.mode; updateModePill(s.mode);
    const mi = s.mode || {};
    const srcName = { manual: t('manuellt'), webhook: 'webhook', schedule: t('schema'), schedule_return: t('schema'), homemode: 'Home Mode', default: '–' }[mi.source] || mi.source || '–';
    setPriority(s.priority?.until);
    $('#stOut').innerHTML = `
      <div class="panel"><h3>${t('Läge')}</h3>
        <div class="chips modebtns">${modeList().map(m => `<button class="chip ${m.id === mi.current ? 'on' : ''}" data-setmode="${esc(m.id)}">${esc(m.name)}</button>`).join('')}</div>
        <p class="small muted" style="margin:8px 0 0">${t('Senast ändrat: {d} ({s})', { d: mi.since ? fmtTime(mi.since) : '–', s: esc(srcName) })}${mi.follow_homemode ? ' · Home Mode: ' + (mi.homemode === true ? t('på') : mi.homemode === false ? t('av') : t('okänt') + (mi.homemode_error ? ' (' + esc(mi.homemode_error) + ')' : '')) : ''}</p>
        ${mi.hold ? `<p class="small" style="margin:6px 0 0">⏸ ${t('Schemat håller läget – Home Mode väntar till återgången.')}</p>` : ''}</div>
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
    $$('[data-setmode]').forEach(b => b.onclick = async () => { if (await setMode(b.dataset.setmode)) renderStatus(); });
    $('#updBtn').onclick = async () => {
      $('#updBtn').disabled = true;
      try { S.update = await api('/api/update?force=1'); $('#updOut').innerHTML = updateHtml(S.update); $('#nav button[data-tab=status]').classList.toggle('badge', !!S.update.newer); }
      catch (e) { toast(e.message, true); }
      $('#updBtn').disabled = false;
    };
  } catch (e) { $('#stOut').innerHTML = `<p class="err">${esc(e.message)}</p>`; }
}

boot();
