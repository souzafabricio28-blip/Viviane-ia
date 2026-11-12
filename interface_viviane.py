from __future__ import annotations

import logging
import math
import os
import re
import sys
import threading
import tkinter as tk
import traceback
from datetime import datetime

_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import customtkinter as ctk
import psutil

from core.assistant import Assistente
from core.settings import settings

log = logging.getLogger("VivianeApp")

ERROR_LOG = os.path.join(_PROJECT_ROOT, "logs", "error_log.txt")
os.makedirs(os.path.dirname(ERROR_LOG), exist_ok=True)

with open(ERROR_LOG, "a", encoding="utf-8") as f:
    f.write(f"[{datetime.now().isoformat()}] Interface Viviane inicializada\n")


def _log_error(erro: str, contexto: str = "") -> None:
    tb = traceback.format_exc() if contexto else ""
    with open(ERROR_LOG, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().isoformat()}] {contexto}: {erro}\n{tb}\n")


# ── Visual JARVIS ──────────────────────────────────────────────────────

COLORS = {
    "bg": "#02070D",
    "panel": "#04101A",
    "panel_alt": "#071A28",
    "card": "#0A2434",
    "accent": "#00E5FF",
    "accent_2": "#1E90FF",
    "accent_3": "#8CF3FF",
    "user": "#FFB02E",
    "text": "#CDEFF7",
    "muted": "#4F8A99",
    "success": "#2EE6A4",
    "warn": "#FFB02E",
    "danger": "#FF4D5E",
    "border": "#0E4A5E",
    "glow": "#00E5FF",
}

FONTE_TITULO = "Bahnschrift"
FONTE_MONO = "Consolas"

_PALETA_GLOBO = (
    (0, 232, 255),
    (70, 140, 255),
    (168, 85, 255),
    (255, 47, 196),
    (255, 176, 48),
    (46, 230, 164),
)


def _fonte(tamanho: int, negrito: bool = False, familia: str = FONTE_TITULO) -> ctk.CTkFont:
    return ctk.CTkFont(family=familia, size=tamanho, weight="bold" if negrito else "normal")


class NucleoVisual:
    """Relógio, giro e brilho compartilhados pelo HUD."""

    def __init__(self) -> None:
        self.t = 0.0
        self.angulo = 0.0
        self.pulso = 0.12

    def brilhar(self) -> None:
        self.pulso = 1.0

    def avancar(self) -> None:
        try:
            from core.amplitude import get_amplitude
            amp = get_amplitude()
        except Exception:
            amp = 0.0
        self.pulso = max(amp, self.pulso * 0.96, 0.10)
        self.t += 0.04
        self.angulo = (self.angulo + 0.045 + self.pulso * 0.07) % math.tau


