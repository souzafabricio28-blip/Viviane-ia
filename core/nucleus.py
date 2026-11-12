from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from core.settings import settings
from core.memoria import memoria as db_memoria
from core.skills.aprendizado import aprendizado

log = logging.getLogger("Viviane.Nucleo")


@dataclass
class NucleoInteligencia:
    """Nucleo central: integra percepcao, memoria/aprendizado, acao e identidade."""

    initialized: bool = False
    last_identity: str | None = None
    capabilities: dict[str, bool] = field(default_factory=dict)

    def initialize(self) -> dict[str, Any]:
        self.capabilities = {
            "comandos": True,
            "voz_entrada": True,
            "voz_saida_feminina": "Neural" in getattr(settings, "tts_voice", "") or getattr(settings, "tts_engine", "") == "edge",
            "aprendizado": bool(getattr(settings, "enable_continuous_learning", True)),
            "memoria": True,
            "conhecimento": True,
            "reconhecimento_facial": bool(getattr(settings, "enable_face_recognition", True)),
            "ia_online": bool(getattr(settings, "openai_base_url", "") or getattr(settings, "groq_api_key", "") or getattr(settings, "gemini_api_key", "")),
        }
        self.initialized = True
        return self.status()

    def status(self) -> dict[str, Any]:
        stats = {}
        try:
            stats = aprendizado.obter_estatisticas()
        except Exception:
            stats = {}
        try:
            cont = db_memoria.db_contagem()
        except Exception:
            cont = {}
        return {
            "initialized": self.initialized,
            "identity": self.last_identity,
            "capabilities": self.capabilities,
            "learning": {
                "comandos_aprendidos": stats.get("comandos_aprendidos", 0),
                "taxa_sucesso_media": stats.get("taxa_sucesso_media", 0),
            },
            "memory": cont,
            "provider": getattr(settings, "ai_provider", ""),
            "model": getattr(settings, "openai_model", "") or "",
            "voice": getattr(settings, "tts_voice", ""),
        }

    def aprender_interacao(self, comando: str, intent: str, parametros: dict, resposta: str, sucesso: bool = True) -> None:
        if not getattr(settings, "enable_continuous_learning", True):
            return
        try:
            if intent and intent != "conversa":
                aprendizado.aprender(comando, intent, parametros or {})
            aprendizado.registrar_feedback(comando, positivo=sucesso)
        except Exception as e:
            log.debug("Falha ao registrar aprendizado: %s", e)

    def registrar_identidade(self, nome: str | None) -> None:
        if nome:
            self.last_identity = nome
            try:
                db_memoria.salvar_perfil("ultima_pessoa_reconhecida", nome)
            except Exception:
                pass


nucleo = NucleoInteligencia()
