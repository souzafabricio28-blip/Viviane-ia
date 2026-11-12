from __future__ import annotations

import logging
import re
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from core.memoria import memoria as db_memoria

log = logging.getLogger("Viviane")

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}

_TIMEOUT = 15


_base = None


def _base_conhecimento():
    global _base
    if _base is None:
        from core.conhecimento import BaseConhecimento
        _base = BaseConhecimento()
    return _base


def guardar_resultados(query: str, resultados: list[dict]) -> int:
    """Grava cada resultado com texto útil na base de conhecimento (sem duplicar)."""
    base = _base_conhecimento()
    salvos = 0
    for r in resultados:
        titulo = (r.get("title") or "").strip()
        corpo = (r.get("body") or "").strip()
        if not titulo or len(corpo) < 30:
            continue
        try:
            base.adicionar(
                titulo=titulo[:200],
                conteudo=corpo[:800],
                bloco_nome="Web",
                tags=query.strip()[:120],
                fonte=(r.get("href") or "")[:300],
            )
            salvos += 1
        except Exception as e:
            log.warning("Erro ao guardar conhecimento web: %s", e)
    return salvos


def _variantes(query: str) -> list[str]:
    """A frase inteira e uma versão só com as palavras-chave (frase longa costuma não achar nada)."""
    from core.conhecimento import BaseConhecimento

    query = (query or "").strip()
    simples = " ".join(dict.fromkeys(BaseConhecimento.palavras_chave(query)))[:90]
    variantes = [query]
    if simples and simples.lower() != query.lower():
        variantes.append(simples)
    return variantes


def _pesquisar_ddgs(query: str, num_resultados: int) -> list[dict]:
    try:
        from ddgs import DDGS
    except ImportError:
        return []

    for regiao in ("br-pt", None):
        try:
            ddgs = DDGS()
            if regiao:
                brutos = list(ddgs.text(query, region=regiao, max_results=num_resultados))
            else:
                brutos = list(ddgs.text(query, max_results=num_resultados))
        except Exception as e:
            log.info("ddgs sem resultado (%s, %s): %s", query[:40], regiao, e)
            continue
        resultados = [
            {"title": r.get("title", ""), "body": r.get("body", ""), "href": r.get("href", "")}
            for r in brutos
        ]
        if resultados:
            return resultados
    return []


def _pesquisar_wikipedia(query: str, num_resultados: int = 3) -> list[dict]:
    """Último recurso, sem chave de API: resumo introdutório da Wikipédia em português."""
    try:
        resp = requests.get(
            "https://pt.wikipedia.org/w/api.php",
            params={
                "action": "query", "generator": "search", "gsrsearch": query,
                "gsrlimit": num_resultados, "prop": "extracts|info", "inprop": "url",
                "exintro": 1, "explaintext": 1, "exchars": 900,
                "format": "json", "utf8": 1,
            },
            headers=_HEADERS,
            timeout=_TIMEOUT,
        )
        paginas = (resp.json().get("query") or {}).get("pages") or {}
        ordenadas = sorted(paginas.values(), key=lambda p: p.get("index", 99))
        return [
            {
                "title": f"{p.get('title', '')} – Wikipédia",
                "body": (p.get("extract") or "").strip(),
                "href": p.get("fullurl", ""),
            }
            for p in ordenadas
            if (p.get("extract") or "").strip()
        ]
    except Exception as e:
        log.warning("Erro na Wikipédia: %s", e)
        return []


def pesquisar_web(query: str, num_resultados: int = 5) -> list[dict]:
    """Pesquisa na internet e devolve [{title, body, href}]. Lista vazia se tudo falhar."""
    variantes = _variantes(query)
    for q in variantes:
        resultados = _pesquisar_ddgs(q, num_resultados) or _pesquisar_lite(q, num_resultados)
        if resultados:
            return resultados
    for q in variantes:
        resultados = _pesquisar_wikipedia(q, 3)
        if resultados:
            return resultados
    return []


def _pesquisar_lite(query: str, num_resultados: int = 5) -> list[dict]:
    try:
        resp = requests.get(
            "https://lite.duckduckgo.com/lite/",
            params={"q": query},
            headers=_HEADERS,
            timeout=_TIMEOUT,
        )
        soup = BeautifulSoup(resp.text, "lxml")
        links = soup.find_all("a", class_="result-link")
        snippets = soup.find_all("td", class_="result-snippet")
        resultados = []
        for i, a in enumerate(links[:num_resultados]):
            corpo = snippets[i].get_text(" ", strip=True) if i < len(snippets) else ""
            resultados.append({
                "title": a.get_text(strip=True),
                "body": corpo,
                "href": a.get("href", ""),
            })
        return resultados
    except Exception as e:
        log.warning("Erro no fallback web: %s", e)
        return []


def formatar_resultados(query: str, resultados: list[dict]) -> str:
    linhas = [f"Resultados da pesquisa sobre '{query}':"]
    for r in resultados:
        titulo = (r.get("title") or "").strip()
        if not titulo:
            continue
        linhas.append(f"\n- {titulo}")
        corpo = (r.get("body") or "").strip()
        if corpo:
            linhas.append(f"  {corpo[:300]}")
        if r.get("href"):
            linhas.append(f"  ({r['href']})")
    return "\n".join(linhas)


def buscar_web(query: str, num_resultados: int = 5) -> str:
    resultados = pesquisar_web(query, num_resultados)
    if not resultados:
        return "Não encontrei resultados para sua pesquisa."
    guardar_resultados(query, resultados)
    texto = formatar_resultados(query, resultados)
    db_memoria.registrar_comando("web_search", query, texto[:300])
    return texto


def buscar_web_fallback(query: str, num_resultados: int = 5) -> str:
    resultados = _pesquisar_lite(query, num_resultados)
    if not resultados:
        return "Não encontrei resultados para sua pesquisa."
    guardar_resultados(query, resultados)
    return formatar_resultados(query, resultados)


def fetch_page(url: str) -> str:
    try:
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        resp.encoding = resp.apparent_encoding or "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        texto = soup.get_text(separator=" ", strip=True)
        texto = re.sub(r"\s+", " ", texto).strip()

        linhas = [l.strip() for l in texto.split(". ") if len(l.strip()) > 40]
        conteudo = ". ".join(linhas[:20])

        if not conteudo:
            conteudo = texto[:2000]

        titulo_pagina = soup.title.string.strip() if soup.title and soup.title.string else url
        guardar_resultados(titulo_pagina, [{"title": titulo_pagina, "body": conteudo[:800], "href": url}])

        db_memoria.registrar_comando("web_fetch", url, conteudo[:200])
        return conteudo[:3000]

    except requests.ConnectionError:
        return "Não consegui acessar a página. Verifique a conexão."
    except Exception as e:
        log.warning(f"Erro ao acessar página: {e}")
        return f"Erro ao acessar: {str(e)[:80]}"


def buscar_e_aprender(query: str, profundidade: int = 3) -> str:
    return buscar_web(query, num_resultados=profundidade)
