"""Översättning av texter från servern (felmeddelanden, logg). Svenska är grundspråk."""
from .config import config

EN = {
    # allmänt / inloggning
    "Installationen är inte klar": "Setup is not finished",
    "Inte inloggad": "Not logged in",
    "Fel token": "Wrong token",
    "Redan installerad": "Already set up",
    "Installationen kan bara göras från hemnätet": "Setup can only be done from the local network",
    "Adressen måste börja med http:// eller https://": "The address must start with http:// or https://",
    "Kunde inte ansluta till Surveillance Station: {e}": "Could not connect to Surveillance Station: {e}",
    "Kunde inte nå NAS:en: {e}": "Could not reach the NAS: {e}",
    "Ditt DSM-konto: {e}": "Your DSM account: {e}",
    "För många försök, vänta 5 minuter": "Too many attempts, wait 5 minutes",
    "Inloggning med DSM-konto är avstängd, använd SSO": "DSM account login is disabled, use SSO",
    "Kontot har inte behörighet till SynoArgus": "This account is not allowed to use SynoArgus",
    "Du ({me}) måste finnas med bland tillåtna konton": "You ({me}) must be in the list of allowed accounts",
    "Minst ett inloggningssätt måste vara på": "At least one login method must be enabled",
    "Sparat, men modellen kunde inte laddas: {e}": "Saved, but the model could not be loaded: {e}",
    "Okänd typ av notifierare": "Unknown notifier type",
    "Spara notifieraren först": "Save the notifier first",
    "Inget skickades": "Nothing was sent",
    "Bilden finns inte": "Image not found",
    "Okänd kamera": "Unknown camera",
    "Ogiltig tidszon: {tz}": "Invalid time zone: {tz}",
    "Filen är inte en SynoArgus-export": "The file is not a SynoArgus export",
    "Okänd åtgärd (on, off, toggle eller status)": "Unknown action (on, off, toggle or status)",
    "Hittade inga värden för rörelsedetektering": "No motion detection values found",
    # synology
    "Fel användarnamn eller lösenord": "Wrong username or password",
    "Kontot är inaktiverat eller ett gästkonto": "The account is disabled or a guest account",
    "Kontot saknar behörighet": "The account lacks permission",
    "Engångskod (tvåstegsverifiering) krävs": "One-time code (2-step verification) required",
    "Engångskoden stämmer inte": "The one-time code is wrong",
    "Tvåstegsverifiering måste aktiveras för kontot": "2-step verification must be enabled for the account",
    "För många försök, IP-adressen är spärrad": "Too many attempts, the IP address is blocked",
    "Lösenordet har gått ut": "The password has expired",
    "Lösenordet måste bytas": "The password must be changed",
    "Kontot är låst": "The account is locked",
    "Okänt fel": "Unknown error",
    "Ogiltiga parametrar": "Invalid parameters",
    "API:t finns inte": "The API does not exist",
    "Metoden finns inte": "The method does not exist",
    "API-versionen stöds inte": "The API version is not supported",
    "Behörighet saknas (har kontot rätt till Surveillance Station?)": "Permission denied (does the account have access to Surveillance Station?)",
    "Sessionen har gått ut": "The session has expired",
    "Inloggad från flera ställen": "Logged in from several places",
    "Sessionen är ogiltig": "The session is invalid",
    "Synology-anslutningen är inte inställd": "The Synology connection is not set up",
    "Kameran \"{name}\" finns inte i Surveillance Station": "The camera \"{name}\" does not exist in Surveillance Station",
    "Oväntat svar från Synology ({code}, {ctype})": "Unexpected response from Synology ({code}, {ctype})",
    "Kunde inte nå DSM på {url}: {e}": "Could not reach DSM at {url}: {e}",
    "{text} (DSM-kod {code})": "{text} (DSM code {code})",
    # logg
    "Okänd kamera (lägg till den under Kameror)": "Unknown camera (add it under Cameras)",
    "Inget av intresse ({ms} ms)": "Nothing of interest ({ms} ms)",
    "Larm: {types}": "Alarm: {types}",
    "Fel: {e}": "Error: {e}",
    "Testkamera": "Test camera",
}


def lang():
    return config.get("language") or "sv"


def tr(msg, /, **kw):
    if lang() == "en":
        msg = EN.get(msg, msg)
    return msg.format(**kw) if kw else msg
