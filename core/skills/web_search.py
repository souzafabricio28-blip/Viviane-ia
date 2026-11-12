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


def _salvar_conhecimento(titulo: str, conteudo: str, bloco: str = "Web") -> None:
    try:
        db_memoria.salvar_memoria(
            titulo=titulo[:200],
            conteudo=conteudo[:1000],
            tipo="facto",
            tags=bloco,
            importancia=2,
            fonte="web_search",
        )
    except Exception as e:
        log.warning(f"Erro ao salvar conhecimento web: {e}")


def buscar_web(query: str, num_resultados: int = 5) -> str:
    from ddgs import DDGS

    try:
        ddgs = DDGS()
        resultados = list(ddgs.text(query, max_results=num_resultados))

        if not resultados:
            return "Não encontrei resultados para sua pesquisa."

        linhas = [f"Resultados da pesquisa sobre '{query}':"]
        for r in resultados:
            titulo = r.get("title", "").strip()
            body = r.get("body", "").strip()
            href = r.get("href", "")
            if titulo:
                linhas.append(f"\n- {titulo}")
                if body:
                    linhas.append(f"  {body[:200]}")
                if href:
                    linhas.append(f"  ({href})")

                _salvar_conhecimento(titulo, body[:500], "Web")

        db_memoria.registrar_comando("web_search", query, str(linhas[:3]))
        return "\n".join(linhas)

    except ImportError:
        return buscar_web_fallback(query, num_resultados)
    except Exception as e:
        log.warning(f"Erro na pesquisa web: {e}")
        return f"Erro ao pesquisar: {str(e)[:80]}"


def buscar_web_fallback(query: str, num_resultados: int = 5) -> str:
    try:
        resp = requests.get(
            "https://lite.duckduckgo.com/lite/",
            params={"q": query},
            headers=_HEADERS,
            timeout=_TIMEOUT,
        )
        soup = BeautifulSoup(resp.text, "lxml")
        resultados = soup.find_all("a", class_="result-link")
        if not resultados:
            links = soup.select('a[href*="://"]')
            resultados = [l for l in links if l.get_text(strip=True)][:num_resultados]

        if not resultados:
            return "Não encontrei resultados para sua pesquisa."

        linhas = [f"Resultados da pesquisa sobre '{query}':"]
        for r in resultados[:num_resultados]:
            texto = r.get_text(strip=True)
            href = r.get("href", "")
            if texto:
                linhas.append(f"- {texto}")
                if href and href.startswith("http"):
                    linhas.append(f"  ({href})")
                _salvar_conhecimento(texto, href, "Web")

        db_memoria.registrar_comando("web_search", query, str(linhas[:3]))
        return "\n".join(linhas)

    except Exception as e:
        log.warning(f"Erro no fallback web: {e}")
        return f"Não foi possível pesquisar: {str(e)[:80]}"


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
        _salvar_conhecimento(titulo_pagina, conteudo[:500], "Web")

        db_memoria.registrar_comando("web_fetch", url, conteudo[:200])
        return conteudo[:3000]

    except requests.ConnectionError:
        return "Não consegui acessar a página. Verifique a conexão."
    except Exception as e:
        log.warning(f"Erro ao acessar página: {e}")
        return f"Erro ao acessar: {str(e)[:80]}"


def buscar_e_aprender(query: str, profundidade: int = 3) -> str:
    resultado = buscar_web(query, num_resultados=profundidade)
    _aprender_resultados(query)
    return resultado


def _aprender_resultados(query: str) -> None:
    try:
        from ddgs import DDGS
        ddgs = DDGS()
        resultados = list(ddgs.text(query, max_results=5))
        for r in resultados:
            titulo = r.get("title", "").strip()
            body = r.get("body", "").strip()
            href = r.get("href", "")
            if titulo and body:
                db_memoria.salvar_memoria(
                    titulo=f"Web: {titulo[:180]}",
                    conteudo=f"Fonte: {href}\nResumo: {body[:500]}",
                    tipo="facto",
                    tags="Web, Aprendizado",
                    importancia=1,
                    fonte="web_learn",
                )
                log.info(f"Aprendido da web: {titulo[:60]}")
    except Exception as e:
        log.warning(f"Erro ao aprender da web: {e}")
