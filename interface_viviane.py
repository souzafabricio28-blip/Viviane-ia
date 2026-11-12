from __future__ import annotations

import os
import sys
import threading
import time
import logging
import traceback
from datetime import datetime

_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import customtkinter as ctk

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


# ── Cores e configurações visuais ──────────────────────────────────────

COLORS = {
    "bg": "#070B12",
    "panel": "#0E1522",
    "panel_alt": "#141C2B",
    "card": "#1A2436",
    "accent": "#3EE0C5",
    "accent_2": "#3B82F6",
    "accent_3": "#8AF0DE",
    "user": "#102033",
    "assistant": "#141C2B",
    "text": "#E8EEF7",
    "muted": "#8AA0B8",
    "success": "#3DDC97",
    "warn": "#F0B429",
    "danger": "#F07178",
    "border": "#2A384C",
    "glow": "#3EE0C5",
}

ORB_STATES = ["●", "○", "●", "○"]
ORB_ANIM_DELAY = 180


# ── Componentes da UI ──────────────────────────────────────────────────

class MessageBubble(ctk.CTkFrame):
    """Bolha de mensagem - Estilo JARVIS."""

    def __init__(self, parent, sender: str, text: str, timestamp: str,
                 is_user: bool, is_error: bool = False, on_copy=None):
        super().__init__(parent, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)

        if is_user:
            bubble_color = COLORS["user"]
            text_color = COLORS["text"]
            border_color = COLORS["accent"]
            avatar_text = "Eu"
            avatar_color = COLORS["accent"]
            avatar_text_color = "#071018"
        elif is_error:
            bubble_color = "#2A1518"
            text_color = "#FFB4B4"
            border_color = COLORS["danger"]
            avatar_text = "!"
            avatar_color = COLORS["danger"]
            avatar_text_color = "#1A0A0C"
        else:
            bubble_color = COLORS["assistant"]
            text_color = COLORS["text"]
            border_color = COLORS["border"]
            avatar_text = "V"
            avatar_color = COLORS["accent_2"]
            avatar_text_color = "#F4F7FB"

        self.columnconfigure(1, weight=1)

        avatar_size = 34
        avatar_col = 2 if is_user else 0
        avatar = ctk.CTkLabel(
            self, text=avatar_text, width=avatar_size, height=avatar_size,
            corner_radius=avatar_size // 2, fg_color=avatar_color,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=avatar_text_color
        )
        avatar.grid(row=0, column=avatar_col, padx=(4, 8) if not is_user else (8, 4), pady=(4, 0), sticky="n")

        # Bubble frame
        bubble = ctk.CTkFrame(self, fg_color=bubble_color, corner_radius=16,
                              border_width=1, border_color=border_color)
        bubble.grid(row=0, column=1, sticky="ew", padx=4, pady=2)
        bubble.grid_columnconfigure(0, weight=1)

        # Header with sender name and timestamp
        header = ctk.CTkFrame(bubble, fg_color="transparent")
        header.pack(fill="x", padx=12, pady=(6, 2))
        ctk.CTkLabel(
            header, text=f"{sender}   {timestamp}",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLORS["muted"]
        ).pack(side="left")
        if on_copy:
            ctk.CTkButton(
                header, text="⧉", width=24, height=24, corner_radius=6,
                fg_color="transparent", hover_color=COLORS["panel_alt"],
                text_color=COLORS["muted"], font=ctk.CTkFont(size=11),
                command=lambda: on_copy(text)
            ).pack(side="right", padx=4)

        # Message text
        msg = ctk.CTkLabel(
            bubble, text=text, font=ctk.CTkFont(size=14), text_color=text_color,
            justify="left", wraplength=640, anchor="w"
        )
        msg.pack(fill="x", padx=12, pady=(0, 8))


