"""Comandos resolvidos na máquina, sem chamar o modelo."""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Atalho:
    texto: str
    encerrar: bool = False
    registrar: bool = True


def resolver_atalho(comando: str) -> Atalho | None:
    cmd = (comando or "").lower().strip()
    if not cmd:
        return None

    if any(p in cmd for p in ("pare de falar", "cala a boca", "silêncio", "silenciar", "para de falar")):
        from core.voice import parar_fala
        parar_fala()
        return Atalho("Falando parado.", registrar=False)

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
