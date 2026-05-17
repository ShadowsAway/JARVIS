"""
JARVIS Voice Engine
Offline speech recognition via Vosk + text-to-speech via pyttsx3.
Uses sounddevice instead of pyaudio (easier to install on Windows).
"""

import json
import queue
import threading

import sounddevice as sd
import pyttsx3
import vosk


class VoiceEngine:
    SAMPLE_RATE    = 16000
    BLOCK_SIZE     = 4096
    CHANNELS       = 1
    DTYPE          = "int16"

    def __init__(self, model_path: str, on_result_callback):
        vosk.SetLogLevel(-1)
        self.model         = vosk.Model(model_path)
        self.audio_queue: queue.Queue = queue.Queue()
        self.is_recording  = False
        self.on_result     = on_result_callback
        self._stream       = None

        self.tts           = pyttsx3.init()
        self.tts_thread: threading.Thread | None = None
        self._tts_lock     = threading.Lock()
        self._setup_tts()

    def _setup_tts(self) -> None:
        voices = self.tts.getProperty("voices")
        spanish_keywords = ("spanish", "helena", "sabina", "jorge",
                            "es-es", "es_es", "pablo", "microsoft pablo",
                            "microsoft helena", "microsoft sabina")
        for v in voices:
            if any(kw in v.name.lower() or kw in v.id.lower() for kw in spanish_keywords):
                self.tts.setProperty("voice", v.id)
                break
        self.tts.setProperty("rate",   175)
        self.tts.setProperty("volume", 0.9)

    # ── Recording ─────────────────────────────────────────────────────────────

    def start_recording(self) -> None:
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                break

        self.is_recording = True
        self._stream = sd.RawInputStream(
            samplerate=self.SAMPLE_RATE,
            blocksize=self.BLOCK_SIZE,
            dtype=self.DTYPE,
            channels=self.CHANNELS,
            callback=self._audio_callback,
        )
        self._stream.start()

    def _audio_callback(self, indata, frames, time_info, status):
        if self.is_recording:
            self.audio_queue.put(bytes(indata))

    def stop_recording(self) -> None:
        self.is_recording = False
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        threading.Thread(target=self._process_audio, daemon=True).start()

    # ── Recognition ───────────────────────────────────────────────────────────

    def _process_audio(self) -> None:
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
            if self.on_result:
                self.on_result("")
            return

        result = json.loads(rec.FinalResult())
        text   = result.get("text", "").strip()
        if self.on_result:
            self.on_result(text)

    # ── TTS ───────────────────────────────────────────────────────────────────

    def speak(self, text: str) -> None:
        def _speak() -> None:
            with self._tts_lock:
                try:
                    self.tts.say(text)
                    self.tts.runAndWait()
                except RuntimeError:
                    self.tts = pyttsx3.init()
                    self._setup_tts()
                    self.tts.say(text)
                    self.tts.runAndWait()
                except Exception:
                    pass

        self.tts_thread = threading.Thread(target=_speak, daemon=True)
        self.tts_thread.start()

    # ── Cleanup ───────────────────────────────────────────────────────────────

    def cleanup(self) -> None:
        self.is_recording = False
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
