/* SynoArgus – guide (visas under fliken Guide). Samma innehåll som docs/guide.md på GitHub. */
'use strict';
window.GUIDE = {
  sv: {
    title: 'Guide',
    intro: 'Så här ställer du in SynoArgus, steg för steg. Installationen av själva containern beskrivs i README på GitHub.',
    sections: [
      ['start', 'Kom igång', `
<p>SynoArgus analyserar en bild när Surveillance Station upptäcker rörelse och larmar bara om AI:n hittar det du valt (person, bil, katt …).</p>
<ol>
  <li><b>Kameror:</b> under <b>Inställningar &gt; Kameror</b> hämtas kamerorna från Surveillance Station. Saknas någon, tryck <i>Hämta från Surveillance Station</i>.</li>
  <li><b>Regel i Surveillance Station:</b> varje kamera behöver en Action Rule som anropar SynoArgus vid rörelse. Tryck <i>Skapa regel</i> under kameran (kräver profilen <b>Administrator</b> för SynoArgus-användaren – du kan slå på den tillfälligt). Eller skapa den för hand, se <a href="#g-regel">Regel för hand</a>.</li>
  <li><b>Vad ska larma:</b> välj typer per kamera och tryck <b>Spara</b>.</li>
  <li><b>Notifiering:</b> lägg till minst en under <b>Inställningar &gt; Notifiering</b>, spara och tryck <i>Skicka test</i>.</li>
  <li><b>Testa:</b> gå framför kameran. Under <b>Status &gt; Logg</b> syns varje anrop från Surveillance Station och vad som hände.</li>
</ol>`],
      ['cam', 'Ställa in en kamera', `
<ul>
  <li><b>Larmar i läge</b> – i vilka lägen kameran larmar (inga valda = alla). Se <a href="#g-modes">Lägen</a>.</li>
  <li><b>Typer</b> – vad som ska larma. Fler typer finns under <i>Lägg till annan typ…</i></li>
  <li><b>Säkerhet minst</b> – hur säker AI:n måste vara. Börja runt 50–60 %.</li>
  <li><b>Minsta bredd/höjd</b> – ignorera små träffar långt bort (i pixlar i bilden).</li>
  <li><b>Tyst efter larm</b> – inga nya larm under X sekunder efter ett larm.</li>
  <li><b>Minsta tid mellan analyser</b> – begränsar belastningen om Surveillance Station reagerar hela tiden.</li>
  <li><b>Antal bilder vid rörelse</b> – syns inget på första bilden tas en till (upp till antalet).</li>
  <li><b>Uteslutningszoner</b> – tryck <i>Hämta bild</i> och dra rutor, t.ex. över grannens uppfart. <i>Helt inom</i> ignorerar föremål som ligger helt i zonen, <i>Berör</i> allt som rör vid den.</li>
</ul>
<h4>Testa och livebild</h4>
<p><i>Ta bild och analysera</i> visar exakt vad AI:n ser och varför varje träff skulle eller inte skulle larma – utan att skicka något. Osparade inställningar används, så du kan prova dig fram. <i>Live</i> visar en löpande bild, med <i>Visa AI</i> ritas rutorna ut.</p>
<h4 id="g-md">Rörelsedetektering i Surveillance Station</h4>
<p>SynoArgus läser <b>känslighet</b> och <b>tröskel</b> från Surveillance Station och kan ändra dem i steg om 5. Tryck <i>Starta mätning</i> och gå framför kameran – mätaren blinkar varje gång Surveillance Station reagerar.</p>
<ul>
  <li><b>Känslighet</b> (1–99): hur mycket en pixel måste ändras. Högre = små ändringar räknas.</li>
  <li><b>Tröskel</b> (1–99): hur stor del av området som måste ändras. Lägre = mindre ytor räcker.</li>
  <li>Kräver profilen <b>All-Object Manager</b> (eller Administrator) och att kameran har detekteringskälla <i>By Surveillance Station</i>.</li>
</ul>
<h4 id="g-regel">Regel för hand</h4>
<ol>
  <li>Kopiera adressen överst under kameran.</li>
  <li>Surveillance Station &gt; <b>Action Rule</b> &gt; <b>Lägg till</b>: regeltyp <i>Triggered</i>, åtgärdstyp <i>Interruptible</i>.</li>
  <li>Händelse: källa <i>Kamera</i>, din kamera, <i>Motion detected</i>.</li>
  <li>Åtgärd: enhet <b>Webhook</b>, adressen du kopierade, metod <b>GET</b>, 1 gång. Tryck <i>Skicka test</i> – en rad dyker upp under Status &gt; Logg.</li>
  <li>I Surveillance Station &gt; Home Mode &gt; Inställningar &gt; Action Rule ska SynoArgus-regeln vara <b>ikryssad</b> (aktiv även i Home Mode). När det ska larma styrs med lägen i SynoArgus.</li>
</ol>`],
      ['noti', 'Notifiering', `
<p>Lägg till så många du vill under <b>Inställningar &gt; Notifiering</b>. Varje notifiering kan begränsas till vissa kameror, typer och lägen. Spara och tryck <i>Skicka test</i>. En gul varning visas om filtret aldrig kan matcha.</p>
<ul>
  <li><b>Pushbullet</b> – Access Token från pushbullet.com &gt; Settings. Enhets-id är inte modellnamnet: pushbullet.com &gt; Devices, klicka på enheten och ta det som står efter <code>#devices/</code>.</li>
  <li><b>Telegram</b> – skapa en bot med <b>@BotFather</b>, skicka ett meddelande till den och hämta <code>chat.id</code> från <code>https://api.telegram.org/bot&lt;token&gt;/getUpdates</code>.</li>
  <li><b>ntfy</b> – installera appen och prenumerera på ett svårgissat ämne. Prioritet 5 bryter igenom Stör ej.</li>
  <li><b>E-post</b> – valfri SMTP-server. Gmail: <code>smtp.gmail.com</code>, port 587, STARTTLS och ett applösenord.</li>
  <li><b>Webhook</b> – valfri adress. GET, eller POST/PUT med JSON (valfritt med bild).</li>
  <li><b>MQTT</b> – publiceras på <code>synoargus/&lt;kamera&gt;/notification</code> som JSON.</li>
</ul>
<h4>Platshållare</h4>
<p>I adresser och texter kan du använda <code>%kamera%</code>, <code>%vad%</code>, <code>%vad_en%</code>, <code>%antal%</code>, <code>%meddelande%</code>, <code>%säkerhet%</code>, <code>%tid%</code>, <code>%datum%</code> och <code>%bild%</code> (engelska namn fungerar också). Klicka på en platshållare under fältet för att lägga in den.</p>
<h4>Exempel: Homey</h4>
<p>Webhook, metod GET, adress <code>https://webhook.homey.app/&lt;homey-id&gt;/synoargus?tag=%kamera%;%vad%</code>. Bocka ur <i>Skicka bild</i>. I Homey: <i>När</i> Logik &gt; <i>En webhook anropas</i>, händelse <code>synoargus</code>. Taggen blir t.ex. <i>OutDoor2-Backyard;Person</i>.</p>`],
      ['modes', 'Lägen och Home Mode', `
<p>SynoArgus har ett aktuellt <b>läge</b> – från början <i>Hemma</i>, <i>Natt</i> och <i>Borta</i>. Byt namn och lägg till egna under <b>Inställningar &gt; Lägen</b>.</p>
<ul>
  <li><b>Per kamera</b> (<i>Larmar i läge</i>) – i vilka lägen kameran larmar. Inga valda = alla.</li>
  <li><b>Per notifiering</b> (<i>Bara i läge</i>) – i vilka lägen den skickas. Inga valda = alla.</li>
  <li>Läget syns i headern. Klicka på det för att byta under Status.</li>
</ul>
<h4>Vem byter läge?</h4>
<p>Det som ändrar läget senast gäller:</p>
<ul>
  <li><b>Manuellt</b> – i headern eller under Status.</li>
  <li><b>Webhook</b> – <code>/api/mode?token=…&amp;mode=natt</code>, t.ex. från Homey. Adressen byggs under Lägen.</li>
  <li><b>Följ Home Mode</b> – t.ex. Home Mode på → Hemma, av → Borta (kontrolleras var 20:e sekund).</li>
  <li><b>Schema</b> – vid en viss tid vissa dagar.</li>
</ul>
<h4>Schema med återgång</h4>
<p>I schemat kan du välja ett läge, <b>↩ Följ Home Mode</b> eller <b>↩ Föregående läge</b>.</p>
<ul>
  <li>Från ett schemabyte tills schemat återgår <b>väntar Home Mode-ändringar</b>.</li>
  <li><b>↩ Följ Home Mode</b> går till det läge Home Mode anger just då (är Home Mode okänt: läget före schemat).</li>
  <li><b>↩ Föregående läge</b> går tillbaka till läget före schemat.</li>
  <li>Byter du läge <b>för hand eller via webhook</b> gäller det direkt och väntan upphör.</li>
</ul>
<p><b>Exempel:</b> Följ Home Mode (på → Hemma, av → Borta) och schemat <i>Natt</i> 01:00 och <i>↩ Följ Home Mode</i> 06:00, alla dagar. Går du hemifrån 03:00 är det fortfarande Natt till 06:00, sedan Borta. Kommer du hem 05:00 blir det Hemma 06:00.</p>
<p><b>Exempel på filter:</b> utekameror larmar i alla lägen, hallen bara i Natt och Borta. Telegram skickas bara i Natt och Borta, Homey-webhooken får allt (t.ex. för att tända lampor).</p>`],
      ['calib', 'Kalibrering', `
<p>Kalibreringen mäter under 12–72 timmar hur kameran beter sig och föreslår känslighet och tröskel för Surveillance Station. Den finns längst ned under varje kamera.</p>
<ul>
  <li>Var 30:e sekund tas två bilder med en sekunds mellanrum. SynoArgus mäter själv hur mycket som ändras i detekteringsområdet och AI:n avgör om ett mål syns och rör sig.</li>
  <li>Varje reaktion från Surveillance Station loggas med AI-resultat.</li>
  <li><b>Jag går förbi nu</b> tar <b>3 bilder per sekund i 90 sekunder</b> – gå genom bilden under tiden. Rörelsen mäts mellan bilder 1 sekund isär och AI:n analyserar så många bilder den hinner.</li>
  <li>Under de 90 sekunderna <b>går kalibreringen före larm</b>: larm från alla kameror ställs i kö och kan komma upp till 90 sekunder sent. Headern visar <i>Kalibrerar – larm fördröjs</i>.</li>
  <li><b>En kamera i taget.</b> Kalibrera kamerorna efter varandra – färdiga rapporter finns kvar.</li>
  <li>Inga bilder sparas, bara statistik.</li>
</ul>
<h4>Så gör du</h4>
<ol>
  <li>Starta (24 h är lagom) under ett vanligt dygn.</li>
  <li>Gå förbi kameran 2–3 gånger med <i>Jag går förbi nu</i>, gärna både dag och kväll. Ett tomt hus ger bara brus.</li>
  <li>När rapporten är klar: läs förslaget och tryck <i>Använd förslaget</i>. <i>Ångra</i> återställer de gamla värdena.</li>
  <li>Kontrollera med rörelsemätaren och kör gärna en ny kalibrering.</li>
</ol>
<p class="muted">Förslaget ändrar högst ±10 i steg om 5, missar aldrig fler mål än i dag och används aldrig automatiskt. Det är en uppskattning – Synology beskriver inte sin algoritm.</p>`],
      ['other', 'Övrigt', `
<ul>
  <li><b>Styr kameror (webhook)</b> – slå på eller av analysen per kamera, t.ex. från Homey: <code>/api/control?token=…&amp;camera=all&amp;action=off</code>. Surveillance Station påverkas inte.</li>
  <li><b>AI-modell</b> – börja med en s-modell. Under 1 s per bild (se <i>Ta bild och analysera</i>) är bra. Egna modeller (t.ex. YOLO26) läggs till med konverteraren, se README.</li>
  <li><b>Inloggning</b> – vilka DSM-konton som får logga in, och Synology SSO.</li>
  <li><b>Säkerhetskopia</b> – exportera och importera alla inställningar. Med lösenord blir filen känslig – förvara den säkert.</li>
  <li><b>Uppdatering</b> – en prick på Status betyder ny version. Container Manager &gt; Projekt &gt; synoargus &gt; Åtgärd &gt; <b>Stoppa</b>, sedan <b>Bygg</b>. Städa under Image &gt; Remove Unused Images.</li>
</ul>`],
      ['faq', 'Vanliga problem', `
<ul>
  <li><b>Inget händer vid rörelse</b> – syns anropet under Status &gt; Logg? Om inte: är regeln aktiv (även i Home Mode)? Fungerar <i>Skicka test</i> i regeln? Står det <i>ignoreras (läge …)</i> larmar kameran inte i det aktuella läget.</li>
  <li><b>Noll reaktioner i rörelsemätaren</b> – regeln saknas, är avstängd eller inte aktiv i Home Mode.</li>
  <li><b>AI:n hittar inget / för mycket</b> – använd <i>Ta bild och analysera</i>, sänk säkerheten eller minsta storlek, prova en större modell eller se över zonerna.</li>
  <li><b>Fel 105</b> – SynoArgus-användaren saknar behörighet: Action Rules kräver <b>Administrator</b>, rörelsedetektering <b>All-Object Manager</b>.</li>
  <li><b>Utelåst</b> – ta bort <code>#</code> framför <code>SYNOARGUS_UNLOCK=1</code> i docker-compose.yml och bygg projektet. Lägg till ditt konto, sätt tillbaka <code>#</code> och bygg igen.</li>
  <li><b>Kopiera fungerar inte</b> – över HTTP markeras texten i stället, tryck Ctrl+C.</li>
  <li><b>Logg</b> – Container Manager &gt; Container &gt; synoargus &gt; Logg.</li>
</ul>`],
    ],
  },
  en: {
    title: 'Guide',
    intro: 'How to set up SynoArgus, step by step. Installing the container itself is described in the README on GitHub.',
    sections: [
      ['start', 'Getting started', `
<p>SynoArgus analyses a snapshot when Surveillance Station detects motion and only alarms if the AI finds what you chose (person, car, cat …).</p>
<ol>
  <li><b>Cameras:</b> under <b>Settings &gt; Cameras</b> the cameras are fetched from Surveillance Station. If one is missing, press <i>Fetch from Surveillance Station</i>.</li>
  <li><b>Rule in Surveillance Station:</b> every camera needs an Action Rule that calls SynoArgus on motion. Press <i>Create rule</i> under the camera (requires the <b>Administrator</b> profile for the SynoArgus user – you can enable it temporarily). Or create it manually, see <a href="#g-regel">Manual rule</a>.</li>
  <li><b>What should alarm:</b> choose types per camera and press <b>Save</b>.</li>
  <li><b>Notifications:</b> add at least one under <b>Settings &gt; Notifications</b>, save and press <i>Send test</i>.</li>
  <li><b>Test:</b> walk in front of the camera. <b>Status &gt; Log</b> shows every call from Surveillance Station and what happened.</li>
</ol>`],
      ['cam', 'Setting up a camera', `
<ul>
  <li><b>Alarms in mode</b> – in which modes the camera alarms (none selected = all). See <a href="#g-modes">Modes</a>.</li>
  <li><b>Types</b> – what should alarm. More types under <i>Add another type…</i></li>
  <li><b>Minimum confidence</b> – how sure the AI must be. Start around 50–60 %.</li>
  <li><b>Minimum width/height</b> – ignore small detections far away (pixels in the image).</li>
  <li><b>Quiet after alarm</b> – no new alarms for X seconds after an alarm.</li>
  <li><b>Minimum time between analyses</b> – limits load if Surveillance Station reacts all the time.</li>
  <li><b>Snapshots per motion event</b> – if the first image shows nothing, another one is taken (up to the number).</li>
  <li><b>Exclusion zones</b> – press <i>Get image</i> and drag boxes, e.g. over the neighbour's driveway. <i>Fully inside</i> ignores objects entirely inside the zone, <i>Touches</i> anything touching it.</li>
</ul>
<h4>Test and live view</h4>
<p><i>Take snapshot and analyse</i> shows exactly what the AI sees and why each detection would or would not alarm – without sending anything. Unsaved settings are used, so you can experiment. <i>Live</i> shows a continuously refreshed image; with <i>Show AI</i> the boxes are drawn.</p>
<h4 id="g-md">Motion detection in Surveillance Station</h4>
<p>SynoArgus reads <b>sensitivity</b> and <b>threshold</b> from Surveillance Station and can change them in steps of 5. Press <i>Start measuring</i> and walk in front of the camera – the meter flashes each time Surveillance Station reacts.</p>
<ul>
  <li><b>Sensitivity</b> (1–99): how much a pixel must change. Higher = small changes count.</li>
  <li><b>Threshold</b> (1–99): how large a share of the area must change. Lower = smaller areas are enough.</li>
  <li>Requires the <b>All-Object Manager</b> (or Administrator) profile and detection source <i>By Surveillance Station</i>.</li>
</ul>
<h4 id="g-regel">Manual rule</h4>
<ol>
  <li>Copy the address at the top of the camera.</li>
  <li>Surveillance Station &gt; <b>Action Rule</b> &gt; <b>Add</b>: rule type <i>Triggered</i>, action type <i>Interruptible</i>.</li>
  <li>Event: source <i>Camera</i>, your camera, <i>Motion detected</i>.</li>
  <li>Action: device <b>Webhook</b>, the copied address, method <b>GET</b>, 1 time. Press <i>Send test</i> – a line appears under Status &gt; Log.</li>
  <li>In Surveillance Station &gt; Home Mode &gt; Settings &gt; Action Rule the SynoArgus rule should be <b>checked</b> (active in Home Mode too). When to alarm is decided by modes in SynoArgus.</li>
</ol>`],
      ['noti', 'Notifications', `
<p>Add as many as you like under <b>Settings &gt; Notifications</b>. Each one can be limited to certain cameras, types and modes. Save and press <i>Send test</i>. A yellow warning appears if the filter can never match.</p>
<ul>
  <li><b>Pushbullet</b> – Access Token from pushbullet.com &gt; Settings. The device id is not the model name: pushbullet.com &gt; Devices, click the device and take what follows <code>#devices/</code>.</li>
  <li><b>Telegram</b> – create a bot with <b>@BotFather</b>, send it a message and get <code>chat.id</code> from <code>https://api.telegram.org/bot&lt;token&gt;/getUpdates</code>.</li>
  <li><b>ntfy</b> – install the app and subscribe to a hard-to-guess topic. Priority 5 breaks through Do Not Disturb.</li>
  <li><b>Email</b> – any SMTP server. Gmail: <code>smtp.gmail.com</code>, port 587, STARTTLS and an app password.</li>
  <li><b>Webhook</b> – any URL. GET, or POST/PUT with JSON (optionally with the image).</li>
  <li><b>MQTT</b> – published to <code>synoargus/&lt;camera&gt;/notification</code> as JSON.</li>
</ul>
<h4>Placeholders</h4>
<p>In URLs and texts you can use <code>%camera%</code>, <code>%what%</code>, <code>%what_en%</code>, <code>%count%</code>, <code>%message%</code>, <code>%confidence%</code>, <code>%time%</code>, <code>%date%</code> and <code>%image%</code> (Swedish names work too). Click a placeholder under the field to insert it.</p>
<h4>Example: Homey</h4>
<p>Webhook, method GET, URL <code>https://webhook.homey.app/&lt;homey-id&gt;/synoargus?tag=%camera%;%what%</code>. Uncheck <i>Send image</i>. In Homey: <i>When</i> Logic &gt; <i>A webhook is called</i>, event <code>synoargus</code>. The tag becomes e.g. <i>OutDoor2-Backyard;Person</i>.</p>`],
      ['modes', 'Modes and Home Mode', `
<p>SynoArgus has a current <b>mode</b> – initially <i>Home</i>, <i>Night</i> and <i>Away</i>. Rename them and add your own under <b>Settings &gt; Modes</b>.</p>
<ul>
  <li><b>Per camera</b> (<i>Alarms in mode</i>) – in which modes the camera alarms. None selected = all.</li>
  <li><b>Per notification</b> (<i>Only in mode</i>) – in which modes it is sent. None selected = all.</li>
  <li>The mode is shown in the header. Click it to change it under Status.</li>
</ul>
<h4>Who changes the mode?</h4>
<p>Whatever changes the mode last wins:</p>
<ul>
  <li><b>Manually</b> – in the header or under Status.</li>
  <li><b>Webhook</b> – <code>/api/mode?token=…&amp;mode=night</code>, e.g. from Homey. The URL is built under Modes.</li>
  <li><b>Follow Home Mode</b> – e.g. Home Mode on → Home, off → Away (checked every 20 seconds).</li>
  <li><b>Schedule</b> – at a certain time on certain days.</li>
</ul>
<h4>Schedule with return</h4>
<p>In the schedule you can choose a mode, <b>↩ Follow Home Mode</b> or <b>↩ Previous mode</b>.</p>
<ul>
  <li>From a schedule change until the schedule returns, <b>Home Mode changes wait</b>.</li>
  <li><b>↩ Follow Home Mode</b> goes to the mode Home Mode indicates right then (if Home Mode is unknown: the mode before the schedule).</li>
  <li><b>↩ Previous mode</b> goes back to the mode before the schedule.</li>
  <li>If you change the mode <b>by hand or via webhook</b> it applies immediately and the waiting ends.</li>
</ul>
<p><b>Example:</b> Follow Home Mode (on → Home, off → Away) and the schedule <i>Night</i> 01:00 and <i>↩ Follow Home Mode</i> 06:00, every day. If you leave at 03:00 it stays Night until 06:00, then Away. If you come home at 05:00 it becomes Home at 06:00.</p>
<p><b>Filter example:</b> outdoor cameras alarm in all modes, the hall only in Night and Away. Telegram is sent only in Night and Away, the Homey webhook gets everything (e.g. to turn on lights).</p>`],
      ['calib', 'Calibration', `
<p>The calibration measures over 12–72 hours how the camera behaves and proposes sensitivity and threshold for Surveillance Station. It is at the bottom of each camera.</p>
<ul>
  <li>Every 30 seconds two images are taken one second apart. SynoArgus measures how much changes in the detection area and the AI decides whether a target is visible and moving.</li>
  <li>Every reaction from Surveillance Station is logged with the AI result.</li>
  <li><b>I am walking past now</b> takes <b>3 images per second for 90 seconds</b> – walk through the picture meanwhile. Motion is measured between images 1 second apart and the AI analyses as many images as it can keep up with.</li>
  <li>During those 90 seconds <b>the calibration goes before alarms</b>: alarms from all cameras are queued and can arrive up to 90 seconds late. The header shows <i>Calibrating – alarms delayed</i>.</li>
  <li><b>One camera at a time.</b> Calibrate the cameras one after another – finished reports are kept.</li>
  <li>No images are stored, only statistics.</li>
</ul>
<h4>How to</h4>
<ol>
  <li>Start it (24 h is about right) during a normal day.</li>
  <li>Walk past the camera 2–3 times with <i>I am walking past now</i>, ideally both day and evening. An empty house only gives noise.</li>
  <li>When the report is ready: read the proposal and press <i>Apply the proposal</i>. <i>Undo</i> restores the old values.</li>
  <li>Check with the motion meter and feel free to run another calibration.</li>
</ol>
<p class="muted">The proposal changes at most ±10 in steps of 5, never misses more targets than today and is never applied automatically. It is an estimate – Synology does not document its algorithm.</p>`],
      ['other', 'Other', `
<ul>
  <li><b>Control cameras (webhook)</b> – turn the analysis on or off per camera, e.g. from Homey: <code>/api/control?token=…&amp;camera=all&amp;action=off</code>. Surveillance Station is not affected.</li>
  <li><b>AI model</b> – start with an s model. Under 1 s per image (see <i>Take snapshot and analyse</i>) is good. Own models (e.g. YOLO26) are added with the converter, see the README.</li>
  <li><b>Login</b> – which DSM accounts may log in, and Synology SSO.</li>
  <li><b>Backup</b> – export and import all settings. With passwords the file is sensitive – keep it safe.</li>
  <li><b>Update</b> – a dot on Status means a new version. Container Manager &gt; Project &gt; synoargus &gt; Action &gt; <b>Stop</b>, then <b>Build</b>. Clean up under Image &gt; Remove Unused Images.</li>
</ul>`],
      ['faq', 'Troubleshooting', `
<ul>
  <li><b>Nothing happens on motion</b> – is the call shown under Status &gt; Log? If not: is the rule enabled (also in Home Mode)? Does <i>Send test</i> in the rule work? If it says <i>ignored (mode …)</i> the camera does not alarm in the current mode.</li>
  <li><b>Zero reactions in the motion meter</b> – the rule is missing, disabled or not active in Home Mode.</li>
  <li><b>The AI finds nothing / too much</b> – use <i>Take snapshot and analyse</i>, lower the confidence or minimum size, try a larger model or check the zones.</li>
  <li><b>Error 105</b> – the SynoArgus user lacks permission: Action Rules need <b>Administrator</b>, motion detection <b>All-Object Manager</b>.</li>
  <li><b>Locked out</b> – remove the <code>#</code> in front of <code>SYNOARGUS_UNLOCK=1</code> in docker-compose.yml and build the project. Add your account, put the <code>#</code> back and build again.</li>
  <li><b>Copy does not work</b> – over HTTP the text is selected instead, press Ctrl+C.</li>
  <li><b>Logs</b> – Container Manager &gt; Container &gt; synoargus &gt; Log.</li>
</ul>`],
    ],
  },
};
