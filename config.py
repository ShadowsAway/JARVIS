"""
JARVIS Configuration
All constants, paths, mappings, and color definitions live here.
"""

import os

# ── Identity ───────────────────────────────────────────────────────────────────
APP_NAME = "J.A.R.V.I.S"
VERSION  = "1.0"

# ── Speech / ASR ──────────────────────────────────────────────────────────────
MODEL_PATH = os.path.join("models", "vosk-model-small-es-0.42")
LANGUAGE   = "es"

# ── Hotkey ────────────────────────────────────────────────────────────────────
# Hold this key to record voice.  "0" matches both numpad 0 and the top-row 0.
LISTEN_KEY = "0"

# ── File paths ────────────────────────────────────────────────────────────────
# Screenshots are saved to the user's Desktop when available, otherwise Documents.
def _default_screenshot_dir() -> str:
    home = os.path.expanduser("~")
    for candidate in ("Desktop", "Escritorio", "Documents", "Documentos"):
        path = os.path.join(home, candidate)
        if os.path.isdir(path):
            return path
    return home

SCREENSHOTS_DIR   = _default_screenshot_dir()

# Chrome user-data directory for a persistent WhatsApp Web session.
# Keep this directory; deleting it forces a new QR-code scan.
WHATSAPP_PROFILE  = os.path.join(os.path.dirname(__file__), "whatsapp_profile")

# ── Program aliases → executable name ─────────────────────────────────────────
# Keys are lowercase Spanish names (or common abbreviations).
# Values are the executable name passed to subprocess / shutil.which.
PROGRAMS: dict[str, str] = {
    # Browsers
    "chrome":                    "chrome",
    "google chrome":             "chrome",
    "navegador":                 "chrome",
    "firefox":                   "firefox",
    # Communication
    "discord":                   "Discord",
    "whatsapp":                  "WhatsApp",
    "telegram":                  "Telegram",
    # Media
    "spotify":                   "Spotify",
    "vlc":                       "vlc",
    "obs":                       "obs64",
    # Gaming
    "steam":                     "Steam",
    # Productivity / System
    "notepad":                   "notepad",
    "bloc de notas":             "notepad",
    "calculadora":               "calc",
    "explorador":                "explorer",
    "explorador de archivos":    "explorer",
    "paint":                     "mspaint",
    "administrador de tareas":   "taskmgr",
    "task manager":              "taskmgr",
    # Microsoft Office
    "word":                      "WINWORD",
    "excel":                     "EXCEL",
    # Development
    "vscode":                    "Code",
    "visual studio code":        "Code",
    # Creative
    "photoshop":                 "Photoshop",
}

# ── Website aliases ────────────────────────────────────────────────────────────
WEBSITES: dict[str, str] = {
    "youtube":    "https://www.youtube.com",
    "google":     "https://www.google.com",
    "facebook":   "https://www.facebook.com",
    "instagram":  "https://www.instagram.com",
    "twitter":    "https://www.twitter.com",
    "x":          "https://www.twitter.com",
    "twitch":     "https://www.twitch.tv",
    "netflix":    "https://www.netflix.com",
    "gmail":      "https://mail.google.com",
    "github":     "https://www.github.com",
    "whatsapp":   "https://web.whatsapp.com",
}

# ── Phonetic aliases ──────────────────────────────────────────────────────────
# Vosk (Spanish model) transcribes English words phonetically in Spanish.
# Map each likely transcription → correct word used in patterns/PROGRAMS.
PHONETIC_ALIASES: dict[str, str] = {
    # Chrome
    "cromo": "chrome",  "crome": "chrome",  "krome": "chrome",  "chrom": "chrome",
    # Phonk
    "fon": "phonk",     "fonk": "phonk",    "funk": "phonk",    "fanc": "phonk",
    # YouTube
    "yutu": "youtube",  "yutub": "youtube", "utub": "youtube",  "jutub": "youtube",
    "iutub": "youtube",
    # WhatsApp
    "wasap": "whatsapp",   "guasap": "whatsapp",  "uasap": "whatsapp",
    "uatsap": "whatsapp",  "whasap": "whatsapp",  "watsap": "whatsapp",
    # Spotify
    "espotifai": "spotify", "spotifai": "spotify", "espotify": "spotify",
    "spotifi": "spotify",   "espotifi": "spotify",
    # Discord
    "discor": "discord",  "diskor": "discord",  "discort": "discord",
    # Netflix
    "netflis": "netflix",  "netflics": "netflix",  "netflic": "netflix",
    # Twitch
    "tuich": "twitch",  "tuit": "twitch",  "tuitch": "twitch",
    # Steam
    "estim": "steam",  "estam": "steam",  "estean": "steam",
    # Fortnite
    "fortnait": "fortnite",  "fortnai": "fortnite",  "fortnite": "fortnite",
    # Instagram
    "instragram": "instagram",  "instragam": "instagram",  "instag": "instagram",
    # TikTok
    "ticto": "tiktok",  "tikto": "tiktok",  "tic toc": "tiktok",
    # Minecraft
    "maincraf": "minecraft",  "mainkraf": "minecraft",
    # Telegram
    "telegran": "telegram",  "telagram": "telegram",
}

# Multi-word phonetic aliases (applied as substring replacements)
PHONETIC_MULTIWORD: dict[str, str] = {
    "yu tu":    "youtube",
    "you tube": "youtube",
    "wats ap":  "whatsapp",
    "what sap": "whatsapp",
    "es pot if ai": "spotify",
}

# ── Contact name aliases ──────────────────────────────────────────────────────
# Vosk (Spanish model) hears Catalan/Spanish names and outputs their English
# equivalents.  These corrections apply ONLY to the WhatsApp contact search.
# Add any name that Vosk gets wrong for your contacts.
CONTACT_NAME_ALIASES: dict[str, str] = {
    "andrew":  "andreu",   # Catalan: Andreu → Vosk hears: andrew
    "mark":    "marc",     # Catalan: Marc   → Vosk hears: mark
    "paul":    "pau",      # Catalan: Pau    → Vosk hears: paul
    "peter":   "pere",     # Catalan: Pere   → Vosk hears: peter
    "john":    "joan",     # Catalan: Joan   → Vosk hears: john
    "james":   "jaume",    # Catalan: Jaume  → Vosk hears: james
    "george":  "jordi",    # Catalan: Jordi  → Vosk hears: george
    "raymond": "ramon",    # Catalan: Ramon  → Vosk hears: raymond
    "matthew": "mateu",    # Catalan: Mateu  → Vosk hears: matthew
}

# ── GUI Color Palette (Iron Man / HUD aesthetic) ───────────────────────────────
BG       = "#050a14"   # Deep space black-blue  (background)
ACCENT   = "#00d4ff"   # Electric cyan           (primary accent)
ACCENT2  = "#0055ff"   # Arc-reactor blue        (secondary accent)
TEXT     = "#c8e8ff"   # Light ice blue          (body text)
DIM      = "#1a3a5c"   # Dark steel blue         (inactive / dimmed)
SUCCESS  = "#00ff88"   # Matrix green            (success / speaking)
WARNING  = "#ffaa00"   # Amber                   (processing / warning)
ERROR    = "#ff3355"   # Alert red               (error)
