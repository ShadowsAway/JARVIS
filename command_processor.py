"""
JARVIS Command Processor
Spanish NLP with regex-based intent recognition and RapidFuzz fallback.
"""

import re
import unicodedata

from rapidfuzz import fuzz, process as fuzz_process


# ── Text normalisation ────────────────────────────────────────────────────────

def normalize(text: str) -> str:
    """
    Lowercase, strip diacritics, collapse whitespace, remove punctuation,
    then apply phonetic aliases so Vosk mispronunciations are corrected.
    """
    text = text.lower().strip()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = _apply_phonetic_aliases(text)
    return text


def _apply_phonetic_aliases(text: str) -> str:
    """Replace phonetically misspelled English words with correct forms."""
    import config as _cfg
    # Multi-word first (longer matches take priority)
    for wrong, right in _cfg.PHONETIC_MULTIWORD.items():
        text = text.replace(wrong, right)
    # Single-word aliases
    words = text.split()
    words = [_cfg.PHONETIC_ALIASES.get(w, w) for w in words]
    return " ".join(words)


# ── Intent pattern definitions ────────────────────────────────────────────────
# Every pattern is written in normalised form (no accents, lower-case).

INTENTS: dict[str, list[str]] = {

    # ── System power ──────────────────────────────────────────────────────────
    "shutdown": [
        r"apaga(?:r)?\s+(?:el\s+)?(?:ordenador|pc|computadora|equipo|sistema)",
        r"apaga(?:r)?\s+(?:mi\s+)?(?:ordenador|pc|computadora)",
        r"cierra\s+(?:el\s+)?(?:ordenador|pc|computadora|equipo)",
        r"^apagar$",
        r"quiero\s+apagar",
        r"apaga\s+todo",
    ],
    "restart": [
        r"reinicia(?:r)?\s+(?:el\s+)?(?:ordenador|pc|computadora|equipo)",
        r"reinicia(?:r)?\s+(?:el\s+)?sistema",
        r"reiniciar\s+(?:el\s+)?(?:ordenador|pc)",
        r"vuelve\s+a\s+iniciar",
    ],
    "sleep": [
        r"(?:pon|poner|manda?)\s+(?:el\s+)?(?:ordenador|pc)\s+(?:a\s+)?(?:dormir|suspension|suspender)",
        r"suspender?\s+(?:el\s+)?(?:ordenador|pc)",
        r"modo\s+(?:suspension|sleep|hibernacion)",
    ],

    # ── WhatsApp ──────────────────────────────────────────────────────────────
    "send_whatsapp": [
        # With explicit delimiter — multi-word contact names supported (lazy match)
        r"(?:manda|envia|escribe|dile|contacta)\s+(?:un\s+)?mensaje\s+(?:(?:por\s+)?whatsapp\s+)?a\s+(\w+(?:\s+\w+)*?)\s+(?:que\s+diga|diciendo|con\s+el\s+texto|con)\s+(.+)",
        r"(?:manda|envia)\s+(?:un\s+)?mensaje\s+a\s+(\w+(?:\s+\w+)*?)\s+(?:por\s+)?whatsapp\s+(?:que\s+diga|diciendo)\s+(.+)",
        r"whatsapp\s+(?:a\s+)?(\w+(?:\s+\w+)*?)\s+(?:que\s+diga|diciendo|con)\s+(.+)",
        r"(?:dile|escribele)\s+a\s+(\w+(?:\s+\w+)*?)\s+(?:por\s+whatsapp\s+)?(?:que\s+)?(.+)",
        r"(?:manda|envia)\s+a\s+(\w+(?:\s+\w+)*?)\s+(?:por\s+whatsapp\s+)?(?:que\s+diga\s+|el\s+mensaje\s+)?(.+)",
        r"mensaje\s+a\s+(\w+(?:\s+\w+)*?)\s+(?:diciendo|que\s+diga|con)\s+(.+)",
        # Without delimiter: "manda un mensaje a {contact} {message}" (contact = first word)
        r"(?:manda|envia)\s+(?:un\s+)?mensaje\s+(?:(?:por\s+)?whatsapp\s+)?a\s+(\w+)\s+(.+)",
    ],
    "open_whatsapp_chrome": [
        r"abre?\s+whatsapp\s+(?:en\s+)?(?:chrome|el\s+navegador)",
        r"abre?\s+whatsapp\s+web",
        r"whatsapp\s+(?:en\s+)?(?:chrome|el\s+navegador)",
        r"abre?\s+web(?:site)?\s+de\s+whatsapp",
    ],

    # ── YouTube ───────────────────────────────────────────────────────────────
    "play_youtube": [
        r"pon\s+(.+?)\s+en\s+youtube",
        r"reproduce\s+(.+?)\s+en\s+youtube",
        r"busca\s+(.+?)\s+en\s+youtube",
        r"escuchar?\s+(.+?)\s+en\s+youtube",
        r"pon\s+musica\s+(?:de\s+)?(.+)",
        r"reproduce\s+musica\s+(?:de\s+)?(.+)",
        r"quiero\s+(?:escuchar|oir)\s+(.+)",
        r"youtube\s+(.+)",
        r"pon\s+(?:el\s+|la\s+|un\s+)?(.+?)\s+(?:en\s+youtube|de\s+youtube)",
    ],

    # ── Programs ──────────────────────────────────────────────────────────────
    "open_program": [
        r"(?:abre?|ejecuta|inicia|lanza|arranca|corre|activa)\s+(?:el\s+programa\s+|el\s+|la\s+)?(.+)",
        r"(?:abrir|ejecutar|iniciar|lanzar|arrancar)\s+(?:el\s+|la\s+)?(.+)",
        r"quiero\s+(?:abrir|usar|ejecutar)\s+(.+)",
        r"necesito\s+(?:abrir|usar)\s+(.+)",
        r"pon\s+(?:en\s+marcha\s+)?(?:el\s+|la\s+)?(.+)",
    ],
    "close_program": [
        r"(?:cierra?|cerrar|mata|matar|termina|terminar|para|parar)\s+(?:el\s+programa\s+|el\s+|la\s+)?(.+)",
        r"(?:cierra?|cerrar)\s+(?:la\s+)?(?:ventana|aplicacion)\s+(?:de\s+)?(.+)",
    ],

    # ── Websites ──────────────────────────────────────────────────────────────
    "open_website": [
        r"(?:abre?|ve\s+a|entra\s+en|navega\s+(?:a|hacia))\s+(?:la\s+(?:pagina|web|pagina\s+web)\s+(?:de\s+)?)?(.+)",
        r"(?:abre?|ve\s+a)\s+(.+\.(?:com|es|net|org|io))",
        r"busca(?:r)?\s+en\s+google\s+(.+)",
    ],

    # ── Volume ────────────────────────────────────────────────────────────────
    "volume_up": [
        r"sube(?:r)?\s+(?:el\s+)?(?:volumen|sonido|audio)",
        r"mas\s+(?:volumen|sonido)",
        r"(?:volumen|sonido)\s+(?:mas\s+)?(?:alto|subir)",
        r"aumenta(?:r)?\s+(?:el\s+)?(?:volumen|sonido)",
    ],
    "volume_down": [
        r"baja(?:r)?\s+(?:el\s+)?(?:volumen|sonido|audio)",
        r"menos\s+(?:volumen|sonido)",
        r"(?:volumen|sonido)\s+(?:mas\s+)?(?:bajo|bajar)",
        r"(?:reduce|disminuye)\s+(?:el\s+)?(?:volumen|sonido)",
    ],
    "mute": [
        r"silencia(?:r)?(?:\s+(?:el\s+)?(?:sonido|audio))?",
        r"(?:quita|quitar|desactiva)\s+(?:el\s+)?(?:sonido|audio|volumen)",
        r"^(?:mute|silencio)$",
        r"sin\s+(?:sonido|audio)",
    ],

    # ── Screenshot ────────────────────────────────────────────────────────────
    "screenshot": [
        r"(?:haz|hacer|toma|tomar)\s+(?:una\s+)?captura(?:\s+de\s+(?:la\s+)?pantalla)?",
        r"captura(?:r)?\s+(?:la\s+)?pantalla",
        r"(?:screenshot|foto\s+de\s+(?:la\s+)?pantalla)",
        r"pantallazo",
    ],

    # ── Time / Date ───────────────────────────────────────────────────────────
    "time": [
        r"(?:que|cual\s+es\s+la)\s+hora\s+(?:es|son)?",
        r"dime\s+(?:la\s+)?hora",
        r"(?:que\s+)?hora\s+(?:es|son)",
        r"^hora$",
    ],
    "date": [
        r"(?:que|cual\s+es\s+la)\s+(?:fecha|dia)\s+(?:es\s+hoy)?",
        r"dime\s+(?:la\s+)?fecha",
        r"que\s+(?:dia|fecha)\s+(?:es\s+hoy|tenemos)",
        r"^(?:fecha|dia)$",
    ],

    # ── Files ─────────────────────────────────────────────────────────────────
    "move_file": [
        r"(?:mueve?|mover|copia|copiar|traslada)\s+(?:el\s+)?(?:archivo|fichero|carpeta)?\s*(.+?)\s+(?:a|hacia|en)\s+(.+)",
    ],

    # ── System info ───────────────────────────────────────────────────────────
    "system_info": [
        r"(?:muestra|dime|dame)\s+(?:la\s+)?informacion\s+del\s+sistema",
        r"(?:como\s+esta|estado\s+del?)\s+(?:sistema|pc|ordenador)",
        r"(?:uso\s+de\s+)?(?:cpu|ram|memoria|procesador)",
    ],

    # ── Help ──────────────────────────────────────────────────────────────────
    "help": [
        r"ayuda(?:me)?",
        r"que\s+(?:puedes\s+)?hacer",
        r"(?:dime\s+(?:tus\s+)?|que\s+son\s+(?:los\s+)?)comandos",
        r"^(?:ayuda|help)$",
    ],
}