class HudCore(tk.Canvas):
    """Reator central: anéis giratórios, régua de ticks, voz em barras e globo 3D colorido."""

    def __init__(self, parent, nucleo: NucleoVisual, size: int, bg: str):
        super().__init__(parent, width=size, height=size, bg=bg, highlightthickness=0, bd=0)
        self.nucleo = nucleo
        self.size = size
        self._lats = list(range(-75, 90, 15))
        self._lons = list(range(0, 360, 20))

    @staticmethod
    def _rgb(rgb, f: float) -> str:
        r, g, b = (max(0, min(255, int(v * f))) for v in rgb)
        return f"#{r:02x}{g:02x}{b:02x}"

    def desenhar(self) -> None:
        self.delete("all")
        s = self.size
        cx = cy = s / 2
        n = self.nucleo
        p = n.pulso
        t = n.t
        ciano = (0, 229, 255)

        def cor(f: float) -> str:
            return self._rgb(ciano, f)

        # Cantos de mira
        m, comp = 6, 22
        for sx, sy in ((m, m), (s - m, m), (m, s - m), (s - m, s - m)):
            dx = 1 if sx < cx else -1
            dy = 1 if sy < cy else -1
            self.create_line(sx, sy, sx + dx * comp, sy, fill=cor(0.55 + 0.4 * p), width=2)
            self.create_line(sx, sy, sx, sy + dy * comp, fill=cor(0.55 + 0.4 * p), width=2)

        # Anel externo e marcadores cardinais
        r = s * 0.475
        self.create_oval(cx - r, cy - r, cx + r, cy + r, outline=cor(0.22 + 0.35 * p))
        for k in range(4):
            a = k * math.pi / 2
            self.create_line(
                cx + math.cos(a) * r, cy + math.sin(a) * r,
                cx + math.cos(a) * (r - s * 0.035), cy + math.sin(a) * (r - s * 0.035),
                fill=cor(0.95), width=2,
            )

        # Arcos giratórios em sentidos opostos
        r2 = s * 0.44
        for k in range(3):
            self.create_arc(
                cx - r2, cy - r2, cx + r2, cy + r2,
                start=-math.degrees(t) * 1.2 + k * 120, extent=64,
                style=tk.ARC, outline=cor(0.65 + 0.35 * p), width=3,
            )
        r2b = s * 0.415
        for k in range(2):
            self.create_arc(
                cx - r2b, cy - r2b, cx + r2b, cy + r2b,
                start=math.degrees(t) * 0.9 + k * 180, extent=44,
                style=tk.ARC, outline=cor(0.4 + 0.3 * p), width=2,
            )

        # Régua de ticks
        r3 = s * 0.385
        giro = math.degrees(t) * 0.6
        for i in range(72):
            a = math.radians(i * 5 - giro)
            longo = i % 6 == 0
            tam = s * (0.028 if longo else 0.014)
            self.create_line(
                cx + math.cos(a) * r3, cy + math.sin(a) * r3,
                cx + math.cos(a) * (r3 - tam), cy + math.sin(a) * (r3 - tam),
                fill=cor(0.85 if longo else 0.3 + 0.45 * p),
            )

        # Anel pontilhado interno
        r4 = s * 0.33
        self.create_oval(cx - r4, cy - r4, cx + r4, cy + r4, outline=cor(0.3 + 0.3 * p), dash=(2, 5))

        # Barras de voz
        if p > 0.14:
            r5 = s * 0.305
            for i in range(72):
                a = math.radians(i * 5)
                v = 0.25 + 0.75 * abs(math.sin(i * 0.85 + t * 9))
                tam = s * 0.045 * min(1.0, p) * v
                base = _PALETA_GLOBO[i % len(_PALETA_GLOBO)]
                self.create_line(
                    cx + math.cos(a) * r5, cy + math.sin(a) * r5,
                    cx + math.cos(a) * (r5 + tam), cy + math.sin(a) * (r5 + tam),
                    fill=self._rgb(base, 0.6 + 0.4 * min(1.0, p)), width=2,
                )

        self._globo(cx, cy, s * 0.26, p, n.angulo)

    def _globo(self, cx: float, cy: float, raio: float, pulso: float, ang: float) -> None:
        inclinacao = 0.42

        def projetar(lat: float, lon: float):
            la = math.radians(lat)
            lo = math.radians(lon) + ang
            x = math.cos(la) * math.sin(lo)
            y = math.sin(la)
            z = math.cos(la) * math.cos(lo)
            y2 = y * math.cos(inclinacao) - z * math.sin(inclinacao)
            z2 = y * math.sin(inclinacao) + z * math.cos(inclinacao)
            escala = 1 + 0.12 * z2
            return cx + x * raio * escala, cy - y2 * raio * escala, z2

        def cor_globo(fase: float, z: float, forca: float) -> str:
            k = len(_PALETA_GLOBO)
            pos = (fase % 1.0) * (k - 1)
            i = int(pos) % k
            t = pos - int(pos)
            a, b = _PALETA_GLOBO[i], _PALETA_GLOBO[(i + 1) % k]
            luz = (0.28 + 0.72 * max(0.0, z)) * forca
            mix = tuple(a[c] + (b[c] - a[c]) * t for c in range(3))
            return self._rgb(mix, luz)

        brilho = 0.55 + pulso * 1.35

        if pulso > 0.3:
            for i, fator in enumerate((1.28, 1.42, 1.58)):
                base = _PALETA_GLOBO[int(ang * 2 + i) % len(_PALETA_GLOBO)]
                rr = raio * fator
                self.create_oval(
                    cx - rr, cy - rr, cx + rr, cy + rr,
                    outline=self._rgb(base, 0.25 + pulso * 0.75 - i * 0.12),
                    width=2 if i == 0 else 1,
                )

        segmentos = []
        for lon in self._lons:
            pts = [projetar(lat, lon) for lat in self._lats]
            for a, b in zip(pts, pts[1:]):
                segmentos.append((a, b, (lon % 360) / 360))
        for lat in self._lats:
            pts = [projetar(lat, lon) for lon in self._lons]
            pts.append(pts[0])
            for a, b in zip(pts, pts[1:]):
                segmentos.append((a, b, (lat + 90) / 180))
        segmentos.sort(key=lambda item: (item[0][2] + item[1][2]) * 0.5)

        for a, b, fase in segmentos:
            z = (a[2] + b[2]) * 0.5
            if z < -0.55:
                continue
            self.create_line(
                a[0], a[1], b[0], b[1],
                fill=cor_globo(fase, z, brilho),
                width=2 if pulso > 0.65 and z > 0 else 1,
            )

        for lat in (-30, 20, 55):
            for lon in range(0, 360, 40):
                x, y, z = projetar(lat, lon)
                if z < 0.05:
                    continue
                rr = 1.4 + pulso * 2.2
                self.create_oval(x - rr, y - rr, x + rr, y + rr, fill=cor_globo(lon / 360, z, 1.4), outline="")


# ── Componentes ────────────────────────────────────────────────────────

class MessageBubble(ctk.CTkFrame):
    """Linha de mensagem no estilo terminal HUD."""

    def __init__(self, parent, sender: str, text: str, timestamp: str,
                 is_user: bool, is_error: bool = False, on_copy=None, wrap: int = 560):
        super().__init__(parent, fg_color="transparent", height=1)
        if is_error:
            cor = COLORS["danger"]
        elif is_user:
            cor = COLORS["user"]
        else:
            cor = COLORS["accent"]

        self.grid_columnconfigure(1, weight=1)
        ctk.CTkFrame(self, width=2, height=1, fg_color=cor, corner_radius=0).grid(
            row=0, column=0, sticky="ns", padx=(2, 10), pady=2,
        )
        corpo = ctk.CTkFrame(self, fg_color="transparent", height=1)
        corpo.grid(row=0, column=1, sticky="ew")

        topo = ctk.CTkFrame(corpo, fg_color="transparent", height=1)
        topo.pack(fill="x")
        ctk.CTkLabel(
            topo, text=f"▸ {sender.upper()}", font=_fonte(12, True), text_color=cor,
        ).pack(side="left")
        ctk.CTkLabel(
            topo, text=timestamp, font=_fonte(10, False, FONTE_MONO), text_color=COLORS["muted"],
        ).pack(side="left", padx=(10, 0))
        if on_copy:
            ctk.CTkButton(
                topo, text="copiar", width=46, height=18, corner_radius=0,
                fg_color="transparent", hover_color=COLORS["card"],
                text_color=COLORS["muted"], font=_fonte(10, False, FONTE_MONO),
                command=lambda: on_copy(text),
            ).pack(side="right")

        ctk.CTkLabel(
            corpo, text=text, font=_fonte(14), text_color="#FFB4BC" if is_error else COLORS["text"],
            justify="left", wraplength=wrap, anchor="w",
        ).pack(fill="x", pady=(2, 8))


