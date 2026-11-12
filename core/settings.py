from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

from dotenv import load_dotenv
from os import environ

_DOTENV_PATH = Path(__file__).parent.parent / ".env"
load_dotenv(_DOTENV_PATH)

_CONFIG_KEYS = {
    "groq": ("GROQ_API_KEY",),
    "gemini": ("GEMINI_API_KEY",),
    "ollama": (),
    "openai": ("OPENAI_BASE_URL",),
    "openai_compat": ("OPENAI_BASE_URL",),
    "custom": ("OPENAI_BASE_URL",),
    "local": ("OPENAI_BASE_URL",),
    "fallback": ("GROQ_API_KEY", "GEMINI_API_KEY"),
    "auto": ("GROQ_API_KEY", "GEMINI_API_KEY"),
}

_REQUIRED_KEYS = {
    "groq": ("GROQ_API_KEY",),
    "gemini": ("GEMINI_API_KEY",),
    "openai": ("OPENAI_BASE_URL",),
    "openai_compat": ("OPENAI_BASE_URL",),
    "custom": ("OPENAI_BASE_URL",),
    "local": ("OPENAI_BASE_URL",),
    "fallback": (),
    "auto": (),
}

_PLACEHOLDER_PATTERNS = [
    r"^sk-[a-zA-Z0-9]{5,8}$",
    r"^gsk_[a-zA-Z0-9]{5,8}$",
    r"^r8_[a-zA-Z0-9]{5,10}$",
    r"^AQ\.[a-zA-Z0-9]{5,10}$",
    r"^sua[_-]",
    r"^your[_-]",
    r"^<.*>$",
]

_ENV_KEY_NAMES = [
    "GROQ_API_KEY", "GEMINI_API_KEY", "REPLICATE_API_KEY", "OPENAI_API_KEY",
    "WEATHER_API_KEY", "NEWS_API_KEY", "VIVIANE_API_TOKEN",
]

_VOZ_PADRAO = "pt-BR-ThalitaMultilingualNeural"


