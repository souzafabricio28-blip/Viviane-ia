from __future__ import annotations

import time
from urllib.parse import quote

import requests

from core.conversa import registrar
from core.settings import settings
from core.voice import falar

_CACHE: dict[str, tuple[list[str], float]] = {}
_CACHE_TTL = 600


class Noticias:
    def __init__(self) -> None:
        self.api_key = settings.news_api_key
        self._sessao = requests.Session()

    def obter_noticias(self, assunto: str = "") -> str:
        if not self.api_key:
            msg = "Notícias não disponíveis. Configure NEWS_API_KEY no .env"
            falar(msg)
            return msg

        chave_cache = assunto.lower().strip() if assunto else "principais"
        agora = time.time()

        if chave_cache in _CACHE:
            titulos, timestamp = _CACHE[chave_cache]
            if agora - timestamp < _CACHE_TTL:
                return self._ler_titulos(titulos, assunto)

        try:
            params = {
                "country": "br",
                "apiKey": self.api_key,
                "pageSize": 5,
                "language": "pt",
            }
            if assunto:
                params["q"] = assunto
                falar(f"A procurar notícias sobre {assunto}...")
            else:
                falar("A procurar os destaques de hoje...")

            resp = self._sessao.get(
                "https://newsapi.org/v2/top-headlines",
                params=params,
                timeout=4,
            )
            dados = resp.json()

            if resp.status_code == 401:
                msg = "Chave da API de notícias inválida"
                falar(msg)
                return msg
            if dados.get("status") != "ok":
                msg = "Serviço de notícias indisponível no momento"
                falar(msg)
                return msg

            artigos = dados.get("articles", [])
            if not artigos:
                msg = f"Não encontrei notícias sobre {assunto}" if assunto else "Não encontrei notícias no momento"
                falar(msg)
                return msg

            titulos = []
            for a in artigos[:3]:
                fonte = a["source"].get("name", "") if a.get("source") else ""
                titulo = a["title"] or ""
                if fonte and fonte.lower() not in titulo.lower():
                    titulos.append(f"{titulo} - {fonte}")
                else:
                    titulos.append(titulo)

            _CACHE[chave_cache] = (titulos, time.time())
            return self._ler_titulos(titulos, assunto)

        except requests.ConnectionError:
            msg = "Sem conexão com a internet para obter as notícias"
            falar(msg)
            return msg
        except requests.Timeout:
            msg = "O serviço de notícias demorou muito para responder"
            falar(msg)
            return msg
        except requests.RequestException as exc:
            msg = f"Erro ao obter notícias: {str(exc)[:60]}"
            falar(msg)
            return msg

    def _ler_titulos(self, titulos: list[str], assunto: str) -> str:
        if assunto:
            cabecalho = f"Aqui estão as notícias sobre {assunto}"
        else:
            cabecalho = "Aqui estão as principais notícias"

        texto_todos = ". ".join(titulos)
        registrar("assistente", f"[Notícias] {texto_todos}")
        falar(cabecalho)
        falar(texto_todos)
        falar("Estas foram as principais notícias.")
        return f"{cabecalho}. {texto_todos}."
