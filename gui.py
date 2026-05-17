"""
JARVIS GUI
Futuristic Iron Man HUD interface built with customtkinter and Canvas animations.
"""

import math
import threading
import time
from datetime import datetime
from typing import Literal

import customtkinter as ctk
import psutil
from tkinter import Canvas, font as tkfont

import config as cfg

# ── Appearance ────────────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

# State type alias
StateType = Literal["idle", "listening", "processing", "speaking"]

# Colour map per state
STATE_COLORS: dict[str, dict[str, str]] = {
    "idle": {
        "orb":        cfg.DIM,
        "orb_inner":  "#0d2040",
        "arc1":       cfg.DIM,
        "arc2":       "#0a2030",
        "label":      cfg.DIM,
        "status_txt": "INACTIVO",
    },
    "listening": {
        "orb":        cfg.ACCENT,
        "orb_inner":  "#002a3a",
        "arc1":       cfg.ACCENT,
        "arc2":       cfg.ACCENT2,
        "label":      cfg.ACCENT,
        "status_txt": "ESCUCHANDO",
    },
    "processing": {
        "orb":        cfg.WARNING,
        "orb_inner":  "#2a1a00",
        "arc1":       cfg.WARNING,
        "arc2":       "#ff6600",
        "label":      cfg.WARNING,
        "status_txt": "PROCESANDO",
    },
    "speaking": {
        "orb":        cfg.SUCCESS,
        "orb_inner":  "#001a0d",
        "arc1":       cfg.SUCCESS,
        "arc2":       "#009944",
        "label":      cfg.SUCCESS,
        "status_txt": "HABLANDO",
    },
}