# ── Command Processor ─────────────────────────────────────────────────────────

class CommandProcessor:
    """
    Parses a normalised Spanish utterance and returns (intent, entities).
    Falls back to fuzzy program-name matching when no regex fires.
    """

    def __init__(self, config):
        self.config = config

        # Pre-compile every pattern once at startup
        self._compiled: dict[str, list[re.Pattern]] = {}
        for intent, patterns in INTENTS.items():
            self._compiled[intent] = [
                re.compile(p, re.IGNORECASE) for p in patterns
            ]

    # ── Public API ────────────────────────────────────────────────────────────

    def process(self, text: str) -> tuple[str | None, dict]:
        """
        Returns (intent_name, entities_dict) or (None, {}) if nothing matched.
        """
        if not text or not text.strip():
            return None, {}

        norm = normalize(text)

        # ── Regex pass ────────────────────────────────────────────────────────
        for intent, patterns in self._compiled.items():
            for pattern in patterns:
                m = pattern.search(norm)
                if m:
                    entities = self._extract_entities(intent, m, norm)
                    return intent, entities

        # ── Fuzzy fallback — maybe user just said a program name ──────────────
        prog = self._find_program_fuzzy(norm)
        if prog:
            return "open_program", {"program": prog}

        return None, {}

    # ── Entity extraction ─────────────────────────────────────────────────────

    def _extract_entities(self, intent: str, match: re.Match, norm: str) -> dict:
        try:
            if intent == "send_whatsapp":
                return {
                    "contact": match.group(1).strip(),
                    "message": match.group(2).strip(),
                }
            if intent == "play_youtube":
                return {"query": match.group(1).strip()}
            if intent == "open_program":
                return {"program": match.group(1).strip()}
            if intent == "open_website":
                return {"site": match.group(1).strip()}
            if intent == "move_file":
                return {
                    "source": match.group(1).strip(),
                    "dest":   match.group(2).strip(),
                }
            if intent == "close_program":
                return {"program": match.group(1).strip()}
        except (IndexError, AttributeError):
            pass
        return {}

    # ── Fuzzy matching ────────────────────────────────────────────────────────

    def _find_program_fuzzy(self, text: str) -> str | None:
        """
        Check whether *text* closely resembles a known program name.
        Returns the matched key if confidence >= 80, otherwise None.
        """
        all_names = list(self.config.PROGRAMS.keys())
        result = fuzz_process.extractOne(
            text, all_names,
            scorer=fuzz.partial_ratio,
            score_cutoff=80,
        )
        return result[0] if result else None
