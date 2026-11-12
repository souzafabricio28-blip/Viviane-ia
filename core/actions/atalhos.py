"""Comandos resolvidos na máquina, sem chamar o modelo."""

from __future__ import annotations

import random
import re
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Atalho:
    texto: str
    encerrar: bool = False
    registrar: bool = True
    falar: bool = True


_FRASES_PARAR = (
    "pare de falar", "para de falar", "cala a boca", "cale a boca", "silêncio", "silencio",
    "silenciar", "chega de falar", "fica quieta", "fique quieta", "pode parar de falar",
)
_PALAVRAS_PARAR = frozenset({
    "pare", "para", "parar", "stop", "chega", "quieta", "calada", "cala", "cale", "cale-se",
    "psiu", "shh", "xiu",
})
_PALAVRAS_NEUTRAS = frozenset({
    "viviane", "ai", "aí", "agora", "por", "favor", "pode", "já", "ja", "ok", "aqui", "mesmo",
    "de", "falar", "a", "fala", "tudo", "isso",
})


def eh_comando_parar(comando: str) -> bool:
    """True para 'pare', 'para de falar', 'viviane pare agora', 'cala a boca'..."""
    cmd = re.sub(r"[^\w\s\-]", " ", (comando or "").lower())
    cmd = re.sub(r"\s+", " ", cmd).strip()
    if not cmd:
        return False
    if any(f in cmd for f in _FRASES_PARAR):
        return True
    palavras = cmd.split()
    return (
        len(palavras) <= 4
        and any(p in _PALAVRAS_PARAR for p in palavras)
        and all(p in _PALAVRAS_PARAR or p in _PALAVRAS_NEUTRAS for p in palavras)
    )


def parar_tudo() -> None:
    from core.voice import parar_fala
    parar_fala()


def resolver_atalho(comando: str) -> Atalho | None:
    cmd = (comando or "").lower().strip()
    if not cmd:
        return None

    if eh_comando_parar(cmd):
        parar_tudo()
        return Atalho("Parei de falar.", registrar=False, falar=False)

    if any(p in cmd for p in ("desligar", "sair", "parar", "dormir", "descansar")):
        if any(p in cmd for p in ("assistente", "viviane", "alexia", "programa", "sistema", "tudo")):
            return Atalho("Desligando.", encerrar=True, registrar=False)

    if "hora" in cmd or "que horas" in cmd:
        hora = datetime.now().strftime("%H:%M")
        return Atalho(f"Agora são exatamente {hora}")

    if any(p in cmd for p in ("data", "que dia", "que dia é")):
        data = datetime.now().strftime("%d de %B de %Y")
        return Atalho(f"Hoje é {data}")

    if "boa noite" in cmd:
        return Atalho("Boa noite")
    if "bom dia" in cmd:
        return Atalho("Bom dia")
    if "boa tarde" in cmd:
        return Atalho("Boa tarde")

    palavras = set(cmd.split())
    if any(p in palavras for p in ("olá", "ola", "oi", "hey", "eai", "fala")) or "e aí" in cmd:
        return Atalho(random.choice(["Fala", "Oi", "Olá", "E aí"]))

    return None