class TypingIndicator(ctk.CTkFrame):
    """Indicador de digitação animado."""

    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)

        colors = {"panel_alt": COLORS["panel_alt"], "muted": COLORS["muted"], "border": COLORS["border"]}

        bubble = ctk.CTkFrame(self, fg_color=colors["panel_alt"], corner_radius=18,
                              border_width=1, border_color=colors["border"])
        bubble.grid(row=0, column=0, sticky="w", padx=4, pady=2)

        self.dots = []
        for i in range(3):
            dot = ctk.CTkLabel(bubble, text="●", font=ctk.CTkFont(size=16, weight="bold"),
                               text_color=colors["muted"])
            dot.pack(side="left", padx=4, pady=8)
            self.dots.append(dot)

        self._anim_idx = 0
        self._animate()

    def _animate(self):
        colors = {"muted": COLORS["muted"], "accent": COLORS["accent"]}
        for i, dot in enumerate(self.dots):
            dot.configure(text_color=colors["accent"] if i == self._anim_idx else colors["muted"])
        self._anim_idx = (self._anim_idx + 1) % 3
        self.after(350, self._animate)


class OrbPulse(ctk.CTkLabel):
    """Orb pulsante JARVIS - indica estado de escuta."""

    def __init__(self, parent, fg_color, text_color):
        super().__init__(parent, text="V", fg_color=fg_color, text_color=text_color,
                         width=52, height=52, corner_radius=26,
                         font=ctk.CTkFont(size=22, weight="bold"))
        self._idx = 0
        self._animate()

    def _animate(self):
        # Efeito de pulso JARVIS
        colors = [COLORS["accent"], COLORS["accent_2"], COLORS["accent_3"], COLORS["accent"]]
        self.configure(text_color=colors[self._idx % len(colors)])
        self._idx = (self._idx + 1) % len(colors)
        self.after(200, self._animate)


# ── Janela principal ───────────────────────────────────────────────────

class VivianeApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Viviane IA")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self._fit_to_screen()
        self._placeholder = "Escreva uma mensagem..."

        self.colors = COLORS
        self.configure(fg_color=self.colors["bg"])

        self.assistente = None
        self.thread_ia = None
        self.thread_mic = None
        self._busy = False
        self._sidebar_collapsed = False
        self._settings_dialog = None
        self._listening = False
        self._last_clock = 0

        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Bindings de teclado
        self.bind("<Control-Return>", lambda e: self.enviar_comando())
        self.bind("<Control-l>", lambda e: self._clear_chat())
        self.bind("<Control-s>", lambda e: self._open_settings())
        self.bind("<Escape>", lambda e: self._clear_input())

        self._build_ui()
        self._set_status("Inicializando assistente...", self.colors["warn"])
        self.after(200, self._init_assistente)
        self._start_wake_word()

    def _fit_to_screen(self):
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w = min(1120, max(880, sw - 80))
        h = min(720, max(560, sh - 96))
        x = max(0, (sw - w) // 2)
        y = max(0, (sh - h) // 2 - 16)
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.minsize(min(860, sw - 40), min(560, sh - 80))

    # ── Wake Word ──────────────────────────────────────────────────────

    def _start_wake_word(self):
        """Inicia o detector de wake word (palavra-chave 'oi viviane')."""
        try:
            from core.skills.wake_word import wake_word_manager
            wake_word_manager.set_activation_callback(self._on_wake_word)
            wake_word_manager.start()
            self._set_status("Ouvindo... diga 'oi viviane'", self.colors["success"])
        except Exception as e:
            _log_error(str(e), "wake_word_start")

    def _on_wake_word(self, keyword: str):
        """Callback quando a wake word é detectada."""
        self.after(0, lambda: self._set_status("Escutando seu comando...", self.colors["success"]))
        self.after(0, lambda: self._add_message("Viviane", "O que posso fazer por você?"))
        self.after(0, lambda: self.entry_box.focus_set())
        self.after(0, lambda: self._set_busy(False, "Aguardando comando...", self.colors["success"]))

    # ── Construção da UI ──────────────────────────────────────────────

    def _build_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = ctk.CTkFrame(self, width=292, corner_radius=0, fg_color=self.colors["panel"])
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        self.sidebar.grid_columnconfigure(0, weight=1)
        self.sidebar.grid_rowconfigure(2, weight=1)

        brand = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        brand.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 8))
        self.orb = OrbPulse(brand, COLORS["panel_alt"], COLORS["accent"])
        self.orb.pack(side="left")
        titles = ctk.CTkFrame(brand, fg_color="transparent")
        titles.pack(side="left", padx=(12, 0))
        ctk.CTkLabel(
            titles, text="Viviane",
            font=ctk.CTkFont(size=24, weight="bold"), text_color=self.colors["text"],
        ).pack(anchor="w")
        ctk.CTkLabel(
            titles, text="Assistente neste computador",
            font=ctk.CTkFont(size=12), text_color=self.colors["muted"],
        ).pack(anchor="w")

        self.status_card = ctk.CTkFrame(
            self.sidebar, fg_color=self.colors["panel_alt"], corner_radius=14,
            border_width=1, border_color=self.colors["border"],
        )
        self.status_card.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 8))
        ctk.CTkLabel(
            self.status_card, text="Estado",
            font=ctk.CTkFont(size=11, weight="bold"), text_color=self.colors["muted"],
        ).pack(anchor="w", padx=12, pady=(10, 0))
        self.status_label = ctk.CTkLabel(
            self.status_card, text="Iniciando...",
            font=ctk.CTkFont(size=14, weight="bold"), text_color=self.colors["warn"],
            justify="left", wraplength=230, anchor="w",
        )
        self.status_label.pack(anchor="w", padx=12, pady=(2, 12))

        self.side_scroll = ctk.CTkScrollableFrame(
            self.sidebar, fg_color="transparent", corner_radius=0,
        )
        self.side_scroll.grid(row=2, column=0, sticky="nsew", padx=8, pady=0)

        info_card = ctk.CTkFrame(self.side_scroll, fg_color=self.colors["panel_alt"], corner_radius=14)
        info_card.pack(fill="x", padx=8, pady=(4, 8))
        self._info_row(info_card, "Provedor", getattr(settings, "ai_provider", "-"))
        self._info_row(info_card, "Modelo", getattr(settings, "openai_model", "") or "(automático)")
        base = getattr(settings, "openai_base_url", "") or "neste computador"
        self._info_row(info_card, "Onde responde", self._short(base, 36))
        self._info_row(info_card, "Usuário", str(getattr(settings, "user_name", "Usuário")))

        actions_card = ctk.CTkFrame(self.side_scroll, fg_color=self.colors["panel_alt"], corner_radius=14)
        actions_card.pack(fill="x", padx=8, pady=(0, 8))
        ctk.CTkLabel(
            actions_card, text="Ações rápidas",
            font=ctk.CTkFont(size=12, weight="bold"), text_color=self.colors["muted"],
        ).pack(anchor="w", padx=12, pady=(10, 6))
        quick_actions = [
            ("Que horas são?", "Que horas são?"),
            ("Status do PC", "Faça um diagnóstico do sistema"),
            ("Previsão do tempo", "Qual a previsão do tempo em São Paulo?"),
            ("Programas abertos", "Quais programas estão abertos?"),
            ("Criar lembrete", "Lembrete em 30 minutos tomar água"),
            ("Pesquisar na web", "Pesquise sobre..."),
        ]
        for label, cmd in quick_actions:
            ctk.CTkButton(
                actions_card, text=label, height=32, corner_radius=8,
                fg_color=self.colors["card"], hover_color=self.colors["border"],
                text_color=self.colors["text"], anchor="w",
                command=lambda c=cmd: self._quick_send(c),
            ).pack(fill="x", padx=12, pady=3)
        ctk.CTkFrame(actions_card, height=8, fg_color="transparent").pack()

        footer = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        footer.grid(row=3, column=0, sticky="ew", padx=16, pady=(6, 14))
        icon_row = ctk.CTkFrame(footer, fg_color="transparent")
        icon_row.pack(fill="x", pady=(0, 8))
        self.collapse_btn = ctk.CTkButton(
            icon_row, text="◀", width=36, height=34, corner_radius=8,
            fg_color=self.colors["card"], hover_color=self.colors["border"],
            text_color=self.colors["text"], command=self._toggle_sidebar,
        )
        self.collapse_btn.pack(side="left", padx=(0, 6))
        self.reload_btn = ctk.CTkButton(
            icon_row, text="↻", width=36, height=34, corner_radius=8,
            fg_color=self.colors["card"], hover_color=self.colors["border"],
            text_color=self.colors["accent"], command=self._recarregar,
        )
        self.reload_btn.pack(side="left")
        self.voice_btn = ctk.CTkButton(
            footer, text="Falar", height=40, corner_radius=10,
            fg_color=self.colors["accent_2"], hover_color="#2563EB",
            text_color="white", font=ctk.CTkFont(size=14, weight="bold"),
            command=self.ouvir_microfone,
        )
        self.voice_btn.pack(fill="x", pady=(0, 6))
        self.clear_chat_btn = ctk.CTkButton(
            footer, text="Limpar conversa", height=34, corner_radius=8,
            fg_color=self.colors["panel_alt"], hover_color=self.colors["border"],
            text_color=self.colors["muted"], command=self._clear_chat,
        )
        self.clear_chat_btn.pack(fill="x", pady=(0, 6))
        self.settings_btn = ctk.CTkButton(
            footer, text="Configurações", height=34, corner_radius=8,
            fg_color=self.colors["panel_alt"], hover_color=self.colors["border"],
            text_color=self.colors["accent"], command=self._open_settings,
        )
        self.settings_btn.pack(fill="x")

        self.main = ctk.CTkFrame(self, corner_radius=0, fg_color=self.colors["bg"])
        self.main.grid(row=0, column=1, sticky="nsew")
        self.main.grid_rowconfigure(1, weight=1)
        self.main.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(self.main, fg_color=self.colors["bg"], corner_radius=0)
        header.grid(row=0, column=0, sticky="ew", padx=22, pady=(16, 6))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            header, text="Conversa",
            font=ctk.CTkFont(size=26, weight="bold"), text_color=self.colors["text"],
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            header, text="Texto e voz, só neste computador",
            font=ctk.CTkFont(size=12), text_color=self.colors["muted"],
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))
        self.clock_label = ctk.CTkLabel(
            header, text="", font=ctk.CTkFont(size=13, weight="bold"),
            text_color=self.colors["accent"],
        )
        self.clock_label.grid(row=0, column=1, rowspan=2, sticky="e")
        self._tick_clock()

        chat_wrap = ctk.CTkFrame(
            self.main, fg_color=self.colors["panel"], corner_radius=16,
            border_width=1, border_color=self.colors["border"],
        )
        chat_wrap.grid(row=1, column=0, sticky="nsew", padx=22, pady=(6, 10))
        chat_wrap.grid_rowconfigure(0, weight=1)
        chat_wrap.grid_columnconfigure(0, weight=1)
        self.chat_canvas = ctk.CTkScrollableFrame(chat_wrap, fg_color="transparent", corner_radius=0)
        self.chat_canvas.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        self.chat_canvas.grid_columnconfigure(0, weight=1)

        input_bar = ctk.CTkFrame(
            self.main, fg_color=self.colors["panel"], corner_radius=16,
            border_width=1, border_color=self.colors["border"],
        )
        input_bar.grid(row=2, column=0, sticky="ew", padx=22, pady=(0, 8))
        input_bar.grid_columnconfigure(0, weight=1)
        self.entry_box = ctk.CTkTextbox(
            input_bar, height=56, corner_radius=12,
            fg_color=self.colors["panel_alt"], border_width=0,
            text_color=self.colors["muted"], font=ctk.CTkFont(size=15), wrap="word",
        )
        self.entry_box.grid(row=0, column=0, sticky="ew", padx=(12, 8), pady=12)
        self.entry_box.insert("1.0", self._placeholder)
        self.entry_box.bind("<FocusIn>", self._on_entry_focus_in)
        self.entry_box.bind("<FocusOut>", self._on_entry_focus_out)
        self.entry_box.bind("<Return>", self._on_enter)
        self.entry_box.bind("<Shift-Return>", lambda e: None)

        btns = ctk.CTkFrame(input_bar, fg_color="transparent")
        btns.grid(row=0, column=1, sticky="e", padx=(0, 12), pady=12)
        self.clear_input_btn = ctk.CTkButton(
            btns, text="✕", width=40, height=40, corner_radius=10,
            fg_color="transparent", hover_color=self.colors["card"],
            text_color=self.colors["muted"], font=ctk.CTkFont(size=16, weight="bold"),
            command=self._clear_input,
        )
        self.clear_input_btn.pack(side="left", padx=4)
        self.send_button = ctk.CTkButton(
            btns, text="Enviar", width=84, height=40, corner_radius=10,
            fg_color=self.colors["accent"], hover_color=self.colors["accent_3"],
            text_color="#071018", font=ctk.CTkFont(size=14, weight="bold"),
            command=self.enviar_comando,
        )
        self.send_button.pack(side="left", padx=4)

        ctk.CTkLabel(
            self.main, text="Enter envia    Shift+Enter quebra a linha",
            font=ctk.CTkFont(size=11), text_color=self.colors["muted"],
        ).grid(row=3, column=0, sticky="w", padx=28, pady=(0, 12))

    def _info_row(self, parent, label, value):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=4)
        ctk.CTkLabel(row, text=label, font=ctk.CTkFont(size=11), text_color=self.colors["muted"]).pack(anchor="w")
        ctk.CTkLabel(row, text=value, font=ctk.CTkFont(size=12, weight="bold"),
                    text_color=self.colors["text"], justify="left", wraplength=220).pack(anchor="w")

    @staticmethod
    def _short(s, n):
        s = str(s)
        return s if len(s) <= n else s[: n - 1] + "…"

    def _tick_clock(self):
        now = datetime.now().strftime("%d/%m/%Y  %H:%M:%S")
        if now != self.clock_label.cget("text"):
            self.clock_label.configure(text=now)
        self.after(200, self._tick_clock)

    def _set_status(self, text, color=None):
        self.status_label.configure(text=text, text_color=color or self.colors["muted"])
        orb_color = color or self.colors["accent"]
        self.orb.configure(text_color=orb_color)

    def _init_assistente(self):
        def worker():
            try:
                self._set_status("Carregando módulos...", self.colors["warn"])
                self.assistente = Assistente()
                self.after(0, self._on_ready)
            except Exception as e:
                msg = f"Falha ao iniciar: {str(e)[:120]}"
                _log_error(msg, "init_assistente falha")
                self.after(0, lambda m=msg: self._set_status(m, self.colors["danger"]))
                self.after(0, lambda m=msg: self._add_message("Sistema", m, is_error=True))

        threading.Thread(target=worker, daemon=True).start()

    def _on_ready(self):
        self._iniciar_servidor_flask()
        self._set_status("Pronta para ajudar", self.colors["success"])
        self._add_message("Viviane", f"Olá, {getattr(settings, 'user_name', '') or 'usuário'}! "
                        f"Estou pronta. Posso conversar, responder e executar ações permitidas no seu computador.",
                        is_assistant=True)

    def _clear_chat(self):
        for w in self.chat_canvas.winfo_children():
            w.destroy()

    def _entry_text(self) -> str:
        texto = self.entry_box.get("1.0", "end").strip()
        if texto == self._placeholder:
            return ""
        return texto

    def _show_placeholder(self):
        self.entry_box.delete("1.0", "end")
        self.entry_box.insert("1.0", self._placeholder)
        self.entry_box.configure(text_color=self.colors["muted"])

    def _on_entry_focus_in(self, _event=None):
        if self.entry_box.get("1.0", "end").strip() == self._placeholder:
            self.entry_box.delete("1.0", "end")
            self.entry_box.configure(text_color=self.colors["text"])

    def _on_entry_focus_out(self, _event=None):
        if not self.entry_box.get("1.0", "end").strip():
            self._show_placeholder()

    def _clear_input(self):
        self._show_placeholder()

    def _quick_send(self, text):
        self.entry_box.configure(text_color=self.colors["text"])
        self.entry_box.delete("1.0", "end")
        self.entry_box.insert("1.0", text)
        self.enviar_comando()

    def _on_enter(self, event):
        if event.state & 0x0001:  # Shift
            return None
        self.enviar_comando()
        return "break"

    def _toggle_sidebar(self):
        self._sidebar_collapsed = not self._sidebar_collapsed
        if self._sidebar_collapsed:
            self.sidebar.configure(width=84)
            self.side_scroll.grid_remove()
            self.status_card.grid_remove()
            self.voice_btn.configure(text="Voz")
            self.clear_chat_btn.pack_forget()
            self.settings_btn.pack_forget()
            self.collapse_btn.configure(text="▶")
        else:
            self.sidebar.configure(width=292)
            self.status_card.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 8))
            self.side_scroll.grid(row=2, column=0, sticky="nsew", padx=8, pady=0)
            self.voice_btn.configure(text="Falar")
            self.clear_chat_btn.pack(fill="x", pady=(0, 6))
            self.settings_btn.pack(fill="x")
            self.collapse_btn.configure(text="◀")

    def _recarregar(self):
        """Recarrega a interface - limpa chat e reinicia assistente."""
        self._clear_chat()
        self._set_status("Recarregando...", self.colors["warn"])
        self.assistente = None
        self._init_assistente()
        self._add_message("Sistema", "Interface recarregada com sucesso.", is_user=True)

    def _open_settings(self):
        if self._settings_dialog and self._settings_dialog.winfo_exists():
            self._settings_dialog.lift()
            return
        self._settings_dialog = SettingsDialog(self, settings)

    def _add_message(self, sender: str, text: str, is_user: bool = False, is_assistant: bool = False, is_error: bool = False):
        ts = datetime.now().strftime("%H:%M:%S")
        bubble = MessageBubble(
            self.chat_canvas,
            sender=sender,
            text=text,
            timestamp=ts,
            is_user=is_user,
            is_error=is_error,
            on_copy=lambda t: self._copy_to_clipboard(t)
        )
        bubble.pack(fill="x", padx=6, pady=4)
        self.after(30, self._scroll_to_bottom)

    def _copy_to_clipboard(self, text):
        self.clipboard_clear()
        self.clipboard_append(text)
        self._set_status("Copiado!", self.colors["success"])
        self.after(1500, lambda: self._set_status("Pronta para ajudar", self.colors["success"]))

    def _add_typing(self):
        indicator = TypingIndicator(self.chat_canvas)
        indicator.pack(fill="x", padx=6, pady=4)
        self.after(30, self._scroll_to_bottom)
        return indicator

    def _scroll_to_bottom(self):
        try:
            canvas = self.chat_canvas._parent_canvas
            canvas.yview_moveto(1.0)
        except Exception:
            pass

    def _set_busy(self, busy, status=None, color=None):
        self._busy = busy
        state = "disabled" if busy else "normal"
        self.send_button.configure(state=state)
        self.voice_btn.configure(state=state)
        self.clear_input_btn.configure(state=state)
        self.entry_box.configure(state=state)
        if status:
            self._set_status(status, color)

    # ── Entrada de texto ────────────────────────────────────────────

    def enviar_comando(self, texto=None):
        if self.assistente is None:
            self._add_message("Sistema", "Aguarde, a assistente ainda está inicializando.", is_error=True)
            return
        if texto is None:
            texto = self._entry_text()
        if not texto:
            return
        if self._busy:
            return

        self._clear_input()
        self._add_message("Você", texto, is_user=True)
        typing = self._add_typing()
        self._set_busy(True, "Processando...", self.colors["accent"])

        def worker():
            try:
                from core.settings import settings as _st
                speak = bool(getattr(_st, "speak_responses", True))
                resposta = self.assistente.executar_comando(texto, falar_resposta=speak) or ""
            except Exception as e:
                resposta = f"Erro: {str(e)[:180]}"
            def done():
                try:
                    typing.destroy()
                except Exception:
                    pass
                self._add_message("Viviane", resposta.strip() or "Sem resposta.", is_assistant=True)
                self._set_busy(False, "Pronta para ajudar", self.colors["success"])
            self.after(0, done)

        self.thread_ia = threading.Thread(target=worker, daemon=True)
        self.thread_ia.start()

    # ── Entrada de voz ──────────────────────────────────────────────

    def ouvir_microfone(self):
        if self.assistente is None or self._busy or self._listening:
            return
        self._listening = True
        self._set_busy(True, "Ouvindo pelo microfone...", self.colors["warn"])
        self._add_message("Sistema", "Escutando... fale seu comando.")

        def worker():
            try:
                texto = self.assistente.voz.ouvir_comando()
            except Exception as e:
                texto = None
                err = str(e)
                _log_error(err, "ouvir_microfone exception")
            else:
                err = ""
            def done():
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

    # ── Servidor Flask ──────────────────────────────────────────────

    def _iniciar_servidor_flask(self):
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

    def _on_close(self):
        self.parar()
        self.destroy()

    def parar(self):
        try:
            if self.assistente:
                self.assistente.parar()
        except Exception:
            pass

    # ── Dialog de configurações ─────────────────────────────────────

    class SettingsDialog(ctk.CTkToplevel):
        """Dialog de configurações."""

        def __init__(self, parent, current_settings):
            super().__init__(parent)
            self.title("Configurações")
            self.geometry("520x620")
            self.resizable(False, False)
            self.transient(parent)
            self.grab_set()

            self.current = current_settings
            self.vars = {}
            self._build_ui()

        def _build_ui(self):
            ctk.set_appearance_mode("dark")
            scroll = ctk.CTkScrollableFrame(self, corner_radius=0)
            scroll.pack(fill="both", expand=True, padx=20, pady=20)

            # Theme
            self._section(scroll, "Aparência")
            self._combobox_row(scroll, "Tema", "theme", ["Escuro", "Claro", "Sistema"],
                           "Escuro" if settings.ai_provider != "light" else "Claro")

            # AI Provider
            self._section(scroll, "IA / Provedor")
            providers = ["openai", "groq", "gemini", "ollama", "fallback", "auto"]
            self._combobox_row(scroll, "Provedor", "ai_provider", providers,
                           getattr(settings, "ai_provider", "openai"))
            self._entry_row(scroll, "Base URL (OpenAI-compat)", "openai_base_url",
                         getattr(settings, "openai_base_url", ""))
            self._entry_row(scroll, "API Key", "openai_api_key",
                         getattr(settings, "openai_api_key", ""), show="*")
            self._entry_row(scroll, "Modelo", "openai_model",
                         getattr(settings, "openai_model", ""))

            # Voice
            self._section(scroll, "Voz")
            self._switch_row(scroll, "Falar respostas", "speak_responses",
                         getattr(settings, "speak_responses", True))
            self._entry_row(scroll, "Voz TTS", "tts_voice",
                         getattr(settings, "tts_voice", "pt-BR-FranciscaNeural"))
            self._entry_row(scroll, "Engine TTS", "tts_engine",
                         getattr(settings, "tts_engine", "edge"))

            # Permissions
            self._section(scroll, "Permissões")
            self._switch_row(scroll, "Ações de sistema", "allow_system_actions",
                         getattr(settings, "allow_system_actions", True))
            self._switch_row(scroll, "Painel web neste PC (127.0.0.1)", "enable_local_web",
                         getattr(settings, "enable_local_web", False))

            # Wake word
            self._section(scroll, "Wake Word")
            self._entry_row(scroll, "Palavra-chave", "wake_word",
                         getattr(settings, "wake_word", "oi viviane"))
            self._combobox_row(scroll, "Engine", "wake_word_engine", ["simple", "openwakeword", "vosk"],
                           getattr(settings, "wake_word_engine", "simple"))

            # Buttons
            btn_frame = ctk.CTkFrame(self, fg_color="transparent")
            btn_frame.pack(fill="x", padx=20, pady=20)
            ctk.CTkButton(btn_frame, text="Salvar", width=140, height=40, corner_radius=10,
                         command=self._save).pack(side="right", padx=8)
            ctk.CTkButton(btn_frame, text="Cancelar", width=140, height=40, corner_radius=10,
                         fg_color="#374151", hover_color="#4B5563", command=self.destroy).pack(side="right")

        def _section(self, parent, title):
            ctk.CTkLabel(parent, text=title, font=ctk.CTkFont(size=14, weight="bold"),
                        text_color="#4CC9F0").pack(anchor="w", pady=(16, 8))

        def _combobox_row(self, parent, label, key, values, current):
            row = ctk.CTkFrame(parent, fg_color="transparent")
            row.pack(fill="x", pady=4)
            ctk.CTkLabel(row, text=label, font=ctk.CTkFont(size=12), text_color="#93A4C3").pack(anchor="w")
            var = ctk.StringVar(value=str(current))
            self.vars[key] = var
            ctk.CTkComboBox(row, values=values, variable=var, width=300, height=36,
                           corner_radius=8, font=ctk.CTkFont(size=12)).pack(fill="x", pady=(4, 0))

        def _entry_row(self, parent, label, key, current, show=None):
            row = ctk.CTkFrame(parent, fg_color="transparent")
            row.pack(fill="x", pady=4)
            ctk.CTkLabel(row, text=label, font=ctk.CTkFont(size=12), text_color="#93A4C3").pack(anchor="w")
            var = ctk.StringVar(value=str(current))
            self.vars[key] = var
            ctk.CTkEntry(row, textvariable=var, width=300, height=36, corner_radius=8,
                        font=ctk.CTkFont(size=14), show=show or "").pack(fill="x", pady=(4, 0))

        def _switch_row(self, parent, label, key, current):
            row = ctk.CTkFrame(parent, fg_color="transparent")
            row.pack(fill="x", pady=4)
            ctk.CTkLabel(row, text=label, font=ctk.CTkFont(size=12), text_color="#93A4C3").pack(anchor="w")
            var = ctk.BooleanVar(value=bool(current))
            self.vars[key] = var
            ctk.CTkSwitch(row, text="Ativado", variable=var, font=ctk.CTkFont(size=12),
                         progress_color="#4CC9F0").pack(anchor="w", pady=(4, 0))

        def _save(self):
            for key, var in self.vars.items():
                val = var.get()
                if isinstance(var, ctk.BooleanVar):
                    setattr(settings, key, val)
                else:
                    setattr(settings, key, val)
            self._save_env()
            self.destroy()

        def _save_env(self):
            env_path = os.path.join(_PROJECT_ROOT, ".env")
            lines = []
            if os.path.exists(env_path):
                with open(env_path, "r", encoding="utf-8") as f:
                    lines = f.read().splitlines()

            updates = {k: v.get() for k, v in self.vars.items()}
            for i, line in enumerate(lines):
                if "=" in line:
                    k = line.split("=")[0].strip()
                    if k in updates:
                        lines[i] = f"{k}={updates[k]}"
                        del updates[k]

            for k, v in updates.items():
                lines.append(f"{k}={v}")

            with open(env_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")


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