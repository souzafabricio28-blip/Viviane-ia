"""Contexto passado aos handlers. O assistente preenche; as ações não conhecem a UI."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class ActionContext:
    intent: str
    comando: str
    params: dict = field(default_factory=dict)
    falar: Callable[[str], None] = lambda _texto: None
    pc: Any = None
    lembretes: Any = None
    clima: Any = None
    noticias: Any = None
    diagnostico: Any = None
    info_sistema: Any = None
    conhecimento: Any = None
    voz: Any = None
    cerebro: Any = None
    status_db: Callable[[], str] = lambda: ""
    encerrar: Callable[[], None] = lambda: None