class JarvisGUI:
    """
    Main JARVIS HUD window.

    Public API
    ----------
    set_state(state)          – change visual state
    add_log(text, level)      – append a line to the activity log
    set_recognized_text(text) – display last recognised speech
    set_last_command(text)    – display last executed command
    run()                     – start the Tk main loop (blocking)
    """

    # ── Window geometry ───────────────────────────────────────────────────────
    WIN_W  = 1380
    WIN_H  = 720
    LEFT_W = 340
    RIGHT_W = 560
    CMD_W  = 480  # commands panel

    # ── Animation constants ───────────────────────────────────────────────────
    ORB_SIZE = 260           # diameter of the outer bounding box
    ORB_CX = LEFT_W // 2    # orb centre x in left panel
    ORB_CY = 175             # orb centre y in left panel canvas
    ANIM_INTERVAL_MS = 33    # ~30 fps
    STAT_INTERVAL_MS = 3000  # system stats refresh

    def __init__(self) -> None:
        self._state: StateType = "idle"
        self._on_command_callback = None
        self._arc1_angle: float = 0.0
        self._arc2_angle: float = 0.0
        self._scan_y: float = 0.0
        self._pulse: float = 0.0
        self._pulse_dir: float = 1.0
        self._blink_visible: bool = True
        self._blink_counter: int = 0
        self._wave_phase: float = 0.0
        self._running: bool = True

        self._build_window()
        self._build_left_panel()
        self._build_right_panel()
        self._build_commands_panel()
        self._start_animations()
        self._start_stat_updater()

    # ─────────────────────────────────────────────────────────────────────────
    # Window construction
    # ─────────────────────────────────────────────────────────────────────────

    def _build_window(self) -> None:
        self.root = ctk.CTk()
        self.root.title(f"{cfg.APP_NAME}  v{cfg.VERSION}")
        self.root.geometry(f"{self.WIN_W}x{self.WIN_H}")
        self.root.resizable(False, False)
        self.root.configure(fg_color=cfg.BG)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Outer grid: three columns
        self.root.grid_columnconfigure(0, minsize=self.LEFT_W)
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_columnconfigure(2, minsize=self.CMD_W)
        self.root.grid_rowconfigure(0, weight=1)

        # ── Title bar ─────────────────────────────────────────────────────────
        title_frame = ctk.CTkFrame(
            self.root, fg_color=cfg.BG, height=40, corner_radius=0
        )
        title_frame.grid(row=0, column=0, columnspan=3, sticky="new")

        ctk.CTkLabel(
            title_frame,
            text=f"◈  {cfg.APP_NAME}  —  Sistema de Inteligencia Artificial  ◈",
            font=ctk.CTkFont(family="Courier New", size=13, weight="bold"),
            text_color=cfg.ACCENT,
        ).pack(side="left", padx=20, pady=6)

        ctk.CTkLabel(
            title_frame,
            text=f"v{cfg.VERSION}",
            font=ctk.CTkFont(family="Courier New", size=11),
            text_color=cfg.DIM,
        ).pack(side="right", padx=20, pady=6)

        # Separator line
        sep = ctk.CTkFrame(
            self.root, fg_color=cfg.DIM, height=1, corner_radius=0
        )
        sep.grid(row=0, column=0, columnspan=3, sticky="sew", pady=(38, 0))

    # ─────────────────────────────────────────────────────────────────────────
    # Left panel
    # ─────────────────────────────────────────────────────────────────────────

    def _build_left_panel(self) -> None:
        self.left = ctk.CTkFrame(
            self.root, fg_color=cfg.BG, width=self.LEFT_W, corner_radius=0
        )
        self.left.grid(row=0, column=0, sticky="nsew", padx=0, pady=(45, 0))
        self.left.grid_propagate(False)

        # ── Orb canvas ────────────────────────────────────────────────────────
        self.orb_canvas = Canvas(
            self.left,
            width=self.LEFT_W,
            height=320,
            bg=cfg.BG,
            highlightthickness=0,
        )
        self.orb_canvas.pack(pady=(20, 0))

        # ── Waveform canvas ───────────────────────────────────────────────────
        self.wave_canvas = Canvas(
            self.left,
            width=self.LEFT_W,
            height=50,
            bg=cfg.BG,
            highlightthickness=0,
        )
        self.wave_canvas.pack(pady=(4, 0))

        # ── Status label ──────────────────────────────────────────────────────
        self.status_label = ctk.CTkLabel(
            self.left,
            text="INACTIVO",
            font=ctk.CTkFont(family="Courier New", size=16, weight="bold"),
            text_color=cfg.DIM,
        )
        self.status_label.pack(pady=(8, 2))

        # ── Hold key instruction ──────────────────────────────────────────────
        ctk.CTkLabel(
            self.left,
            text=f'[ Mantén pulsado  "0"  para hablar ]',
            font=ctk.CTkFont(family="Courier New", size=10),
            text_color=cfg.DIM,
        ).pack(pady=(0, 4))

        # ── Blink indicator ───────────────────────────────────────────────────
        self.blink_label = ctk.CTkLabel(
            self.left,
            text="● REC",
            font=ctk.CTkFont(family="Courier New", size=11, weight="bold"),
            text_color=cfg.BG,  # hidden by default
        )
        self.blink_label.pack(pady=(0, 6))

        # ── CPU / RAM mini bar ────────────────────────────────────────────────
        self.left_stat_label = ctk.CTkLabel(
            self.left,
            text="CPU: --%   RAM: --%",
            font=ctk.CTkFont(family="Courier New", size=10),
            text_color=cfg.DIM,
        )
        self.left_stat_label.pack(pady=(0, 4))

        # Draw initial orb
        self._draw_orb()

    def _draw_orb(self) -> None:
        """Redraw all orb elements on the canvas with current animation state."""
        c = self.orb_canvas
        c.delete("all")

        col = STATE_COLORS[self._state]
        cx, cy = self.ORB_CX, self.ORB_CY
        r = (self.ORB_SIZE // 2) + int(self._pulse * 6)  # breathing radius

        # ── Grid / crosshair lines ────────────────────────────────────────────
        grid_col = "#0a1828"
        for offset in range(-120, 130, 30):
            c.create_line(cx + offset, cy - r - 20, cx + offset, cy + r + 20,
                          fill=grid_col, width=1)
            c.create_line(cx - r - 20, cy + offset, cx + r + 20, cy + offset,
                          fill=grid_col, width=1)

        # ── Outer dashed ring (rotates clockwise) ─────────────────────────────
        self._draw_dashed_arc(c, cx, cy, r + 30, self._arc1_angle, col["arc1"],
                              dash_len=8, gap=6, width=2)

        # ── Middle ring (rotates counter-clockwise) ───────────────────────────
        self._draw_dashed_arc(c, cx, cy, r + 15, -self._arc2_angle, col["arc2"],
                              dash_len=12, gap=4, width=1)

        # ── Outer glow ring ───────────────────────────────────────────────────
        glow_r = r + 8
        for i, alpha in enumerate([0.12, 0.20, 0.35]):
            gr = glow_r + (3 - i) * 4
            glow_col = self._blend_color(col["orb"], cfg.BG, alpha)
            c.create_oval(cx - gr, cy - gr, cx + gr, cy + gr,
                          outline=glow_col, width=2)

        # ── Solid inner circle ────────────────────────────────────────────────
        c.create_oval(cx - r, cy - r, cx + r, cy + r,
                      fill=col["orb_inner"], outline=col["orb"], width=2)

        # ── Scanning line ─────────────────────────────────────────────────────
        scan_y_abs = (cy - r) + int(self._scan_y * (2 * r))
        scan_col = self._blend_color(col["arc1"], cfg.BG, 0.6)
        c.create_line(cx - r, scan_y_abs, cx + r, scan_y_abs,
                      fill=scan_col, width=1)

        # ── HUD corner brackets ───────────────────────────────────────────────
        bx, by, bsize, blen = cx, cy, r + 38, 20
        bracket_col = col["arc2"]
        # Top-left
        c.create_line(bx - bsize, by - bsize, bx - bsize + blen, by - bsize,
                      fill=bracket_col, width=2)
        c.create_line(bx - bsize, by - bsize, bx - bsize, by - bsize + blen,
                      fill=bracket_col, width=2)
        # Top-right
        c.create_line(bx + bsize, by - bsize, bx + bsize - blen, by - bsize,
                      fill=bracket_col, width=2)
        c.create_line(bx + bsize, by - bsize, bx + bsize, by - bsize + blen,
                      fill=bracket_col, width=2)
        # Bottom-left
        c.create_line(bx - bsize, by + bsize, bx - bsize + blen, by + bsize,
                      fill=bracket_col, width=2)
        c.create_line(bx - bsize, by + bsize, bx - bsize, by + bsize - blen,
                      fill=bracket_col, width=2)
        # Bottom-right
        c.create_line(bx + bsize, by + bsize, bx + bsize - blen, by + bsize,
                      fill=bracket_col, width=2)
        c.create_line(bx + bsize, by + bsize, bx + bsize, by + bsize - blen,
                      fill=bracket_col, width=2)

        # ── Diagonal accent lines ─────────────────────────────────────────────
        diag_col = self._blend_color(col["arc2"], cfg.BG, 0.5)
        c.create_line(cx - r - 5, cy, cx - r - 25, cy, fill=diag_col, width=1)
        c.create_line(cx + r + 5, cy, cx + r + 25, cy, fill=diag_col, width=1)
        c.create_line(cx, cy - r - 5, cx, cy - r - 25, fill=diag_col, width=1)
        c.create_line(cx, cy + r + 5, cx, cy + r + 25, fill=diag_col, width=1)

        # ── Inner concentric rings ────────────────────────────────────────────
        for ir in [r * 0.65, r * 0.4, r * 0.2]:
            ir = int(ir)
            c.create_oval(cx - ir, cy - ir, cx + ir, cy + ir,
                          outline=self._blend_color(col["orb"], cfg.BG, 0.3),
                          width=1)

        # ── JARVIS text ───────────────────────────────────────────────────────
        c.create_text(cx, cy - 12,
                      text="J.A.R.V.I.S",
                      fill=col["orb"],
                      font=("Courier New", 14, "bold"))
        c.create_text(cx, cy + 10,
                      text="ONLINE",
                      fill=self._blend_color(col["orb"], cfg.BG, 0.6),
                      font=("Courier New", 9))

        # ── Angle readout decorations ─────────────────────────────────────────
        ang_text = f"{int(self._arc1_angle % 360):03d}°"
        c.create_text(cx - r + 18, cy + r - 14,
                      text=ang_text,
                      fill=self._blend_color(col["arc1"], cfg.BG, 0.5),
                      font=("Courier New", 8))

    def _draw_dashed_arc(
        self,
        c: Canvas,
        cx: int,
        cy: int,
        radius: int,
        start_angle: float,
        color: str,
        dash_len: int = 10,
        gap: int = 5,
        width: int = 2,
    ) -> None:
        """Draw a circle made of short arc segments, rotated by start_angle degrees."""
        circumference = 2 * math.pi * radius
        total = dash_len + gap
        n_dashes = max(1, int(circumference / total))
        dash_deg = 360 / n_dashes * (dash_len / total)
        step_deg = 360 / n_dashes

        for i in range(n_dashes):
            a0 = start_angle + i * step_deg
            a1 = a0 + dash_deg
            x0 = cx - radius
            y0 = cy - radius
            x1 = cx + radius
            y1 = cy + radius
            c.create_arc(
                x0, y0, x1, y1,
                start=a0, extent=dash_deg,
                outline=color, width=width, style="arc",
            )

    def _draw_waveform(self) -> None:
        """Animate the waveform bar display below the orb."""
        c = self.wave_canvas
        c.delete("all")
        width = self.LEFT_W
        mid_y = 25
        n_bars = 24
        bar_w = 6
        spacing = width // n_bars
        col = STATE_COLORS[self._state]["arc1"]

        for i in range(n_bars):
            x = i * spacing + spacing // 2
            if self._state == "listening":
                amp = 18 * abs(
                    math.sin(self._wave_phase + i * 0.45)
                ) + 2
            elif self._state == "speaking":
                amp = 14 * abs(
                    math.sin(self._wave_phase * 1.3 + i * 0.6)
                ) + 3
            elif self._state == "processing":
                amp = 8 * abs(math.sin(self._wave_phase * 0.5 + i * 0.3)) + 2
            else:
                amp = 3  # idle — flat

            c.create_rectangle(
                x - bar_w // 2, mid_y - int(amp),
                x + bar_w // 2, mid_y + int(amp),
                fill=col, outline="",
            )

    # ─────────────────────────────────────────────────────────────────────────
    # Right panel
    # ─────────────────────────────────────────────────────────────────────────

    def _build_right_panel(self) -> None:
        self.right = ctk.CTkFrame(
            self.root, fg_color="#070d1a", corner_radius=0
        )
        self.right.grid(row=0, column=1, sticky="nsew", padx=(1, 0), pady=(45, 0))
        self.right.grid_columnconfigure(0, weight=1)
        self.right.grid_rowconfigure(3, weight=1)  # log gets the extra space
        self.right.grid_rowconfigure(4, minsize=52) # text input row

        # ── Section: Active Listening indicator ───────────────────────────────
        top_bar = ctk.CTkFrame(self.right, fg_color="#050a14", corner_radius=6)
        top_bar.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 4))
        top_bar.grid_columnconfigure(1, weight=1)

        self.listen_indicator = ctk.CTkLabel(
            top_bar,
            text="◉  ESCUCHA ACTIVA",
            font=ctk.CTkFont(family="Courier New", size=12, weight="bold"),
            text_color=cfg.DIM,
        )
        self.listen_indicator.grid(row=0, column=0, padx=12, pady=6)

        self.listen_state_badge = ctk.CTkLabel(
            top_bar,
            text="[ INACTIVO ]",
            font=ctk.CTkFont(family="Courier New", size=11),
            text_color=cfg.DIM,
        )
        self.listen_state_badge.grid(row=0, column=1, padx=12, pady=6, sticky="e")

        # ── Section: Recognised speech ────────────────────────────────────────
        rec_frame = ctk.CTkFrame(self.right, fg_color="#050a14", corner_radius=6)
        rec_frame.grid(row=1, column=0, sticky="ew", padx=12, pady=4)
        rec_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            rec_frame,
            text="ENTRADA DE VOZ",
            font=ctk.CTkFont(family="Courier New", size=9),
            text_color=cfg.DIM,
            anchor="w",
        ).grid(row=0, column=0, padx=12, pady=(6, 0), sticky="w")

        self.recognized_label = ctk.CTkLabel(
            rec_frame,
            text="—",
            font=ctk.CTkFont(family="Courier New", size=13),
            text_color=cfg.TEXT,
            anchor="w",
            wraplength=440,
        )
        self.recognized_label.grid(row=1, column=0, padx=14, pady=(2, 6), sticky="w")

        # ── Section: Last command ─────────────────────────────────────────────
        cmd_frame = ctk.CTkFrame(self.right, fg_color="#050a14", corner_radius=6)
        cmd_frame.grid(row=2, column=0, sticky="ew", padx=12, pady=4)
        cmd_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            cmd_frame,
            text="ÚLTIMO COMANDO EJECUTADO",
            font=ctk.CTkFont(family="Courier New", size=9),
            text_color=cfg.DIM,
            anchor="w",
        ).grid(row=0, column=0, padx=12, pady=(6, 0), sticky="w")

        self.last_cmd_label = ctk.CTkLabel(
            cmd_frame,
            text="—",
            font=ctk.CTkFont(family="Courier New", size=12),
            text_color=cfg.ACCENT,
            anchor="w",
            wraplength=440,
        )
        self.last_cmd_label.grid(row=1, column=0, padx=14, pady=(2, 6), sticky="w")

        # ── Section: Activity log ─────────────────────────────────────────────
        log_frame = ctk.CTkFrame(self.right, fg_color="#050a14", corner_radius=6)
        log_frame.grid(row=3, column=0, sticky="nsew", padx=12, pady=4)
        log_frame.grid_rowconfigure(1, weight=1)
        log_frame.grid_columnconfigure(0, weight=1)

        log_header = ctk.CTkFrame(log_frame, fg_color="#070d1a", corner_radius=0)
        log_header.grid(row=0, column=0, sticky="ew", padx=0, pady=(0, 2))
        ctk.CTkLabel(
            log_header,
            text="◈  REGISTRO DE ACTIVIDAD",
            font=ctk.CTkFont(family="Courier New", size=9, weight="bold"),
            text_color=cfg.ACCENT2,
            anchor="w",
        ).pack(side="left", padx=10, pady=4)
        ctk.CTkButton(
            log_header,
            text="LIMPIAR",
            width=62,
            height=22,
            font=ctk.CTkFont(family="Courier New", size=8, weight="bold"),
            fg_color="#0a1828",
            hover_color="#1a2838",
            text_color=cfg.DIM,
            border_width=1,
            border_color=cfg.DIM,
            corner_radius=3,
            command=self._clear_log,
        ).pack(side="right", padx=10, pady=4)

        self.log_text = ctk.CTkTextbox(
            log_frame,
            fg_color=cfg.BG,
            text_color=cfg.TEXT,
            font=ctk.CTkFont(family="Courier New", size=11),
            corner_radius=0,
            wrap="word",
            state="disabled",
        )
        self.log_text.grid(row=1, column=0, sticky="nsew", padx=2, pady=(0, 2))

        # Tag colours (we apply them manually via tag_config on the underlying Text)
        inner_text = self.log_text._textbox  # underlying tk.Text widget
        inner_text.tag_configure("info",    foreground=cfg.TEXT)
        inner_text.tag_configure("success", foreground=cfg.SUCCESS)
        inner_text.tag_configure("warning", foreground=cfg.WARNING)
        inner_text.tag_configure("error",   foreground=cfg.ERROR)
        inner_text.tag_configure("dim",     foreground=cfg.DIM)

        # ── Section: Text command input ───────────────────────────────────────
        input_frame = ctk.CTkFrame(self.right, fg_color="#050a14", corner_radius=6)
        input_frame.grid(row=4, column=0, sticky="ew", padx=12, pady=(4, 2))
        input_frame.grid_columnconfigure(0, weight=1)

        self.cmd_entry = ctk.CTkEntry(
            input_frame,
            placeholder_text='Escribe un comando y pulsa Enter  (ej: "abre chrome")',
            font=ctk.CTkFont(family="Courier New", size=11),
            fg_color="#030810",
            border_color=cfg.DIM,
            text_color=cfg.TEXT,
            placeholder_text_color=cfg.DIM,
            height=32,
        )
        self.cmd_entry.grid(row=0, column=0, padx=(10, 4), pady=8, sticky="ew")
        self.cmd_entry.bind("<Return>", self._on_text_command)

        ctk.CTkButton(
            input_frame,
            text="▶",
            width=36,
            height=32,
            font=ctk.CTkFont(size=14),
            fg_color=cfg.ACCENT2,
            hover_color=cfg.ACCENT,
            text_color="#ffffff",
            corner_radius=4,
            command=lambda: self._on_text_command(None),
        ).grid(row=0, column=1, padx=(0, 10), pady=8)

        # ── Section: System stats bar ─────────────────────────────────────────
        stats_frame = ctk.CTkFrame(
            self.right, fg_color="#030810", height=34, corner_radius=0
        )
        stats_frame.grid(row=5, column=0, sticky="ew", padx=0, pady=(2, 0))
        stats_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)
        stats_frame.grid_propagate(False)

        self.cpu_label = ctk.CTkLabel(
            stats_frame,
            text="CPU: --%",
            font=ctk.CTkFont(family="Courier New", size=10),
            text_color=cfg.DIM,
        )
        self.cpu_label.grid(row=0, column=0, padx=10, pady=4)

        self.ram_label = ctk.CTkLabel(
            stats_frame,
            text="RAM: --%",
            font=ctk.CTkFont(family="Courier New", size=10),
            text_color=cfg.DIM,
        )
        self.ram_label.grid(row=0, column=1, padx=10, pady=4)

        self.disk_label = ctk.CTkLabel(
            stats_frame,
            text="DISK: --%",
            font=ctk.CTkFont(family="Courier New", size=10),
            text_color=cfg.DIM,
        )
        self.disk_label.grid(row=0, column=2, padx=10, pady=4)

        self.uptime_label = ctk.CTkLabel(
            stats_frame,
            text="UP: --:--",
            font=ctk.CTkFont(family="Courier New", size=10),
            text_color=cfg.DIM,
        )
        self.uptime_label.grid(row=0, column=3, padx=10, pady=4)

        # Seed the log with a startup message
        self.add_log(f"{cfg.APP_NAME} v{cfg.VERSION} iniciado — sistemas en línea.", "success")
        self.add_log('Mantén pulsado "0" y habla en español.', "dim")

    # ─────────────────────────────────────────────────────────────────────────
    # Commands panel
    # ─────────────────────────────────────────────────────────────────────────

    # All active commands grouped by category.
    # Format: (category_title, accent_color, [(icon, description, example), ...])
    _COMMANDS = [
        ("SISTEMA", "#ff3355", [
            ("⏻", "Apagar el ordenador",   "apaga el ordenador / apaga el pc"),
            ("↺", "Reiniciar el equipo",    "reinicia el ordenador / reinicia el pc"),
            ("◌", "Suspender / sleep",      "pon el ordenador a dormir / suspender"),
        ]),
        ("PROGRAMAS", "#00d4ff", [
            ("▶", "Abrir cualquier programa", "abre chrome / ejecuta discord / lanza spotify"),
            ("✕", "Cerrar un programa",       "cierra chrome / termina discord / para spotify"),
        ]),
        ("WHATSAPP", "#25d366", [
            ("⊕", "Abrir WhatsApp en Chrome",  "abre whatsapp en chrome / abre whatsapp web"),
            ("✉", "Enviar mensaje",
             "manda un mensaje a Nil que diga Hola\n"
             "     envía a Ana diciendo Buenas\n"
             "     dile a Juan por whatsapp que llega tarde"),
        ]),
        ("YOUTUBE", "#ff0000", [
            ("♫", "Reproducir música/vídeo",
             "pon música phonk en youtube\n"
             "     reproduce lofi en youtube\n"
             "     quiero escuchar reggaeton"),
        ]),
        ("NAVEGADOR WEB", "#4285f4", [
            ("⊞", "Abrir una web",
             "abre youtube / ve a google / entra en twitch\n"
             "     abre netflix.com"),
        ]),
        ("VOLUMEN", "#ffaa00", [
            ("▲", "Subir volumen",   "sube el volumen / más volumen"),
            ("▼", "Bajar volumen",   "baja el volumen / menos sonido"),
            ("✕", "Silenciar",       "silencia / quita el sonido / mute"),
        ]),
        ("PANTALLA", "#00ff88", [
            ("⬛", "Captura de pantalla",
             "haz una captura / pantallazo / screenshot"),
        ]),
        ("ARCHIVOS", "#c8e8ff", [
            ("⇄", "Mover archivo",
             "mueve el archivo datos.txt a C:\\Backup"),
        ]),
        ("INFORMACIÓN", "#888888", [
            ("◷", "Hora actual",      "qué hora es / dime la hora"),
            ("▦", "Fecha de hoy",     "qué día es hoy / dime la fecha"),
            ("⊙", "Estado del sistema", "cómo está el sistema / uso de cpu"),
            ("?", "Ayuda",            "ayuda / qué puedes hacer / comandos"),
        ]),
    ]

    def _build_commands_panel(self) -> None:
        # Vertical separator
        sep = ctk.CTkFrame(self.root, fg_color=cfg.DIM, width=1, corner_radius=0)
        sep.grid(row=0, column=1, sticky="nse", pady=(45, 0))

        outer = ctk.CTkFrame(
            self.root, fg_color="#060c18", width=self.CMD_W, corner_radius=0
        )
        outer.grid(row=0, column=2, sticky="nsew", padx=0, pady=(45, 0))
        outer.grid_propagate(False)
        outer.grid_rowconfigure(1, weight=1)
        outer.grid_columnconfigure(0, weight=1)

        # Header
        hdr = ctk.CTkFrame(outer, fg_color="#040810", corner_radius=0, height=32)
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.grid_propagate(False)
        ctk.CTkLabel(
            hdr,
            text="◈  COMANDOS DISPONIBLES",
            font=ctk.CTkFont(family="Courier New", size=10, weight="bold"),
            text_color=cfg.ACCENT,
            anchor="w",
        ).pack(side="left", padx=12, pady=6)
        ctk.CTkLabel(
            hdr,
            text="ACTIVO",
            font=ctk.CTkFont(family="Courier New", size=9),
            text_color=cfg.SUCCESS,
            anchor="e",
        ).pack(side="right", padx=12, pady=6)

        # Scrollable content
        scroll = ctk.CTkScrollableFrame(
            outer,
            fg_color="#060c18",
            scrollbar_button_color=cfg.DIM,
            scrollbar_button_hover_color=cfg.ACCENT2,
            corner_radius=0,
        )
        scroll.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
        scroll.grid_columnconfigure(0, weight=1)

        for cat_title, cat_color, commands in self._COMMANDS:
            # Category header
            cat_frame = ctk.CTkFrame(scroll, fg_color="#040810", corner_radius=4)
            cat_frame.pack(fill="x", padx=8, pady=(8, 2))

            ctk.CTkLabel(
                cat_frame,
                text=f"▸  {cat_title}",
                font=ctk.CTkFont(family="Courier New", size=10, weight="bold"),
                text_color=cat_color,
                anchor="w",
            ).pack(side="left", padx=10, pady=4)

            # Status dot
            ctk.CTkLabel(
                cat_frame,
                text="●",
                font=ctk.CTkFont(size=8),
                text_color=cfg.SUCCESS,
                anchor="e",
            ).pack(side="right", padx=10, pady=4)

            # Command rows
            for icon, desc, example in commands:
                row = ctk.CTkFrame(scroll, fg_color="#080f1e", corner_radius=4)
                row.pack(fill="x", padx=8, pady=1)
                row.grid_columnconfigure(1, weight=1)

                # Icon
                ctk.CTkLabel(
                    row,
                    text=icon,
                    font=ctk.CTkFont(family="Courier New", size=13),
                    text_color=cat_color,
                    width=28,
                    anchor="center",
                ).grid(row=0, column=0, rowspan=2, padx=(8, 4), pady=6, sticky="ns")

                # Description
                ctk.CTkLabel(
                    row,
                    text=desc,
                    font=ctk.CTkFont(family="Courier New", size=10, weight="bold"),
                    text_color=cfg.TEXT,
                    anchor="w",
                ).grid(row=0, column=1, padx=4, pady=(5, 0), sticky="w")

                # Example (dimmer, italic-style via smaller font)
                ctk.CTkLabel(
                    row,
                    text=example,
                    font=ctk.CTkFont(family="Courier New", size=9),
                    text_color="#3a6080",
                    anchor="w",
                    wraplength=self.CMD_W - 70,
                    justify="left",
                ).grid(row=1, column=1, padx=4, pady=(0, 5), sticky="w")

        # Bottom hint
        ctk.CTkLabel(
            outer,
            text='[ Mantén "0" · habla · suelta ]',
            font=ctk.CTkFont(family="Courier New", size=9),
            text_color=cfg.DIM,
        ).grid(row=2, column=0, pady=6)

    # ─────────────────────────────────────────────────────────────────────────
    # Animation loop
    # ─────────────────────────────────────────────────────────────────────────

    def _start_animations(self) -> None:
        self._animate()

    def _animate(self) -> None:
        if not self._running:
            return

        # ── Update animation state ────────────────────────────────────────────
        speed = 2.0 if self._state == "listening" else 1.0
        self._arc1_angle = (self._arc1_angle + 1.5 * speed) % 360
        self._arc2_angle = (self._arc2_angle + 0.9 * speed) % 360

        # Scanning line (0 → 1, then loops)
        self._scan_y += 0.008 * speed
        if self._scan_y > 1.0:
            self._scan_y = 0.0

        # Breathing / pulse
        self._pulse += 0.04 * self._pulse_dir
        if self._pulse >= 1.0:
            self._pulse_dir = -1.0
        elif self._pulse <= 0.0:
            self._pulse_dir = 1.0

        # Wave phase
        self._wave_phase += 0.12 * speed

        # Blink (every ~15 frames when listening)
        self._blink_counter += 1
        if self._blink_counter >= 15:
            self._blink_counter = 0
            self._blink_visible = not self._blink_visible

        # ── Redraw ────────────────────────────────────────────────────────────
        self._draw_orb()
        self._draw_waveform()
        self._update_blink()

        # Schedule next frame
        self.root.after(self.ANIM_INTERVAL_MS, self._animate)

    def _update_blink(self) -> None:
        if self._state == "listening":
            color = cfg.ERROR if self._blink_visible else cfg.BG
            self.blink_label.configure(text="● REC", text_color=color)
        else:
            self.blink_label.configure(text_color=cfg.BG)

    # ─────────────────────────────────────────────────────────────────────────
    # System stats updater
    # ─────────────────────────────────────────────────────────────────────────

    def _start_stat_updater(self) -> None:
        self._update_stats()

    def _update_stats(self) -> None:
        if not self._running:
            return
        try:
            cpu = psutil.cpu_percent(interval=None)
            ram = psutil.virtual_memory().percent
            try:
                disk = psutil.disk_usage("/").percent
            except Exception:
                try:
                    disk = psutil.disk_usage("C:\\").percent
                except Exception:
                    disk = 0.0

            boot_time = psutil.boot_time()
            uptime_sec = int(time.time() - boot_time)
            hours, rem = divmod(uptime_sec, 3600)
            minutes = rem // 60

            cpu_col  = cfg.ERROR   if cpu  > 85 else (cfg.WARNING if cpu  > 60 else cfg.DIM)
            ram_col  = cfg.ERROR   if ram  > 85 else (cfg.WARNING if ram  > 70 else cfg.DIM)
            disk_col = cfg.WARNING if disk > 80 else cfg.DIM

            self.cpu_label.configure(
                text=f"CPU: {cpu:.0f}%", text_color=cpu_col
            )
            self.ram_label.configure(
                text=f"RAM: {ram:.0f}%", text_color=ram_col
            )
            self.disk_label.configure(
                text=f"DISK: {disk:.0f}%", text_color=disk_col
            )
            self.uptime_label.configure(
                text=f"UP: {hours:02d}:{minutes:02d}", text_color=cfg.DIM
            )
            # Also update the left panel mini stat
            self.left_stat_label.configure(
                text=f"CPU: {cpu:.0f}%   RAM: {ram:.0f}%",
                text_color=cpu_col,
            )
        except Exception:
            pass

        self.root.after(self.STAT_INTERVAL_MS, self._update_stats)

    # ─────────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────────

    def set_state(self, state: StateType) -> None:
        """Switch the visual state of the HUD (idle / listening / processing / speaking)."""
        if state not in STATE_COLORS:
            return
        self._state = state
        col = STATE_COLORS[state]

        # Update labels (thread-safe via after)
        def _update():
            self.status_label.configure(
                text=col["status_txt"],
                text_color=col["label"],
            )
            self.listen_state_badge.configure(
                text=f"[ {col['status_txt']} ]",
                text_color=col["label"],
            )
            indicator_col = cfg.ACCENT if state == "listening" else cfg.DIM
            self.listen_indicator.configure(text_color=indicator_col)

        self.root.after(0, _update)

    def add_log(self, text: str, level: str = "info") -> None:
        """
        Append *text* to the activity log.
        *level* one of: 'info', 'success', 'warning', 'error', 'dim'
        """
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}]  {text}\n"

        def _insert():
            self.log_text.configure(state="normal")
            inner = self.log_text._textbox
            inner.insert("end", line, level)
            self.log_text.configure(state="disabled")
            self.log_text.see("end")

        self.root.after(0, _insert)

    def set_recognized_text(self, text: str) -> None:
        """Display the last recognised speech in the right panel."""
        def _update():
            self.recognized_label.configure(
                text=text if text else "—",
                text_color=cfg.ACCENT if text else cfg.DIM,
            )
        self.root.after(0, _update)

    def set_last_command(self, text: str) -> None:
        """Display the last command that was dispatched to Actions."""
        def _update():
            self.last_cmd_label.configure(
                text=text if text else "—",
                text_color=cfg.ACCENT if text else cfg.DIM,
            )
        self.root.after(0, _update)

    def set_command_callback(self, callback) -> None:
        """Register the function to call when the user submits a text command."""
        self._on_command_callback = callback

    def _on_text_command(self, event) -> None:
        """Called when user presses Enter or clicks ▶ in the text input."""
        text = self.cmd_entry.get().strip()
        if not text:
            return
        self.cmd_entry.delete(0, "end")
        self.add_log(f'Comando escrito: "{text}"', "info")
        if self._on_command_callback:
            import threading
            threading.Thread(
                target=self._on_command_callback, args=(text,), daemon=True
            ).start()

    def _clear_log(self) -> None:
        """Clear all entries from the activity log."""
        def _do_clear():
            self.log_text.configure(state="normal")
            self.log_text._textbox.delete("1.0", "end")
            self.log_text.configure(state="disabled")
        self.root.after(0, _do_clear)

    # ─────────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _blend_color(hex_color: str, base_hex: str, alpha: float) -> str:
        """
        Linearly blend *hex_color* toward *base_hex* by *alpha* (0=original, 1=base).
        Returns a '#RRGGBB' string.
        """
        def _parse(h: str):
            h = h.lstrip("#")
            return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

        r1, g1, b1 = _parse(hex_color)
        r2, g2, b2 = _parse(base_hex)
        r = int(r1 + (r2 - r1) * alpha)
        g = int(g1 + (g2 - g1) * alpha)
        b = int(b1 + (b2 - b1) * alpha)
        return f"#{r:02x}{g:02x}{b:02x}"

    # ─────────────────────────────────────────────────────────────────────────
    # Lifecycle
    # ─────────────────────────────────────────────────────────────────────────

    def _on_close(self) -> None:
        self._running = False
        self.root.destroy()

    def run(self) -> None:
        """Start the Tk main loop (blocking until window is closed)."""
        self.root.mainloop()
