"""
JARVIS Actions
All action implementations: system control, programs, browser automation,
volume, files, screenshots, and informational queries.
"""

import os
import platform
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from datetime import datetime

import psutil
import pyautogui

# Selenium
from selenium import webdriver
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

# Windows volume control (optional — only available on Windows with pycaw)
try:
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

    PYCAW_AVAILABLE = True
except ImportError:
    PYCAW_AVAILABLE = False

import config as cfg


class Actions:
    """
    Provides all JARVIS capabilities.

    Parameters
    ----------
    speak_func : callable(str)
        Function used to output speech (provided by main.py / VoiceEngine).
    log_func : callable(str, level='info')
        Function used to append messages to the GUI activity log.
    """

    def __init__(self, speak_func, log_func):
        self.speak = speak_func
        self.log = log_func
        self.chrome_driver: webdriver.Chrome | None = None
        self._driver_lock = threading.Lock()

    # ─────────────────────────────────────────────────────────────────────────
    # SYSTEM POWER
    # ─────────────────────────────────────────────────────────────────────────

    def shutdown(self) -> None:
        self.speak("Apagando el ordenador. Hasta pronto.")
        time.sleep(3)
        if platform.system() == "Windows":
            os.system("shutdown /s /t 0")
        else:
            os.system("shutdown -h now")

    def restart(self) -> None:
        self.speak("Reiniciando el ordenador.")
        time.sleep(3)
        if platform.system() == "Windows":
            os.system("shutdown /r /t 0")
        else:
            os.system("reboot")

    def sleep(self) -> None:
        self.speak("Poniendo el ordenador en suspensión.")
        time.sleep(2)
        if platform.system() == "Windows":
            os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
        else:
            os.system("systemctl suspend")

    # ─────────────────────────────────────────────────────────────────────────
    # PROGRAMS
    # ─────────────────────────────────────────────────────────────────────────

    def open_program(self, program_name: str) -> bool:
        """Open a program by its Spanish alias or fuzzy-matched executable."""
        name_lower = program_name.lower().strip()

        # 1. Exact / substring match against known aliases
        exe = self._resolve_program_name(name_lower)

        if exe and platform.system() == "Windows":
            # On Windows use 'start' — works for PATH programs, registered apps
            # and apps like Chrome that aren't in PATH but are registered.
            for cmd in (
                f'start "" "{exe}"',   # quoted exe (full path or registered name)
                f'start "" {exe}',     # unquoted
                exe,                   # direct last resort
            ):
                try:
                    ret = subprocess.Popen(cmd, shell=True)
                    # Small delay then check if process started (start always
                    # returns 0, so we just trust it and log)
                    self.speak(f"Abriendo {program_name}.")
                    self.log(f"Programa iniciado: {exe}")
                    return True
                except Exception:
                    continue

        elif exe:  # Linux / Mac
            try:
                subprocess.Popen(exe, shell=True)
                self.speak(f"Abriendo {program_name}.")
                self.log(f"Programa abierto: {exe}")
                return True
            except Exception as exc:
                self.log(f"Error abriendo {exe}: {exc}", "warning")

        # 2. Search common Windows install directories for the .exe
        if platform.system() == "Windows":
            found_path = self._find_program_windows(name_lower)
            if found_path:
                try:
                    os.startfile(found_path)
                    self.speak(f"Abriendo {program_name}.")
                    self.log(f"Ejecutable encontrado: {found_path}")
                    return True
                except Exception as exc:
                    self.log(f"Error lanzando {found_path}: {exc}", "warning")

        self.speak(f"No encontré el programa {program_name}.")
        self.log(f"Programa no encontrado: {program_name}", "warning")
        return False

    def _resolve_program_name(self, name_lower: str) -> str | None:
        """Return an executable string from the PROGRAMS dict, or None."""
        # Direct key match
        if name_lower in cfg.PROGRAMS:
            return cfg.PROGRAMS[name_lower]
        # Substring match (e.g. "google chrome" matches key "google chrome")
        for key, val in cfg.PROGRAMS.items():
            if key in name_lower or name_lower in key:
                return val
        # Fuzzy fallback
        try:
            from rapidfuzz import fuzz
            from rapidfuzz import process as fuzz_process

            keys = list(cfg.PROGRAMS.keys())
            result = fuzz_process.extractOne(
                name_lower, keys, scorer=fuzz.partial_ratio, score_cutoff=75
            )
            if result:
                return cfg.PROGRAMS[result[0]]
        except ImportError:
            pass
        return None

    def _find_program_windows(self, name: str) -> str | None:
        """Walk common Windows install dirs looking for a matching .exe."""
        search_dirs = [
            os.environ.get("ProgramFiles", r"C:\Program Files"),
            os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs"),
            os.environ.get("SystemRoot", r"C:\Windows"),
            os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32"),
        ]
        name_clean = name.replace(" ", "").replace("-", "")

        for search_dir in search_dirs:
            if not os.path.isdir(search_dir):
                continue
            for root, _dirs, files in os.walk(search_dir):
                # Limit depth to avoid extremely long scans
                depth = root.replace(search_dir, "").count(os.sep)
                if depth > 3:
                    break
                for fname in files:
                    if fname.lower().endswith(".exe"):
                        exe_stem = (
                            fname.lower()
                            .replace(".exe", "")
                            .replace(" ", "")
                            .replace("-", "")
                        )
                        if name_clean in exe_stem or exe_stem in name_clean:
                            return os.path.join(root, fname)

        # Last resort: 'where' command (Windows)
        try:
            result = subprocess.run(
                ["where", name], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                first_line = result.stdout.strip().splitlines()[0]
                if first_line:
                    return first_line
        except Exception:
            pass

        return None

    def close_program(self, program_name: str) -> bool:
        """Kill all processes whose name contains *program_name*."""
        name_lower = program_name.lower().strip()
        killed = 0

        for proc in psutil.process_iter(["pid", "name"]):
            try:
                if name_lower in proc.info["name"].lower():
                    proc.kill()
                    killed += 1
                    self.log(f"Proceso terminado: {proc.info['name']}")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        if killed:
            self.speak(f"He cerrado {program_name}.")
            return True

        self.speak(f"No encontré ningún proceso llamado {program_name}.")
        self.log(f"Proceso no encontrado: {program_name}", "warning")
        return False

    # ─────────────────────────────────────────────────────────────────────────
    # BROWSER / WEB
    # ─────────────────────────────────────────────────────────────────────────

    def _open_url_in_existing_chrome(self, url: str) -> bool:
        """
        Open *url* in the user's existing Chrome window (with their real session).
        Uses 'start chrome URL' on Windows which reuses the running instance.
        Falls back to webbrowser if Chrome is not found.
        """
        if platform.system() == "Windows":
            try:
                # This opens a new tab in the already-running Chrome
                subprocess.Popen(f'start chrome "{url}"', shell=True)
                return True
            except Exception:
                pass
            # Try common Chrome paths
            chrome_paths = [
                os.path.join(os.environ.get("ProgramFiles", ""), "Google", "Chrome", "Application", "chrome.exe"),
                os.path.join(os.environ.get("ProgramFiles(x86)", ""), "Google", "Chrome", "Application", "chrome.exe"),
                os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "Application", "chrome.exe"),
            ]
            for path in chrome_paths:
                if os.path.isfile(path):
                    try:
                        subprocess.Popen([path, url])
                        return True
                    except Exception:
                        pass
        webbrowser.open(url)
        return True

    def _get_whatsapp_driver(self) -> webdriver.Chrome | None:
        """
        Create a Chrome WebDriver with the JARVIS WhatsApp profile.
        This profile persists between runs — QR scan only needed once.
        """
        try:
            profile_path = os.path.abspath(cfg.WHATSAPP_PROFILE)
            os.makedirs(profile_path, exist_ok=True)

            options = webdriver.ChromeOptions()
            options.add_argument(f"--user-data-dir={profile_path}")
            options.add_argument("--profile-directory=Default")
            options.add_argument("--start-maximized")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-session-crashed-bubble")
            options.add_argument("--no-first-run")
            options.add_argument("--no-default-browser-check")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("useAutomationExtension", False)

            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
            return driver
        except WebDriverException as exc:
            self.log(f"Error ChromeDriver: {exc}", "error")
            return None

    def open_website(self, site: str) -> None:
        """Open *site* in the user's existing Chrome (with their real session)."""
        site_lower = site.lower().strip()
        url: str | None = None
        for key, val in cfg.WEBSITES.items():
            if key in site_lower:
                url = val
                break
        if not url:
            if site_lower.startswith("http"):
                url = site_lower
            elif "." in site_lower:
                url = f"https://{site_lower}"
            else:
                url = f"https://www.google.com/search?q={site_lower.replace(' ', '+')}"
        self._open_url_in_existing_chrome(url)
        self.speak(f"Abriendo {site}.")
        self.log(f"Web abierta: {url}")

    def open_whatsapp_chrome(self) -> None:
        """Open WhatsApp Web as a new tab in the user's existing Chrome."""
        self._open_url_in_existing_chrome("https://web.whatsapp.com")
        self.speak("Abriendo WhatsApp en Chrome.")
        self.log("WhatsApp Web abierto en Chrome existente.")

    # ── WhatsApp helpers ──────────────────────────────────────────────────────

    def _is_whatsapp_app_running(self) -> bool:
        """Return True if the WhatsApp desktop process is running."""
        for proc in psutil.process_iter(["name"]):
            try:
                if "whatsapp" in proc.info["name"].lower():
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return False

    def _focus_window(self, partial_title: str) -> bool:
        """Bring a visible window whose title contains *partial_title* to front."""
        if platform.system() != "Windows":
            return False
        try:
            import ctypes
            found = [None]
            EnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)

            def _cb(hwnd, _):
                if ctypes.windll.user32.IsWindowVisible(hwnd):
                    length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
                    buf = ctypes.create_unicode_buffer(length + 1)
                    ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
                    if partial_title.lower() in buf.value.lower():
                        found[0] = hwnd
                        return False
                return True

            ctypes.windll.user32.EnumWindows(EnumProc(_cb), 0)
            if found[0]:
                ctypes.windll.user32.ShowWindow(found[0], 9)   # SW_RESTORE
                ctypes.windll.user32.SetForegroundWindow(found[0])
                return True
        except Exception as exc:
            self.log(f"Error buscando ventana '{partial_title}': {exc}", "warning")
        return False

    def _paste_text(self, text: str) -> None:
        """Copy *text* to the clipboard and paste it (handles special chars)."""
        try:
            import pyperclip
            pyperclip.copy(text)
            pyautogui.hotkey("ctrl", "v")
        except Exception:
            pyautogui.write(text, interval=0.03)

    def _send_via_whatsapp_app(self, contact: str, message: str) -> bool:
        """
        Control the WhatsApp desktop app with pyautogui.
        Searches for *contact* using Ctrl+N (New Chat / search), opens the
        conversation, and sends *message* via the clipboard.
        """
        try:
            # 1. Focus WhatsApp window
            if not self._focus_window("WhatsApp"):
                self.log("Ventana de WhatsApp no encontrada.", "warning")
                return False
            time.sleep(0.8)

            # 2. Open new-chat / contact search with Ctrl+N
            pyautogui.hotkey("ctrl", "n")
            time.sleep(0.6)

            # 3. Type the contact name (use clipboard to avoid encoding issues)
            self._paste_text(contact)
            time.sleep(1.5)   # wait for search results

            # 4. Press Enter / Down + Enter to select the first result
            pyautogui.press("down")
            time.sleep(0.3)
            pyautogui.press("enter")
            time.sleep(0.8)

            # 5. Send message via clipboard
            self._paste_text(message)
            time.sleep(0.3)
            pyautogui.press("enter")

            self.speak(f"Mensaje enviado a {contact} desde la app de WhatsApp.")
            self.log(f"WhatsApp App → {contact}: {message}", "success")
            return True

        except Exception as exc:
            self.log(f"Error controlando WhatsApp App: {exc}", "warning")
            return False

    def _send_via_whatsapp_web_selenium(self, contact: str, message: str) -> bool:
        """Send via WhatsApp Web using the persistent Selenium profile."""
        try:
            with self._driver_lock:
                if self.chrome_driver is None:
                    driver = self._get_whatsapp_driver()
                    if not driver:
                        self.speak("No pude abrir Chrome para WhatsApp.")
                        return False
                    self.chrome_driver = driver

                driver = self.chrome_driver

                if "web.whatsapp.com" not in driver.current_url:
                    driver.get("https://web.whatsapp.com")
                    self.speak("Abriendo WhatsApp, espera un momento.")
                    time.sleep(6)

                wait = WebDriverWait(driver, 30)

                # ── Find the search box ───────────────────────────────────────
                search_selectors = [
                    (By.XPATH, "//div[@data-testid='chat-list-search']//div[@contenteditable='true']"),
                    (By.XPATH, "//div[@role='textbox'][@title='Buscar o empezar un nuevo chat']"),
                    (By.XPATH, "//div[contains(@class,'copyable-text selectable-text')][@data-tab='3']"),
                ]
                search_box = None
                for by, selector in search_selectors:
                    try:
                        search_box = wait.until(
                            EC.presence_of_element_located((by, selector))
                        )
                        break
                    except TimeoutException:
                        continue

                if search_box is None:
                    self.speak(
                        "WhatsApp no ha cargado todavía. Por favor escanea el código QR primero."
                    )
                    return False

                search_box.click()
                time.sleep(0.4)
                # Clear any existing text
                search_box.send_keys(Keys.CONTROL + "a")
                search_box.send_keys(Keys.DELETE)
                search_box.send_keys(contact)
                time.sleep(2)

                # ── Click on the contact ──────────────────────────────────────
                try:
                    contact_elem = wait.until(
                        EC.presence_of_element_located(
                            (By.XPATH, f"//span[@title='{contact}']")
                        )
                    )
                    contact_elem.click()
                except TimeoutException:
                    # Fall back to clicking the first search result
                    try:
                        first_result = driver.find_element(
                            By.XPATH, "//div[@data-testid='cell-frame-container']"
                        )
                        first_result.click()
                    except NoSuchElementException:
                        self.speak(f"No encontré el contacto {contact} en WhatsApp.")
                        return False

                time.sleep(1)

                # ── Type and send the message ─────────────────────────────────
                msg_selectors = [
                    (By.XPATH, "//div[@data-testid='conversation-compose-box-input']"),
                    (By.XPATH, "//div[@role='textbox'][@data-tab='10']"),
                    (By.XPATH, "//div[contains(@class,'copyable-text')][@contenteditable='true'][@data-tab='10']"),
                ]
                msg_box = None
                for by, selector in msg_selectors:
                    try:
                        msg_box = wait.until(
                            EC.presence_of_element_located((by, selector))
                        )
                        break
                    except TimeoutException:
                        continue

                if msg_box is None:
                    self.speak("No pude encontrar el cuadro de mensaje en WhatsApp.")
                    return False

                msg_box.click()
                msg_box.send_keys(message)
                time.sleep(0.4)
                msg_box.send_keys(Keys.ENTER)

                self.speak(f"Mensaje enviado a {contact}.")
                self.log(f"WhatsApp Web → {contact}: {message}", "success")
                return True

        except Exception as exc:
            self.log(f"Error enviando mensaje WhatsApp Web: {exc}", "error")
            self.speak("Hubo un error al intentar enviar el mensaje por WhatsApp.")
            return False

    def send_whatsapp_message(self, contact: str, message: str) -> bool:
        """
        Send *message* to *contact* via WhatsApp.
        Priority:
          1. WhatsApp desktop app (if the process is running) → pyautogui
          2. WhatsApp Web via persistent Selenium profile → Selenium
        """
        if not contact or not message:
            self.speak("Necesito saber a quién enviar el mensaje y qué decir.")
            return False

        # ── 1. WhatsApp desktop app ───────────────────────────────────────────
        if self._is_whatsapp_app_running():
            self.log("WhatsApp App detectada. Usando la aplicación.", "info")
            self.speak(f"Enviando mensaje a {contact} desde la app de WhatsApp.")
            if self._send_via_whatsapp_app(contact, message):
                return True
            self.log("Fallo en la app, intentando con WhatsApp Web.", "warning")

        # ── 2. WhatsApp Web via Selenium (persistent profile) ─────────────────
        self.log("Usando WhatsApp Web con perfil persistente.", "info")
        self.speak(f"Abriendo WhatsApp Web para enviar el mensaje a {contact}.")
        return self._send_via_whatsapp_web_selenium(contact, message)

    def play_youtube(self, query: str) -> bool:
        """Open YouTube search in the user's existing Chrome (with their session)."""
        search_url = (
            f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
        )
        self._open_url_in_existing_chrome(search_url)
        self.speak(f"Buscando {query} en YouTube.")
        self.log(f"YouTube: {query}")
        return True

    # ─────────────────────────────────────────────────────────────────────────
    # VOLUME
    # ─────────────────────────────────────────────────────────────────────────

    def _get_volume_interface(self):
        """Return a pycaw IAudioEndpointVolume interface, or None."""
        if not PYCAW_AVAILABLE or platform.system() != "Windows":
            return None
        try:
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            return interface.QueryInterface(IAudioEndpointVolume)
        except Exception:
            return None

    def volume_up(self, amount: int = 10) -> None:
        vol = self._get_volume_interface()
        if vol:
            try:
                current = vol.GetMasterVolumeLevelScalar()
                new_vol = min(1.0, current + amount / 100)
                vol.SetMasterVolumeLevelScalar(new_vol, None)
                self.speak(f"Volumen al {int(new_vol * 100)} por ciento.")
                self.log(f"Volumen subido a {int(new_vol * 100)}%")
                return
            except Exception:
                pass
        # Keyboard fallback
        for _ in range(max(1, amount // 2)):
            pyautogui.press("volumeup")
        self.speak("Subiendo el volumen.")

    def volume_down(self, amount: int = 10) -> None:
        vol = self._get_volume_interface()
        if vol:
            try:
                current = vol.GetMasterVolumeLevelScalar()
                new_vol = max(0.0, current - amount / 100)
                vol.SetMasterVolumeLevelScalar(new_vol, None)
                self.speak(f"Volumen al {int(new_vol * 100)} por ciento.")
                self.log(f"Volumen bajado a {int(new_vol * 100)}%")
                return
            except Exception:
                pass
        for _ in range(max(1, amount // 2)):
            pyautogui.press("volumedown")
        self.speak("Bajando el volumen.")

    def mute(self) -> None:
        vol = self._get_volume_interface()
        if vol:
            try:
                muted = vol.GetMute()
                vol.SetMute(not muted, None)
                state = "Silenciado." if not muted else "Audio activado."
                self.speak(state)
                self.log(state)
                return
            except Exception:
                pass
        pyautogui.press("volumemute")
        self.speak("Silenciado.")

    # ─────────────────────────────────────────────────────────────────────────
    # FILES
    # ─────────────────────────────────────────────────────────────────────────

    def move_file(self, source: str, destination: str) -> bool:
        """Move or copy *source* to *destination*."""
        try:
            source = os.path.expanduser(source.strip("\"'"))
            destination = os.path.expanduser(destination.strip("\"'"))

            if not os.path.exists(source):
                self.speak(f"No encontré el archivo o carpeta en {source}.")
                self.log(f"Archivo no encontrado: {source}", "warning")
                return False

            # If destination looks like a directory, create it
            if not os.path.splitext(destination)[1]:
                os.makedirs(destination, exist_ok=True)

            shutil.move(source, destination)
            self.speak("Archivo movido correctamente.")
            self.log(f"Movido: {source} → {destination}", "success")
            return True
        except Exception as exc:
            self.log(f"Error moviendo archivo: {exc}", "error")
            self.speak("No pude mover el archivo. Revisa las rutas.")
            return False

    # ─────────────────────────────────────────────────────────────────────────
    # SCREENSHOT
    # ─────────────────────────────────────────────────────────────────────────

    def take_screenshot(self) -> str | None:
        """Capture the screen and save it to the Desktop (or home dir)."""
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_dir = cfg.SCREENSHOTS_DIR
            os.makedirs(save_dir, exist_ok=True)
            filepath = os.path.join(save_dir, f"JARVIS_{ts}.png")

            screenshot = pyautogui.screenshot()
            screenshot.save(filepath)

            self.speak(f"Captura guardada como JARVIS {ts}.")
            self.log(f"Screenshot guardado: {filepath}", "success")
            return filepath
        except Exception as exc:
            self.log(f"Error haciendo screenshot: {exc}", "error")
            self.speak("No pude hacer la captura de pantalla.")
            return None

    # ─────────────────────────────────────────────────────────────────────────
    # TIME & DATE
    # ─────────────────────────────────────────────────────────────────────────

    def get_time(self) -> str:
        now = datetime.now()
        h, m = now.hour, now.minute
        if m == 0:
            phrase = f"Son las {h} en punto."
        elif m == 1:
            phrase = f"Son las {h} y un minuto."
        else:
            phrase = f"Son las {h} y {m} minutos."
        self.speak(phrase)
        self.log(f"Hora consultada: {now.strftime('%H:%M')}")
        return now.strftime("%H:%M")

    def get_date(self) -> str:
        now = datetime.now()
        days = [
            "lunes", "martes", "miércoles", "jueves",
            "viernes", "sábado", "domingo",
        ]
        months = [
            "enero", "febrero", "marzo", "abril", "mayo", "junio",
            "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
        ]
        day_name = days[now.weekday()]
        month_name = months[now.month - 1]
        text = f"Hoy es {day_name} {now.day} de {month_name} de {now.year}."
        self.speak(text)
        self.log(f"Fecha consultada: {now.strftime('%d/%m/%Y')}")
        return text

    # ─────────────────────────────────────────────────────────────────────────
    # SYSTEM INFO
    # ─────────────────────────────────────────────────────────────────────────

    def get_system_info(self) -> dict:
        cpu = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory()
        try:
            disk = psutil.disk_usage("/")
        except Exception:
            try:
                disk = psutil.disk_usage("C:\\")
            except Exception:
                disk = None

        ram_free_gb = ram.available // (1024 ** 3)
        ram_total_gb = ram.total // (1024 ** 3)

        text = (
            f"CPU al {cpu:.0f} por ciento. "
            f"Memoria RAM: {ram.percent:.0f} por ciento en uso, "
            f"{ram_free_gb} gigas libres de {ram_total_gb}."
        )
        if disk:
            text += f" Disco principal al {disk.percent:.0f} por ciento de uso."

        self.speak(text)
        self.log(f"Info sistema — CPU:{cpu:.0f}% RAM:{ram.percent:.0f}%")
        return {
            "cpu": cpu,
            "ram": ram.percent,
            "disk": disk.percent if disk else 0,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # HELP
    # ─────────────────────────────────────────────────────────────────────────

    def show_help(self) -> str:
        help_text = (
            "Puedo ayudarte con: "
            "Abrir y cerrar programas como Chrome, Discord o Spotify. "
            "Apagar, reiniciar o suspender el ordenador. "
            "Enviar mensajes por WhatsApp. "
            "Reproducir música o vídeos en YouTube. "
            "Abrir páginas web. "
            "Subir, bajar o silenciar el volumen. "
            "Hacer capturas de pantalla. "
            "Decirte la hora o la fecha actual. "
            "Mostrar información del sistema. "
            "Y mover archivos de un lugar a otro."
        )
        self.speak(help_text)
        self.log("Ayuda mostrada.")
        return help_text

    # ─────────────────────────────────────────────────────────────────────────
    # CLEANUP
    # ─────────────────────────────────────────────────────────────────────────

    def cleanup(self) -> None:
        """Release Selenium drivers and any other held resources."""
        with self._driver_lock:
            if self.chrome_driver is not None:
                try:
                    self.chrome_driver.quit()
                except Exception:
                    pass
                self.chrome_driver = None
