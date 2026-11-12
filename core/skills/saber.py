"""Responder perguntas: base local primeiro, internet se não souber, e guarda o que achou."""

from __future__ import annotations

import logging
from typing import Callable

from core.skills.web_search import (
    formatar_resultados,
    guardar_resultados,
    pesquisar_web,
)

log = logging.getLogger("Viviane")

_ERROS_LLM = ("problema de comunicação", "Erro:")


def _resumir(cerebro, pergunta: str, rotulo: str, material: str) -> str:
    """Pede ao modelo uma resposta natural a partir do material. Vazio se falhar."""
    if cerebro is None:
        return ""
    try:
        resposta = cerebro.processar(
            f"{pergunta}\n\n[{rotulo}]\n{material[:1800]}\n"
            "Responda em português, curto e direto, usando apenas essas informações."
        )
    except Exception as exc:
        log.warning("Resumo falhou: %s", exc)
        return ""
    resposta = (resposta or "").strip()
    if not resposta or any(e in resposta for e in _ERROS_LLM):
        return ""
    return resposta


def _material_base(itens: list[dict]) -> str:
    return "\n".join(f"- {i['titulo']}: {i['conteudo'][:400]}" for i in itens)


def saber(
    pergunta: str,
    conhecimento,
    cerebro=None,
    falar: Callable[[str], None] | None = None,
    *,
    termo: str | None = None,
) -> str:
    termo = (termo or pergunta).strip()

    itens = conhecimento.buscar(termo, limite=3)
    if itens:
        material = _material_base(itens)
        resumo = _resumir(cerebro, pergunta, "CONHECIMENTO GUARDADO", material)
        return resumo or f"Eu já sabia isso: {itens[0]['titulo']}. {itens[0]['conteudo'][:400]}"

    if falar:
        falar("Não tenho isso guardado, vou pesquisar na internet.")
    return pesquisar_e_resumir(pergunta, cerebro, termo=termo, prefixo_sem_resultado=(
        f"Não achei nada sobre {termo} na minha base e "
    ))


def pesquisar_e_resumir(
    pergunta: str,
    cerebro=None,
    *,
    termo: str | None = None,
    prefixo_sem_resultado: str = "",
) -> str:
    """Pesquisa na internet, guarda na base e devolve um resumo em linguagem natural."""
    termo = (termo or pergunta).strip()
    resultados = pesquisar_web(termo, num_resultados=5)
    if not resultados:
        if prefixo_sem_resultado:
            return (
                f"{prefixo_sem_resultado}a pesquisa na internet não trouxe resultados. "
                "Verifique a conexão e tente de novo."
            )
        return (
            f"A pesquisa na internet não trouxe resultados sobre {termo}. "
            "Verifique a conexão e tente de novo."
        )

    guardar_resultados(termo, resultados)
    resumo = _resumir(cerebro, pergunta, "PESQUISA NA INTERNET", formatar_resultados(termo, resultados))
    if resumo:
        return resumo
    primeiro = next((r for r in resultados if (r.get("body") or "").strip()), resultados[0])
    return f"Pesquisei na internet. {primeiro.get('title', '')}: {(primeiro.get('body') or '')[:500]}"
