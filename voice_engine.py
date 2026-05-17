"""
JARVIS Voice Engine
Offline speech recognition via Vosk + text-to-speech via pyttsx3.
"""

import json
import queue
import threading

import pyaudio
import pyttsx3
import vosk


class VoiceEngine:
    """
    Wraps Vosk ASR and pyttsx3 TTS into a simple push-to-talk interface.

    Usage
    -----
    engine = VoiceEngine(model_path, callback)
    engine.start_recording()   # called when push-to-talk key is pressed
    engine.stop_recording()    # called when key is released → fires callback
    engine.speak("Hello")
    engine.cleanup()
    """

    # ── Audio parameters ──────────────────────────────────────────────────────
    SAMPLE_RATE   = 16000
    CHANNELS      = 1
    FORMAT        = pyaudio.paInt16
    FRAMES_PER_BUF = 4096

    def __init__(self, model_path: str, on_result_callback):
        # ── ASR model ─────────────────────────────────────────────────────────
        vosk.SetLogLevel(-1)                          # suppress Vosk log spam
        self.model           = vosk.Model(model_path)
        self.audio_queue: queue.Queue = queue.Queue()
        self.is_recording    = False
        self.on_result       = on_result_callback

        # ── PyAudio ───────────────────────────────────────────────────────────
        self.pa     = pyaudio.PyAudio()
        self.stream = None

        # ── TTS ───────────────────────────────────────────────────────────────
        self.tts        = pyttsx3.init()
        self.tts_thread: threading.Thread | None = None
        self._tts_lock  = threading.Lock()
        self._setup_tts()

    # ── TTS setup ─────────────────────────────────────────────────────────────

    def _setup_tts(self) -> None:
        """Configure pyttsx3: prefer a Spanish voice, fall back gracefully."""
        voices = self.tts.getProperty("voices")

        spanish_voice_id = None
        spanish_keywords = ("spanish", " es", "helena", "sabina", "jorge",
                             "es-es", "es_es", "microsoft pablo",
                             "microsoft helena", "microsoft sabina")

        for v in voices:
            name_lower = v.name.lower()
            id_lower   = v.id.lower()
            if any(kw in name_lower or kw in id_lower for kw in spanish_keywords):
                spanish_voice_id = v.id
                break

        if spanish_voice_id:
            self.tts.setProperty("voice", spanish_voice_id)

        self.tts.setProperty("rate",   175)   # words per minute
        self.tts.setProperty("volume", 0.9)   # 0.0 – 1.0

    # ── Recording ─────────────────────────────────────────────────────────────

    def start_recording(self) -> None:
        """Open the microphone stream and begin buffering audio."""
        # Flush any leftover audio from a previous session
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                break

        self.is_recording = True

        self.stream = self.pa.open(
            format=self.FORMAT,
            channels=self.CHANNELS,
            rate=self.SAMPLE_RATE,
            input=True,
            frames_per_buffer=self.FRAMES_PER_BUF,
            stream_callback=self._audio_callback,
        )
        self.stream.start_stream()

    def _audio_callback(self, in_data, frame_count, time_info, status):
        """PyAudio callback — runs in a separate thread managed by PyAudio."""
        if self.is_recording:
            self.audio_queue.put(in_data)
        return (None, pyaudio.paContinue)

    def stop_recording(self) -> None:
        """Stop microphone capture and trigger recognition in a background thread."""
        self.is_recording = False

        if self.stream is not None:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None

        # Run recognition off the main thread so the GUI stays responsive
        threading.Thread(target=self._process_audio, daemon=True).start()

    # ── Recognition ───────────────────────────────────────────────────────────

    def _process_audio(self) -> None:
        """Feed all buffered audio chunks through a fresh Vosk recognizer."""
        rec = vosk.KaldiRecognizer(self.model, self.SAMPLE_RATE)

        has_data = False
        while not self.audio_queue.empty():
            try:
                data = self.audio_queue.get_nowait()
                rec.AcceptWaveform(data)
                has_data = True
            except queue.Empty:
                break

        if not has_data:
            # Nothing was captured
            if self.on_result:
                self.on_result("")
            return

        result = json.loads(rec.FinalResult())
        text   = result.get("text", "").strip()

        if self.on_result:
            self.on_result(text)

    # ── TTS ───────────────────────────────────────────────────────────────────

    def speak(self, text: str) -> None:
        """
        Speak *text* asynchronously so the GUI is never blocked.
        If a previous speech is still running, it is interrupted first.
        """
        def _speak() -> None:
            with self._tts_lock:
                try:
                    self.tts.say(text)
                    self.tts.runAndWait()
                except RuntimeError:
                    # pyttsx3 can throw RuntimeError if runAndWait is re-entered;
                    # re-initialise the engine and try once more.
                    self.tts = pyttsx3.init()
                    self._setup_tts()
                    self.tts.say(text)
                    self.tts.runAndWait()
                except Exception:
                    pass  # Silent fail — TTS is non-critical

        self.tts_thread = threading.Thread(target=_speak, daemon=True)
        self.tts_thread.start()

    # ── Cleanup ───────────────────────────────────────────────────────────────

    def cleanup(self) -> None:
        """Release all audio resources."""
        self.is_recording = False

        if self.stream is not None:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except Exception:
                pass
            self.stream = None

        try:
            self.pa.terminate()
        except Exception:
            pass
