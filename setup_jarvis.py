"""
JARVIS Setup Script
Downloads the Vosk Spanish model and verifies all dependencies.
Run this script once before launching JARVIS.
"""

import os
import sys
import subprocess
import urllib.request
import zipfile
import shutil

# ── Configuration ──────────────────────────────────────────────────────────────
MODEL_NAME = "vosk-model-small-es-0.42"
MODEL_DIR  = os.path.join("models", MODEL_NAME)
MODEL_URL  = f"https://alphacephei.com/vosk/models/{MODEL_NAME}.zip"
ZIP_PATH   = os.path.join("models", f"{MODEL_NAME}.zip")

REQUIRED_PACKAGES = [
    "customtkinter",
    "vosk",
    "SpeechRecognition",
    "pyttsx3",
    "pyaudio",
    "selenium",
    "webdriver_manager",
    "pyautogui",
    "keyboard",
    "rapidfuzz",
    "psutil",
    "requests",
    "PIL",          # Pillow
    "pycaw",
    "comtypes",
]

# ── Helpers ────────────────────────────────────────────────────────────────────

def banner(msg: str) -> None:
    width = 60
    print("\n" + "─" * width)
    print(f"  {msg}")
    print("─" * width)


def check_python_version() -> None:
    banner("Checking Python version")
    major, minor = sys.version_info[:2]
    print(f"  Python {major}.{minor} detected.")
    if major < 3 or (major == 3 and minor < 8):
        print("  [ERROR] Python 3.8 or newer is required.")
        sys.exit(1)
    print("  [OK] Python version is compatible.")


def check_packages() -> list[str]:
    """Return list of packages that could NOT be imported."""
    banner("Checking installed packages")
    missing = []
    for pkg in REQUIRED_PACKAGES:
        try:
            __import__(pkg)
            print(f"  [OK]  {pkg}")
        except ImportError:
            print(f"  [!!] MISSING: {pkg}")
            missing.append(pkg)
    return missing


def install_packages(missing: list[str]) -> None:
    banner("Installing missing packages")
    pip_names = {
        "PIL": "Pillow",
        "webdriver_manager": "webdriver-manager",
        "pycaw": "pycaw",
    }
    for pkg in missing:
        pip_pkg = pip_names.get(pkg, pkg)
        print(f"  Installing {pip_pkg} ...")
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", pip_pkg],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            print(f"  [OK]  {pip_pkg} installed.")
        except subprocess.CalledProcessError:
            print(f"  [ERROR] Could not install {pip_pkg}. Install it manually.")


def _progress_hook(count: int, block_size: int, total_size: int) -> None:
    percent = min(100, int(count * block_size * 100 / total_size))
    bar = "#" * (percent // 2)
    print(f"\r  [{bar:<50}] {percent:3d}%", end="", flush=True)


def download_model() -> None:
    banner("Vosk Spanish Model")

    if os.path.isdir(MODEL_DIR):
        print(f"  [OK] Model already present at: {MODEL_DIR}")
        return

    os.makedirs("models", exist_ok=True)

    print(f"  Downloading model from:\n  {MODEL_URL}\n")
    print("  This may take a few minutes (≈ 40 MB) …")

    try:
        urllib.request.urlretrieve(MODEL_URL, ZIP_PATH, reporthook=_progress_hook)
        print()  # newline after progress bar
    except Exception as exc:
        print(f"\n  [ERROR] Download failed: {exc}")
        print("  Please download manually from https://alphacephei.com/vosk/models")
        print(f"  and extract to: {MODEL_DIR}")
        return

    print("  Extracting …")
    try:
        with zipfile.ZipFile(ZIP_PATH, "r") as zf:
            zf.extractall("models")
        os.remove(ZIP_PATH)
        print(f"  [OK] Model extracted to: {MODEL_DIR}")
    except zipfile.BadZipFile as exc:
        print(f"  [ERROR] Extraction failed: {exc}")
        if os.path.exists(ZIP_PATH):
            os.remove(ZIP_PATH)


def print_instructions() -> None:
    banner("Setup Complete — How to Run JARVIS")
    print("""
  1. Make sure you are in the JARVIS project directory:
       cd path\\to\\JARVIS

  2. (Optional) Activate your virtual environment:
       .venv\\Scripts\\activate

  3. Launch JARVIS:
       python main.py

  ─────────────────────────────────────────────────
  USAGE
  ─────────────────────────────────────────────────
  • Hold the [0] key (numpad or keyboard row)
    while speaking your command in Spanish.
  • Release the key to stop recording.
  • JARVIS will recognise your speech and act.

  EXAMPLE COMMANDS (Spanish)
  ─────────────────────────────────────────────────
  "Abre Chrome"
  "Pon música de Metallica en YouTube"
  "Manda un mensaje a Juan por WhatsApp que diga Hola"
  "Sube el volumen"
  "Apaga el ordenador"
  "Haz una captura de pantalla"
  "¿Qué hora es?"
  "Información del sistema"

  ─────────────────────────────────────────────────
  First-time WhatsApp use: the browser will open
  Web WhatsApp — scan the QR code once and the
  session will be reused automatically.
  ─────────────────────────────────────────────────
""")


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    print("\n" + "=" * 60)
    print("   J.A.R.V.I.S  —  Setup & Dependency Checker")
    print("=" * 60)

    check_python_version()

    missing = check_packages()
    if missing:
        install_packages(missing)
        # Re-check after installation
        still_missing = check_packages()
        if still_missing:
            print("\n  [WARNING] The following packages are still missing:")
            for p in still_missing:
                print(f"    - {p}")
            print("  JARVIS may not work correctly until they are installed.")
    else:
        print("\n  All packages are installed.")

    download_model()
    print_instructions()


if __name__ == "__main__":
    main()