class TypingIndicator(ctk.CTkFrame):
    """Indicador 'processando' animado."""

    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent", height=1)
        ctk.CTkFrame(self, width=2, height=1, fg_color=COLORS["accent"], corner_radius=0).pack(
            side="left", fill="y", padx=(2, 10), pady=2,
        )
        self.label = ctk.CTkLabel(
            self, text="▸ VIVIANE  processando", font=_fonte(12, True), text_color=COLORS["accent"],
        )
        self.label.pack(side="left", pady=6)
        self.blocos = ctk.CTkLabel(
            self, text="▪▫▫", font=_fonte(12, True, FONTE_MONO), text_color=COLORS["accent"],
        )
        self.blocos.pack(side="left", padx=8)
        self._idx = 0
        self._after_id = None
        self._animate()

    def _animate(self) -> None:
        frames = ("▪▫▫", "▫▪▫", "▫▫▪", "▫▪▫")
        try:
            self.blocos.configure(text=frames[self._idx % len(frames)])
            self._idx += 1
            self._after_id = self.after(220, self._animate)
        except Exception:
            pass

    def destroy(self) -> None:
        if self._after_id:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
        super().destroy()


def _painel(parent, **kw) -> ctk.CTkFrame:
    return ctk.CTkFrame(
        parent, fg_color=COLORS["panel"], corner_radius=0,
        border_width=1, border_color=COLORS["border"], **kw,
    )


# ── Configurações ──────────────────────────────────────────────────────

_CHAVES_ENV = {
    "ai_provider": "AI_PROVIDER",
    "openai_base_url": "OPENAI_BASE_URL",
    "openai_api_key": "OPENAI_API_KEY",
    "openai_model": "OPENAI_MODEL",
    "speak_responses": "VIVIANE_SPEAK_RESPONSES",
    "tts_voice": "TTS_VOICE",
    "tts_engine": "TTS_ENGINE",
    "allow_system_actions": "ALLOW_SYSTEM_ACTIONS",
    "enable_local_web": "ENABLE_LOCAL_WEB",
    "wake_word": "WAKE_WORD",
    "wake_word_engine": "WAKE_WORD_ENGINE",
}