@dataclass
class Settings:
    BASE_DIR: ClassVar[Path] = Path(__file__).parent.parent

    ai_provider: str = field(
        default_factory=lambda: environ.get("AI_PROVIDER", "fallback")
    )
    groq_api_key: str = field(
        default_factory=lambda: environ.get("GROQ_API_KEY", "")
    )
    gemini_api_key: str = field(
        default_factory=lambda: environ.get("GEMINI_API_KEY", "")
    )
    language: str = field(default_factory=lambda: environ.get("LANGUAGE", "pt-BR"))
    assistant_name: str = field(
        default_factory=lambda: environ.get("ASSISTANT_NAME", "Viviane")
    )
    user_name: str = field(
        default_factory=lambda: environ.get("USER_NAME", "Fabricio")
    )
    weather_api_key: str = field(
        default_factory=lambda: environ.get("WEATHER_API_KEY", "")
    )
    news_api_key: str = field(
        default_factory=lambda: environ.get("NEWS_API_KEY", "")
    )
    replicate_api_key: str = field(
        default_factory=lambda: environ.get("REPLICATE_API_KEY", "")
    )
    ollama_model: str = field(
        default_factory=lambda: environ.get("OLLAMA_MODEL", "llama3")
    )
    ollama_url: str = field(
        default_factory=lambda: environ.get("OLLAMA_URL", "http://localhost:11434")
    )
    openai_base_url: str = field(
        default_factory=lambda: environ.get("OPENAI_BASE_URL", "").rstrip("/")
    )
    openai_api_key: str = field(
        default_factory=lambda: environ.get("OPENAI_API_KEY", "")
    )
    openai_model: str = field(
        default_factory=lambda: environ.get("OPENAI_MODEL", "")
    )
    tts_voice: str = field(
        default_factory=lambda: environ.get("TTS_VOICE", _VOZ_PADRAO)
    )
    tts_engine: str = field(
        default_factory=lambda: environ.get("TTS_ENGINE", "edge")
    )
    tts_rate: str = field(
        default_factory=lambda: environ.get("TTS_RATE", "+12%")
    )
    tts_pitch: str = field(
        default_factory=lambda: environ.get("TTS_PITCH", "+8Hz")
    )
    api_host: str = field(
        default_factory=lambda: environ.get("VIVIANE_HOST", "127.0.0.1")
    )
    api_port: int = field(
        default_factory=lambda: int(environ.get("PORT", environ.get("VIVIANE_PORT", "5000")))
    )
    api_token: str = field(
        default_factory=lambda: environ.get("VIVIANE_API_TOKEN", "")
    )
    data_dir: Path = field(
        default_factory=lambda: Path(environ.get("VIVIANE_DATA_DIR", str(Settings.BASE_DIR / "data")))
    )
    whisper_model: str = field(
        default_factory=lambda: environ.get("VIVIANE_WHISPER_MODEL", "tiny")
    )
    allow_origins: str = field(
        default_factory=lambda: environ.get(
            "VIVIANE_ALLOW_ORIGINS",
            "",
        )
    )
    # Wake Word settings
    wake_word: str = field(
        default_factory=lambda: environ.get("WAKE_WORD", "oi viviane")
    )
    wake_word_engine: str = field(
        default_factory=lambda: environ.get("WAKE_WORD_ENGINE", "simple")
    )
    wake_word_sensitivity: float = field(
        default_factory=lambda: float(environ.get("WAKE_WORD_SENSITIVITY", "0.6"))
    )
    # Safety / platform
    allow_system_actions: bool = field(
        default_factory=lambda: environ.get("ALLOW_SYSTEM_ACTIONS", "true").lower() in ("1", "true", "yes", "on")
    )
    enable_local_web: bool = field(
        default_factory=lambda: environ.get("ENABLE_LOCAL_WEB", "false").lower() in ("1", "true", "yes", "on")
    )
    # Núcleo / UX
    speak_responses: bool = field(
        default_factory=lambda: environ.get("VIVIANE_SPEAK_RESPONSES", "true").lower() in ("1", "true", "yes", "on")
    )
    mic_continuo: bool = field(
        default_factory=lambda: environ.get("VIVIANE_MIC_ATIVO", "true").lower() in ("1", "true", "yes", "on")
    )
    enable_face_recognition: bool = field(
        default_factory=lambda: environ.get("ENABLE_FACE_RECOGNITION", "true").lower() in ("1", "true", "yes", "on")
    )
    enable_continuous_learning: bool = field(
        default_factory=lambda: environ.get("ENABLE_CONTINUOUS_LEARNING", "true").lower() in ("1", "true", "yes", "on")
    )
    local_only: bool = field(
        default_factory=lambda: environ.get("LOCAL_ONLY", "true").lower() in ("1", "true", "yes", "on")
    )

    def __post_init__(self) -> None:
        aplicar_modo_local(self)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        if self.tts_engine not in ("edge", "sapi"):
            self.tts_engine = "edge"
        erros = self.validar()
        if erros:
            for e in erros:
                print(f"[CONFIG] {e}", file=sys.stderr)
        seguranca = self.auditar_seguranca()
        if seguranca:
            for s in seguranca:
                print(f"[SEGURANCA] {s}", file=sys.stderr)

    def auditar_seguranca(self) -> list[str]:
        avisos = []
        if not _DOTENV_PATH.exists():
            return avisos
        try:
            with open(_DOTENV_PATH, encoding="utf-8") as f:
                conteudo = f.read()
        except Exception:
            return avisos
        for nome_chave in _ENV_KEY_NAMES:
            valor = getattr(self, nome_chave.lower(), "")
            if not valor:
                continue
            resp = re.match(rf"^{nome_chave}=(.+)$", conteudo, re.MULTILINE)
            if not resp:
                continue
            if any(re.match(p, valor) for p in _PLACEHOLDER_PATTERNS):
                continue
        return avisos

    def validar(self) -> list[str]:
        erros = []
        if self.ai_provider not in ("groq", "gemini", "ollama", "openai", "openai_compat", "custom", "local", "fallback", "auto"):
            erros.append(f"AI_PROVIDER inválido: '{self.ai_provider}'. Use groq, gemini, ollama, openai, fallback ou auto.")
        required = _REQUIRED_KEYS.get(self.ai_provider, ())
        for k in required:
            if not getattr(self, k.lower(), ""):
                erros.append(f"{k} não configurada no .env (necessário para provider '{self.ai_provider}')")
        return erros


def aplicar_modo_local(cfg: Settings) -> None:
    """Enquanto LOCAL_ONLY estiver ligado, nada escuta fora deste computador."""
    if not cfg.local_only:
        return
    host = (cfg.api_host or "").strip().lower()
    if host not in ("127.0.0.1", "localhost", "::1", ""):
        print("[LOCAL] Endereço público ignorado. Viviane fica em 127.0.0.1.", file=sys.stderr)
    cfg.api_host = "127.0.0.1"
    cfg.allow_origins = ""


settings = Settings()
