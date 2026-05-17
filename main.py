"""
JARVIS — Entry Point
Wires together the GUI, VoiceEngine, CommandProcessor, and Actions.
Hold [0] to speak; release to process.
"""

import os
import subprocess
import sys
import threading

import keyboard

import config as cfg
from actions import Actions
from command_processor import CommandProcessor
from gui import JarvisGUI
from voice_engine import VoiceEngine


class JARVIS:
    """
    Top-level controller that connects all subsystems.

    Lifecycle
    ---------
    1. GUI is created first so log messages are visible immediately.
    2. VoiceEngine is initialised only if the Vosk model exists.
    3. Global keyboard hooks are registered for the LISTEN_KEY.
    4. gui.run() blocks until the window is closed.
    5. Cleanup is performed in the finally block.
    """

    def __init__(self) -> None:
        # ── GUI (must come first — other subsystems log into it) ──────────────
        self.gui = JarvisGUI()

        # ── Actions & command processor ───────────────────────────────────────
        self.actions = Actions(speak_func=self._speak, log_func=self.gui.add_log)
        self.processor = CommandProcessor(cfg)

        # ── Voice engine (conditional on model presence) ──────────────────────
        self.voice: VoiceEngine | None = None

        if os.path.isdir(cfg.MODEL_PATH):
            try:
                self.voice = VoiceEngine(
                    model_path=cfg.MODEL_PATH,
                    on_result_callback=self._on_speech_result,
                )
                self.gui.add_log("Motor de voz cargado correctamente.", "success")
            except Exception as exc:
                self.gui.add_log(f"Error cargando motor de voz: {exc}", "error")
                self.voice = None
        else:
            self.gui.add_log(
                f"Modelo Vosk no encontrado en '{cfg.MODEL_PATH}'. "
                "Ejecuta setup_jarvis.py primero.",
                "error",
            )

        # ── Text command callback ─────────────────────────────────────────────
        self.gui.set_command_callback(self._on_speech_result)

        # ── Keyboard hooks ────────────────────────────────────────────────────
        self._key_held: bool = False
        self._setup_hotkey()

        # ── Initial visual state ──────────────────────────────────────────────
        self.gui.set_state("idle")
        self.gui.add_log(
            f'Mantén pulsado [{cfg.LISTEN_KEY}] para hablar.', "dim"
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Hotkey handlers
    # ─────────────────────────────────────────────────────────────────────────

    def _setup_hotkey(self) -> None:
        keyboard.on_press_key(cfg.LISTEN_KEY, self._on_key_press, suppress=False)
        keyboard.on_release_key(cfg.LISTEN_KEY, self._on_key_release, suppress=False)

    def _on_key_press(self, event) -> None:
        # Guard: ignore if already recording or voice engine is unavailable
        if self.voice is None:
            self.gui.add_log(
                "Motor de voz no disponible. Ejecuta setup_jarvis.py.", "warning"
            )
            return
        if self._key_held:
            return  # key repeat — ignore

        self._key_held = True
        self.voice.start_recording()
        self.gui.set_state("listening")
        self.gui.add_log("Escuchando…", "info")

    def _on_key_release(self, event) -> None:
        if not self._key_held:
            return
        self._key_held = False

        if self.voice and self.voice.is_recording:
            self.voice.stop_recording()
            self.gui.set_state("processing")
            self.gui.add_log("Procesando audio…", "dim")

    # ─────────────────────────────────────────────────────────────────────────
    # Speech callback
    # ─────────────────────────────────────────────────────────────────────────

    def _on_speech_result(self, text: str) -> None:
        """Called by VoiceEngine after recognition completes."""
        if not text or not text.strip():
            self.gui.set_state("idle")
            self.gui.add_log("No se detectó audio.", "dim")
            return

        self.gui.set_recognized_text(text)
        self.gui.add_log(f'Reconocido: "{text}"', "info")

        # Dispatch command handling to a background thread so the GUI stays live
        threading.Thread(
            target=self._handle_command, args=(text,), daemon=True
        ).start()

    # ─────────────────────────────────────────────────────────────────────────
    # Command dispatcher
    # ─────────────────────────────────────────────────────────────────────────

    def _handle_command(self, text: str) -> None:
        intent, entities = self.processor.process(text)

        if intent is None:
            self._speak(f"No entendí el comando: {text}")
            self.gui.add_log(f'Comando no reconocido: "{text}"', "warning")
            self.gui.set_state("idle")
            return

        # Show intent in the GUI
        entity_summary = ", ".join(f"{k}={v}" for k, v in entities.items())
        display = f"{intent}  {entity_summary}".strip()
        self.gui.set_last_command(display)
        self.gui.add_log(f"Ejecutando: {intent}", "success")

        # ── Dispatch ──────────────────────────────────────────────────────────
        try:
            if intent == "shutdown":
                self.actions.shutdown()

            elif intent == "restart":
                self.actions.restart()

            elif intent == "sleep":
                self.actions.sleep()

            elif intent == "open_program":
                self.actions.open_program(entities.get("program", ""))

            elif intent == "close_program":
                self.actions.close_program(entities.get("program", ""))

            elif intent == "open_whatsapp_chrome":
                self.actions.open_whatsapp_chrome()

            elif intent == "send_whatsapp":
                self.actions.send_whatsapp_message(
                    entities.get("contact", ""),
                    entities.get("message", ""),
                )

            elif intent == "play_youtube":
                self.actions.play_youtube(entities.get("query", ""))

            elif intent == "open_website":
                self.actions.open_website(entities.get("site", ""))

            elif intent == "volume_up":
                self.actions.volume_up()

            elif intent == "volume_down":
                self.actions.volume_down()

            elif intent == "mute":
                self.actions.mute()

            elif intent == "screenshot":
                self.actions.take_screenshot()

            elif intent == "time":
                self.actions.get_time()

            elif intent == "date":
                self.actions.get_date()

            elif intent == "system_info":
                self.actions.get_system_info()

            elif intent == "move_file":
                self.actions.move_file(
                    entities.get("source", ""),
                    entities.get("dest", ""),
                )

            elif intent == "help":
                self.actions.show_help()

            else:
                self._speak(f"Acción {intent} no implementada todavía.")
                self.gui.add_log(f"Intent sin handler: {intent}", "warning")

        except Exception as exc:
            self.gui.add_log(f"Error ejecutando {intent}: {exc}", "error")
            self._speak("Ocurrió un error al ejecutar el comando.")
        finally:
            self.gui.set_state("idle")

    # ─────────────────────────────────────────────────────────────────────────
    # Speech output
    # ─────────────────────────────────────────────────────────────────────────

    def _speak(self, text: str) -> None:
        """Update GUI state and delegate to the TTS engine."""
        self.gui.set_state("speaking")
        self.gui.add_log(f"JARVIS: {text}", "success")
        if self.voice:
            self.voice.speak(text)

    # ─────────────────────────────────────────────────────────────────────────
    # Run / cleanup
    # ─────────────────────────────────────────────────────────────────────────

    def run(self) -> None:
        """Start the GUI main loop.  Blocks until the window is closed."""
        try:
            self.gui.run()
        finally:
            self._cleanup()

    def _cleanup(self) -> None:
        try:
            keyboard.unhook_all()
        except Exception:
            pass
        try:
            self.actions.cleanup()
        except Exception:
            pass
        if self.voice:
            try:
                self.voice.cleanup()
            except Exception:
                pass


# ── Bootstrap ─────────────────────────────────────────────────────────────────

def _ensure_model() -> None:
    """
    If the Vosk model folder is missing, offer to run setup_jarvis.py
    before the GUI starts (for CLI users who haven't set up yet).
    """
    if not os.path.isdir(cfg.MODEL_PATH):
        print(
            f"\n[JARVIS] El modelo de voz no está en '{cfg.MODEL_PATH}'."
            "\n[JARVIS] Ejecutando setup_jarvis.py para descargarlo…\n"
        )
        try:
            subprocess.run(
                [sys.executable, "setup_jarvis.py"],
                check=False,
            )
        except Exception as exc:
            print(f"[JARVIS] No se pudo ejecutar setup_jarvis.py: {exc}")
        print()


if __name__ == "__main__":
    # Optionally auto-run setup if model is absent (non-blocking in GUI sense:
    # setup runs synchronously in console before the window opens)
    _ensure_model()

    jarvis = JARVIS()
    jarvis.run()