class SettingsDialog(ctk.CTkToplevel):
    def __init__(self, parent, current_settings):
        super().__init__(parent, fg_color=COLORS["bg"])
        self.title("Configurações")
        self.geometry("520x640")
        self.resizable(False, False)
        self.transient(parent)
        self.current = current_settings
        self.vars: dict = {}
        self._build_ui()
        self.after(100, self.grab_set)

    def _build_ui(self) -> None:
        scroll = ctk.CTkScrollableFrame(self, corner_radius=0, fg_color=COLORS["panel"])
        scroll.pack(fill="both", expand=True, padx=16, pady=(16, 8))

        self._section(scroll, "IA / PROVEDOR")
        self._combobox_row(scroll, "Provedor", "ai_provider",
                           ["openai", "groq", "gemini", "ollama", "fallback", "auto"],
                           getattr(settings, "ai_provider", "openai"))
        self._entry_row(scroll, "Base URL (OpenAI-compat)", "openai_base_url",
                        getattr(settings, "openai_base_url", ""))
        self._entry_row(scroll, "API Key", "openai_api_key",
                        getattr(settings, "openai_api_key", ""), show="*")
        self._entry_row(scroll, "Modelo", "openai_model", getattr(settings, "openai_model", ""))

        self._section(scroll, "VOZ")
        self._switch_row(scroll, "Falar respostas", "speak_responses",
                         getattr(settings, "speak_responses", True))
        self._entry_row(scroll, "Voz TTS", "tts_voice",
                        getattr(settings, "tts_voice", "pt-BR-ThalitaMultilingualNeural"))
        self._combobox_row(scroll, "Engine TTS", "tts_engine", ["edge", "sapi"],
                           getattr(settings, "tts_engine", "edge"))

        self._section(scroll, "PERMISSÕES")
        self._switch_row(scroll, "Ações de sistema", "allow_system_actions",
                         getattr(settings, "allow_system_actions", True))
        self._switch_row(scroll, "Painel web neste PC (127.0.0.1)", "enable_local_web",
                         getattr(settings, "enable_local_web", False))

        self._section(scroll, "WAKE WORD")
        self._entry_row(scroll, "Palavra-chave", "wake_word", getattr(settings, "wake_word", "oi viviane"))
        self._combobox_row(scroll, "Engine", "wake_word_engine", ["simple", "openwakeword", "vosk"],
                           getattr(settings, "wake_word_engine", "simple"))

        ctk.CTkLabel(
            self, text="Provedor, modelo e voz valem por completo depois de reiniciar a Viviane.",
            font=_fonte(11), text_color=COLORS["muted"],
        ).pack(padx=16, anchor="w")

        botoes = ctk.CTkFrame(self, fg_color="transparent")
        botoes.pack(fill="x", padx=16, pady=14)
        ctk.CTkButton(
            botoes, text="SALVAR", width=130, height=36, corner_radius=0,
            fg_color="#06303C", hover_color="#0A4A5E", border_width=1, border_color=COLORS["accent"],
            text_color=COLORS["accent"], font=_fonte(13, True), command=self._save,
        ).pack(side="right", padx=(8, 0))
        ctk.CTkButton(
            botoes, text="CANCELAR", width=130, height=36, corner_radius=0,
            fg_color="transparent", hover_color=COLORS["card"], border_width=1,
            border_color=COLORS["border"], text_color=COLORS["muted"],
            font=_fonte(13, True), command=self.destroy,
        ).pack(side="right")

    def _section(self, parent, title: str) -> None:
        ctk.CTkLabel(parent, text=f"▌{title}", font=_fonte(13, True),
                     text_color=COLORS["accent"]).pack(anchor="w", pady=(16, 6))

    def _rotulo(self, parent, label: str) -> ctk.CTkFrame:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=4)
        ctk.CTkLabel(row, text=label, font=_fonte(11), text_color=COLORS["muted"]).pack(anchor="w")
        return row

    def _combobox_row(self, parent, label, key, values, current) -> None:
        row = self._rotulo(parent, label)
        var = ctk.StringVar(value=str(current))
        self.vars[key] = var
        ctk.CTkComboBox(row, values=values, variable=var, height=34, corner_radius=0,
                        fg_color=COLORS["panel_alt"], border_color=COLORS["border"],
                        button_color=COLORS["border"], font=_fonte(12)).pack(fill="x", pady=(4, 0))

    def _entry_row(self, parent, label, key, current, show=None) -> None:
        row = self._rotulo(parent, label)
        var = ctk.StringVar(value=str(current))
        self.vars[key] = var
        ctk.CTkEntry(row, textvariable=var, height=34, corner_radius=0,
                     fg_color=COLORS["panel_alt"], border_color=COLORS["border"],
                     font=_fonte(13), show=show or "").pack(fill="x", pady=(4, 0))

    def _switch_row(self, parent, label, key, current) -> None:
        row = self._rotulo(parent, label)
        var = ctk.BooleanVar(value=bool(current))
        self.vars[key] = var
        ctk.CTkSwitch(row, text="Ativado", variable=var, font=_fonte(12),
                      progress_color=COLORS["accent"]).pack(anchor="w", pady=(4, 0))

    def _save(self) -> None:
        for key, var in self.vars.items():
            setattr(settings, key, var.get())
        self._save_env()
        self.destroy()

    def _save_env(self) -> None:
        env_path = os.path.join(_PROJECT_ROOT, ".env")
        linhas: list[str] = []
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                linhas = f.read().splitlines()

        novos = {}
        for chave, var in self.vars.items():
            nome = _CHAVES_ENV.get(chave)
            if not nome:
                continue
            valor = var.get()
            novos[nome] = ("true" if valor else "false") if isinstance(valor, bool) else str(valor)

        for i, linha in enumerate(linhas):
            if "=" in linha and not linha.lstrip().startswith("#"):
                nome = linha.split("=", 1)[0].strip().upper()
                if nome in novos:
                    linhas[i] = f"{nome}={novos.pop(nome)}"
        for nome, valor in novos.items():
            linhas.append(f"{nome}={valor}")

        with open(env_path, "w", encoding="utf-8") as f:
            f.write("\n".join(linhas) + "\n")


# ── Janela principal ───────────────────────────────────────────────────

class VivianeApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Viviane IA")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self._win_h = 700
        self._fit_to_screen()
        self._placeholder = "Escreva uma mensagem..."

        self.colors = COLORS
        self.configure(fg_color=self.colors["bg"])

        self.assistente = None
        self.thread_ia = None
        self.thread_mic = None
        self._busy = False
        self._settings_dialog = None
        self._listening = False
        self.nucleo = NucleoVisual()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.bind("<Control-Return>", lambda e: self.enviar_comando())
        self.bind("<Control-l>", lambda e: self._clear_chat())
        self.bind("<Control-s>", lambda e: self._open_settings())
        self.bind("<Escape>", lambda e: self._escape())

        self._build_ui()
        self._set_status("Inicializando assistente...", self.colors["warn"])
        self.after(200, self._init_assistente)
        self._start_wake_word()

    def _fit_to_screen(self) -> None:
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        area_h = sh
        try:
            import ctypes
            from ctypes import wintypes
            rect = wintypes.RECT()
            if ctypes.windll.user32.SystemParametersInfoW(48, 0, ctypes.byref(rect), 0):
                area_h = rect.bottom - rect.top
        except Exception:
            area_h = sh - 48
        # desconta a barra de título e uma folga para as bordas
        h = min(740, max(560, area_h - 70))
        w = min(1180, max(900, sw - 60))
        self._win_h = h
        x = max(0, (sw - w) // 2)
        y = max(0, (area_h - h - 40) // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.minsize(min(900, sw - 40), min(560, area_h - 70))

    # ── Wake word ──────────────────────────────────────────────────────

    def _start_wake_word(self) -> None:
        try:
            from core.skills.wake_word import wake_word_manager
            wake_word_manager.set_activation_callback(self._on_wake_word)
            wake_word_manager.start()
            self._set_status("Ouvindo... diga 'oi viviane'", self.colors["success"])
        except Exception as e:
            _log_error(str(e), "wake_word_start")

    def _on_wake_word(self, keyword: str) -> None:
        self.after(0, self.nucleo.brilhar)
        self.after(0, lambda: self._set_status("Escutando seu comando...", self.colors["success"]))
        self.after(0, lambda: self._add_message("Viviane", "O que posso fazer por você?", is_assistant=True))
        self.after(0, lambda: self.entry_box.focus_set())
        self.after(0, lambda: self._set_busy(False, "Aguardando comando...", self.colors["success"]))

    # ── Construção da UI ──────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.grid_columnconfigure(2, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.left = ctk.CTkFrame(self, width=410, corner_radius=0, fg_color=self.colors["panel"])
        self.left.grid(row=0, column=0, sticky="nsew")
        self.left.grid_propagate(False)
        ctk.CTkFrame(self, width=1, corner_radius=0, fg_color=self.colors["border"]).grid(
            row=0, column=1, sticky="ns",
        )
        self._build_left()

        self.main = ctk.CTkFrame(self, corner_radius=0, fg_color=self.colors["bg"])
        self.main.grid(row=0, column=2, sticky="nsew")
        self.main.grid_rowconfigure(1, weight=1)
        self.main.grid_columnconfigure(0, weight=1)
        self._build_main()

        self._tick_clock()
        self._tick_telemetria()
        self._animar_hud()

    def _build_left(self) -> None:
        c = self.colors
        ctk.CTkLabel(
            self.left, text="V.I.V.I.A.N.E", font=_fonte(26, True), text_color=c["accent"],
        ).pack(pady=(14, 0))
        ctk.CTkLabel(
            self.left, text="ASSISTENTE PESSOAL  //  MODO LOCAL",
            font=_fonte(10, False, FONTE_MONO), text_color=c["muted"],
        ).pack()

        tamanho = max(190, min(340, self._win_h - 395))
        self.hud = HudCore(self.left, self.nucleo, size=tamanho, bg=c["panel"])
        self.hud.pack(pady=(6, 0))

        self.status_label = ctk.CTkLabel(
            self.left, text="● INICIANDO", font=_fonte(13, True), text_color=c["warn"],
            wraplength=360,
        )
        self.status_label.pack(pady=(2, 8))

        tele = _painel(self.left)
        tele.pack(fill="x", padx=18, pady=(0, 8))
        ctk.CTkLabel(tele, text="▌TELEMETRIA", font=_fonte(11, True), text_color=c["accent"]).pack(
            anchor="w", padx=12, pady=(8, 2),
        )
        self.barras: dict[str, tuple[ctk.CTkProgressBar, ctk.CTkLabel]] = {}
        for nome in ("CPU", "RAM", "DISCO"):
            linha = ctk.CTkFrame(tele, fg_color="transparent")
            linha.pack(fill="x", padx=12, pady=2)
            ctk.CTkLabel(linha, text=nome, width=46, anchor="w",
                         font=_fonte(10, True, FONTE_MONO), text_color=c["muted"]).pack(side="left")
            barra = ctk.CTkProgressBar(
                linha, height=6, corner_radius=0, fg_color="#0A2A38", progress_color=c["accent"],
            )
            barra.set(0)
            barra.pack(side="left", fill="x", expand=True, padx=6)
            valor = ctk.CTkLabel(linha, text="--%", width=38, anchor="e",
                                 font=_fonte(10, True, FONTE_MONO), text_color=c["text"])
            valor.pack(side="left")
            self.barras[nome] = (barra, valor)

        base = getattr(settings, "openai_base_url", "") or "neste computador"
        for rotulo, valor in (
            ("PROVEDOR", getattr(settings, "ai_provider", "-")),
            ("MODELO", getattr(settings, "openai_model", "") or "(automático)"),
            ("ENDPOINT", base.replace("http://", "").replace("https://", "")),
        ):
            linha = ctk.CTkFrame(tele, fg_color="transparent")
            linha.pack(fill="x", padx=12)
            ctk.CTkLabel(linha, text=rotulo, width=70, anchor="w",
                         font=_fonte(9, True, FONTE_MONO), text_color=c["muted"]).pack(side="left")
            ctk.CTkLabel(linha, text=self._short(valor, 30), anchor="w",
                         font=_fonte(10, False, FONTE_MONO), text_color=c["text"]).pack(side="left")
        ctk.CTkFrame(tele, height=6, fg_color="transparent").pack()

        rodape = ctk.CTkFrame(self.left, fg_color="transparent")
        rodape.pack(fill="x", padx=18, pady=(0, 10))
        self.voice_btn = ctk.CTkButton(
            rodape, text="◉  FALAR", height=40, corner_radius=0,
            fg_color="#06303C", hover_color="#0A4A5E", border_width=1, border_color=c["accent"],
            text_color=c["accent"], font=_fonte(14, True), command=self._voz_ou_parar,
        )
        self.voice_btn.pack(fill="x", pady=(0, 6))
        mini = ctk.CTkFrame(rodape, fg_color="transparent")
        mini.pack(fill="x")
        mini.grid_columnconfigure((0, 1, 2), weight=1)
        for col, (texto, comando) in enumerate((
            ("LIMPAR", self._clear_chat),
            ("CONFIG", self._open_settings),
            ("RECARREGAR", self._recarregar),
        )):
            ctk.CTkButton(
                mini, text=texto, height=30, corner_radius=0, fg_color="transparent",
                hover_color=c["card"], border_width=1, border_color=c["border"],
                text_color=c["muted"], font=_fonte(11, True), command=comando,
            ).grid(row=0, column=col, sticky="ew", padx=2)
        self.clear_chat_btn = mini

    def _build_main(self) -> None:
        c = self.colors

        header = ctk.CTkFrame(self.main, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(14, 6))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            header, text="CONVERSA  //  CANAL SEGURO", font=_fonte(18, True), text_color=c["text"],
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            header, text="texto e voz, somente neste computador",
            font=_fonte(10, False, FONTE_MONO), text_color=c["muted"],
        ).grid(row=1, column=0, sticky="w")
        self.clock_label = ctk.CTkLabel(
            header, text="", font=_fonte(14, True, FONTE_MONO), text_color=c["accent"],
        )
        self.clock_label.grid(row=0, column=1, rowspan=2, sticky="e")

        chat_wrap = _painel(self.main)
        chat_wrap.grid(row=1, column=0, sticky="nsew", padx=20, pady=(2, 8))
        chat_wrap.grid_rowconfigure(0, weight=1)
        chat_wrap.grid_columnconfigure(0, weight=1)
        self.chat_canvas = ctk.CTkScrollableFrame(
            chat_wrap, fg_color="transparent", corner_radius=0,
            scrollbar_button_color=c["border"], scrollbar_button_hover_color=c["accent"],
        )
        self.chat_canvas.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
        self.chat_canvas.grid_columnconfigure(0, weight=1)

        chips = ctk.CTkFrame(self.main, fg_color="transparent")
        chips.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 6))
        for texto, comando in (
            ("Que horas são?", "Que horas são?"),
            ("Status do PC", "Faça um diagnóstico do sistema"),
            ("Previsão", "Qual a previsão do tempo em São Paulo?"),
            ("Programas", "Quais programas estão abertos?"),
            ("Lembrete", "Lembrete em 30 minutos tomar água"),
            ("Pesquisar", "Pesquise sobre "),
        ):
            ctk.CTkButton(
                chips, text=texto, height=26, corner_radius=0, fg_color="transparent",
                hover_color=c["card"], border_width=1, border_color=c["border"],
                text_color=c["accent_3"], font=_fonte(11), width=80,
                command=lambda cmd=comando: self._quick_send(cmd),
            ).pack(side="left", padx=(0, 6))

        input_bar = _painel(self.main)
        input_bar.grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 6))
        input_bar.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(input_bar, text="▸", font=_fonte(20, True), text_color=c["accent"]).grid(
            row=0, column=0, padx=(12, 0),
        )
        self.entry_box = ctk.CTkTextbox(
            input_bar, height=52, corner_radius=0, fg_color=c["panel_alt"], border_width=0,
            text_color=c["muted"], font=_fonte(15), wrap="word",
        )
        self.entry_box.grid(row=0, column=1, sticky="ew", padx=8, pady=10)
        self.entry_box.insert("1.0", self._placeholder)
        self.entry_box.bind("<FocusIn>", self._on_entry_focus_in)
        self.entry_box.bind("<FocusOut>", self._on_entry_focus_out)
        self.entry_box.bind("<Return>", self._on_enter)
        self.entry_box.bind("<Shift-Return>", lambda e: None)

        botoes = ctk.CTkFrame(input_bar, fg_color="transparent")
        botoes.grid(row=0, column=2, padx=(0, 12), pady=10)
        self.clear_input_btn = ctk.CTkButton(
            botoes, text="✕", width=36, height=38, corner_radius=0, fg_color="transparent",
            hover_color=c["card"], text_color=c["muted"], font=_fonte(14, True),
            command=self._clear_input,
        )
        self.clear_input_btn.pack(side="left", padx=2)
        self.send_button = ctk.CTkButton(
            botoes, text="ENVIAR", width=90, height=38, corner_radius=0,
            fg_color="#06303C", hover_color="#0A4A5E", border_width=1, border_color=c["accent"],
            text_color=c["accent"], font=_fonte(13, True), command=self.enviar_comando,
        )
        self.send_button.pack(side="left", padx=2)

        ctk.CTkLabel(
            self.main, text="Enter envia   //   Shift+Enter quebra a linha",
            font=_fonte(10, False, FONTE_MONO), text_color=c["muted"],
        ).grid(row=4, column=0, sticky="w", padx=22, pady=(0, 10))

    @staticmethod
    def _short(s, n: int) -> str:
        s = str(s)
        return s if len(s) <= n else s[: n - 1] + "…"

    # ── Animação e relógio ─────────────────────────────────────────────

    def _tick_clock(self) -> None:
        try:
            agora = datetime.now().strftime("%d/%m/%Y  %H:%M:%S")
            if agora != self.clock_label.cget("text"):
                self.clock_label.configure(text=agora)
            self.after(250, self._tick_clock)
        except Exception:
            pass

    def _tick_telemetria(self) -> None:
        try:
            valores = {
                "CPU": psutil.cpu_percent(interval=None),
                "RAM": psutil.virtual_memory().percent,
                "DISCO": psutil.disk_usage(os.path.abspath(os.sep)).percent,
            }
            for nome, valor in valores.items():
                barra, rotulo = self.barras[nome]
                barra.set(valor / 100)
                barra.configure(progress_color=self.colors["danger"] if valor >= 90
                                else self.colors["warn"] if valor >= 75 else self.colors["accent"])
                rotulo.configure(text=f"{valor:.0f}%")
            self.after(2000, self._tick_telemetria)
        except Exception:
            pass

    def _animar_hud(self) -> None:
        try:
            self.nucleo.avancar()
            self.hud.desenhar()
            self._quadros = getattr(self, "_quadros", 0) + 1
            if self._quadros % 6 == 0:
                self._atualizar_botao_voz()
            self.after(45, self._animar_hud)
        except Exception:
            pass

    # ── Voz e estado ───────────────────────────────────────────────────

    def _falar_texto(self, texto: str) -> None:
        if not texto or not getattr(settings, "speak_responses", True):
            return
        self.nucleo.brilhar()

        def run() -> None:
            try:
                from core.voice import falar
                falar(texto)
            except Exception as exc:
                _log_error(str(exc), "tts")

        threading.Thread(target=run, daemon=True).start()

    def _set_status(self, text, color=None) -> None:
        self.status_label.configure(
            text=f"● {str(text).upper()}", text_color=color or self.colors["muted"],
        )

    def _init_assistente(self) -> None:
        def worker() -> None:
            try:
                self.after(0, lambda: self._set_status("Carregando módulos...", self.colors["warn"]))
                self.assistente = Assistente()
                self.after(0, self._on_ready)
            except Exception as e:
                msg = f"Falha ao iniciar: {str(e)[:120]}"
                _log_error(msg, "init_assistente falha")
                self.after(0, lambda m=msg: self._set_status(m, self.colors["danger"]))
                self.after(0, lambda m=msg: self._add_message("Sistema", m, is_error=True))

        threading.Thread(target=worker, daemon=True).start()

    def _on_ready(self) -> None:
        self._iniciar_servidor_flask()
        self._set_status("Pronta para ajudar", self.colors["success"])
        nome = getattr(settings, "user_name", "") or "usuário"
        saudacao = (
            f"Olá, {nome}! Estou pronta. Posso conversar, responder e executar ações permitidas no seu computador."
        )
        self._add_message("Viviane", saudacao, is_assistant=True)
        self._falar_texto(saudacao)

    # ── Chat ───────────────────────────────────────────────────────────

    def _clear_chat(self) -> None:
        for w in self.chat_canvas.winfo_children():
            w.destroy()

    def _entry_text(self) -> str:
        texto = self.entry_box.get("1.0", "end").strip()
        return "" if texto == self._placeholder else texto

    def _show_placeholder(self) -> None:
        self.entry_box.delete("1.0", "end")
        self.entry_box.insert("1.0", self._placeholder)
        self.entry_box.configure(text_color=self.colors["muted"])

    def _on_entry_focus_in(self, _event=None) -> None:
        if self.entry_box.get("1.0", "end").strip() == self._placeholder:
            self.entry_box.delete("1.0", "end")
            self.entry_box.configure(text_color=self.colors["text"])

    def _on_entry_focus_out(self, _event=None) -> None:
        if not self.entry_box.get("1.0", "end").strip():
            self._show_placeholder()

    def _clear_input(self) -> None:
        self._show_placeholder()

    def _parar_fala(self) -> None:
        try:
            from core.actions.atalhos import parar_tudo
            parar_tudo()
        except Exception as exc:
            _log_error(str(exc), "parar_fala")
        self._atualizar_botao_voz()

    def _escape(self) -> None:
        if self._falando():
            self._parar_fala()
        else:
            self._clear_input()

    @staticmethod
    def _falando() -> bool:
        try:
            from core.voice import esta_falando
            return esta_falando()
        except Exception:
            return False

    def _voz_ou_parar(self) -> None:
        if self._falando():
            self._parar_fala()
        else:
            self.ouvir_microfone()

    def _atualizar_botao_voz(self) -> None:
        if self._listening:
            return
        texto = "■  PARAR" if self._falando() else "◉  FALAR"
        if self.voice_btn.cget("text") != texto:
            self.voice_btn.configure(text=texto)

    def _quick_send(self, text: str) -> None:
        self.entry_box.configure(text_color=self.colors["text"])
        self.entry_box.delete("1.0", "end")
        self.entry_box.insert("1.0", text)
        if text.endswith(" "):
            self.entry_box.focus_set()
            return
        self.enviar_comando()

    def _on_enter(self, event):
        if event.state & 0x0001:
            return None
        self.enviar_comando()
        return "break"

    def _recarregar(self) -> None:
        self._clear_chat()
        self._set_status("Recarregando...", self.colors["warn"])
        self.assistente = None
        self._init_assistente()
        self._add_message("Sistema", "Interface recarregada com sucesso.", is_user=True)

    def _open_settings(self) -> None:
        if self._settings_dialog and self._settings_dialog.winfo_exists():
            self._settings_dialog.lift()
            return
        self._settings_dialog = SettingsDialog(self, settings)

    def _wrap(self) -> int:
        largura = self.chat_canvas.winfo_width()
        return max(320, largura - 90) if largura > 200 else 560

    @staticmethod
    def _sem_markdown(texto: str) -> str:
        texto = re.sub(r"\*\*(.+?)\*\*", r"\1", texto, flags=re.DOTALL)
        texto = re.sub(r"(?<!\w)__(.+?)__(?!\w)", r"\1", texto, flags=re.DOTALL)
        texto = re.sub(r"`+", "", texto)
        texto = re.sub(r"^\s{0,3}#{1,6}\s*", "", texto, flags=re.MULTILINE)
        texto = re.sub(r"^\s*[\*\-]\s+", "• ", texto, flags=re.MULTILINE)
        return texto.replace("**", "").strip()

    def _add_message(self, sender: str, text: str, is_user: bool = False,
                     is_assistant: bool = False, is_error: bool = False) -> None:
        if not is_user:
            text = self._sem_markdown(text)
        ts = datetime.now().strftime("%H:%M:%S")
        bubble = MessageBubble(
            self.chat_canvas, sender=sender, text=text, timestamp=ts,
            is_user=is_user, is_error=is_error, wrap=self._wrap(),
            on_copy=lambda t: self._copy_to_clipboard(t),
        )
        bubble.pack(fill="x", padx=6, pady=3)
        if is_assistant or (not is_user and not is_error and sender == "Viviane"):
            self.nucleo.brilhar()
        self.after(30, self._scroll_to_bottom)

    def _copy_to_clipboard(self, text: str) -> None:
        self.clipboard_clear()
        self.clipboard_append(text)
        self._set_status("Copiado!", self.colors["success"])
        self.after(1500, lambda: self._set_status("Pronta para ajudar", self.colors["success"]))

    def _add_typing(self) -> TypingIndicator:
        indicador = TypingIndicator(self.chat_canvas)
        indicador.pack(fill="x", padx=6, pady=3)
        self.after(30, self._scroll_to_bottom)
        return indicador

    def _scroll_to_bottom(self) -> None:
        try:
            self.chat_canvas._parent_canvas.yview_moveto(1.0)
        except Exception:
            pass

    def _set_busy(self, busy: bool, status=None, color=None) -> None:
        self._busy = busy
        state = "disabled" if busy else "normal"
        self.send_button.configure(state=state)
        self.voice_btn.configure(state=state)
        self.clear_input_btn.configure(state=state)
        self.entry_box.configure(state=state)
        if status:
            self._set_status(status, color)

    # ── Entrada de texto ───────────────────────────────────────────────

    def enviar_comando(self, texto=None) -> None:
        if self.assistente is None:
            self._add_message("Sistema", "Aguarde, a assistente ainda está inicializando.", is_error=True)
            return
        if texto is None:
            texto = self._entry_text()
        if not texto:
            return

        from core.actions.atalhos import eh_comando_parar
        if eh_comando_parar(texto):
            self._parar_fala()
            self._clear_input()
            self._add_message("Você", texto, is_user=True)
            self._add_message("Sistema", "Parei de falar.")
            return
        if self._busy:
            return

        self._clear_input()
        self._add_message("Você", texto, is_user=True)
        typing = self._add_typing()
        self._set_busy(True, "Processando...", self.colors["accent"])

        def worker() -> None:
            try:
                resposta = self.assistente.executar_comando(texto, falar_resposta=False) or ""
            except Exception as e:
                resposta = f"Erro: {str(e)[:180]}"

            def done() -> None:
                try:
                    typing.destroy()
                except Exception:
                    pass
                texto_fala = resposta.strip() or "Sem resposta."
                self._add_message("Viviane", texto_fala, is_assistant=True)
                self._falar_texto(texto_fala)
                self._set_busy(False, "Pronta para ajudar", self.colors["success"])

            self.after(0, done)

        self.thread_ia = threading.Thread(target=worker, daemon=True)
        self.thread_ia.start()

    # ── Entrada de voz ─────────────────────────────────────────────────

    def ouvir_microfone(self) -> None:
        if self.assistente is None or self._busy or self._listening:
            return
        self._listening = True
        self._set_busy(True, "Ouvindo pelo microfone...", self.colors["warn"])
        self._add_message("Sistema", "Escutando... fale seu comando.")

        def worker() -> None:
            err = ""
            try:
                texto = self.assistente.voz.ouvir_comando()
            except Exception as e:
                texto = None
                err = str(e)
                _log_error(err, "ouvir_microfone exception")

            def done() -> None:
                self._listening = False
                self._set_busy(False, "Pronta para ajudar", self.colors["success"])
                if texto:
                    self.entry_box.delete("1.0", "end")
                    self.entry_box.insert("1.0", texto)
                    self.enviar_comando()
                else:
                    msg = "Não captei áudio ou não foi possível transcrever."
                    if err:
                        msg += f" ({err[:80]})"
                    self._add_message("Sistema", msg, is_error=True)

            self.after(0, done)

        self.thread_mic = threading.Thread(target=worker, daemon=True)
        self.thread_mic.start()

    # ── Servidor Flask ─────────────────────────────────────────────────

    def _iniciar_servidor_flask(self) -> None:
        try:
            if not getattr(settings, "enable_local_web", False):
                return
            from ui.web_app import app
            host = "127.0.0.1" if getattr(settings, "local_only", True) else settings.api_host
            threading.Thread(
                target=lambda: app.run(
                    host=host,
                    port=getattr(settings, "api_port", 5000),
                    debug=False,
                    threaded=True,
                    use_reloader=False,
                ),
                daemon=True,
            ).start()
        except Exception:
            _log_error("Falha ao iniciar servidor web", "web_server_init")

    def _on_close(self) -> None:
        self.parar()
        self.destroy()

    def parar(self) -> None:
        try:
            if self.assistente:
                self.assistente.parar()
        except Exception:
            pass


# ── Entry point ──────────────────────────────────────────────────────

if __name__ == "__main__":
    app = VivianeApp()
    try:
        app.mainloop()
    except KeyboardInterrupt:
        app.parar()
    finally:
        try:
            app.parar()
        except Exception:
            pass
