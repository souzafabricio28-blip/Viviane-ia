from __future__ import annotations

import json
import logging
import time
from abc import ABC, abstractmethod
from typing import Any

import requests

from core.settings import settings

log = logging.getLogger("Viviane")

_MEMORIAS_CACHE: str | None = None


def _memorias_msg() -> str:
    global _MEMORIAS_CACHE
    from core.memoria import memoria as db_memoria
    ctx = db_memoria.contexto_para_ia(limite_conversas=0, limite_memorias=15)
    result = "[MEMORIAS]\n" + ctx if ctx.strip() else ""
    return result


class AIProvider(ABC):
    @abstractmethod
    def completar(self, prompt: str, temperatura: float = 0.3) -> str: ...

    @abstractmethod
    def historico(
        self, texto: str, memoria: list[dict[str, str]], persona: str
    ) -> str: ...

    def health_check(self) -> bool:
        """Verifica se o provedor está saudável."""
        try:
            result = self.completar('{"test": true}', temperatura=0.1)
            return bool(result and "intent" in result)
        except Exception:
            return False


class GroqProvider(AIProvider):
    def __init__(self) -> None:
        from groq import Groq
        self._cliente = Groq(api_key=settings.groq_api_key)
        self._modelo = "allam-2-7b"

    def completar(self, prompt: str, temperatura: float = 0.3) -> str:
        try:
            resposta = self._cliente.chat.completions.create(
                model=self._modelo,
                messages=[
                    {"role": "system", "content": "Você é um classificador de intenções. Responda APENAS com JSON puro: {\"intent\": \"nome_exato\", \"parametros\": {}}. Use EXATAMENTE estes nomes de intent: abrir_programa, buscar_web, fetch_page, previsao_tempo, noticias, lembrete, tocar_musica, comando_sistema, executar_cmd, diagnostico, ip_local, ip_publico, info_disco, info_so, info_processos, info_servicos, info_rede, configuracao, analisar_ecra, gerar_imagem, salvar_conhecimento, buscar_conhecimento, listar_conhecimento, audio_devices, capturar_webcam, gravar_tela, tirar_print, listar_janelas, alternar_janela, fechar_janela, listar_sessoes_audio, volume_app, programas_abertos, listar_servicos_windows, controle_servico, ler_registro, volume_total, info_hardware, matar_processo, verificar_programa, smarthome_dispositivos, smarthome_ligar, smarthome_desligar, smarthome_brilho, smarthome_temperatura, smarthome_cena, ajuda, sugestao_proativa, conversa. NUNCA invente nomes. Se não reconhecer, use 'conversa'. Sem markdown, sem explicações."},
                    {"role": "user", "content": prompt},
                ],
                temperature=temperatura,
                max_tokens=300,
            )
            return resposta.choices[0].message.content or ""
        except Exception as e:
            log.warning("Groq API error: %s", e)
            raise

    def historico(
        self, texto: str, memoria: list[dict[str, str]], persona: str
    ) -> str:
        messages = [{"role": "system", "content": persona}]
        for item in memoria:
            messages.append({"role": "user", "content": item["u"]})
            messages.append({"role": "assistant", "content": item["d"]})
        mem = _memorias_msg()
        if mem:
            messages.append({"role": "system", "content": mem})
        messages.append({"role": "user", "content": texto})
        resposta = self._cliente.chat.completions.create(
            model=self._modelo,
            messages=messages,
            temperature=0.9,
            max_tokens=400,
        )
        return resposta.choices[0].message.content or ""


class GeminiProvider(AIProvider):
    def __init__(self) -> None:
        from google import genai
        from google.genai import types
        self._cliente = genai.Client(api_key=settings.gemini_api_key)
        self._modelo = "gemini-2.0-flash"
        self._types = types

    def completar(self, prompt: str, temperatura: float = 0.7) -> str:
        try:
            resposta = self._cliente.models.generate_content(
                model=self._modelo,
                contents=prompt,
                config=self._types.GenerateContentConfig(
                    temperature=temperatura,
                    max_output_tokens=256,
                    response_mime_type="application/json",
                ),
            )
            return resposta.text or ""
        except Exception as e:
            log.warning("Gemini API error: %s", e)
            raise

    def historico(
        self, texto: str, memoria: list[dict[str, str]], persona: str
    ) -> str:
        contents: list[Any] = []
        for item in memoria:
            contents.append(
                self._types.Content(role="user", parts=[self._types.Part.from_text(text=item["u"])])
            )
            contents.append(
                self._types.Content(role="model", parts=[self._types.Part.from_text(text=item["d"])])
            )
        mem = _memorias_msg()
        if mem:
            contents.append(
                self._types.Content(role="user", parts=[self._types.Part.from_text(text=mem)])
            )
        contents.append(
            self._types.Content(role="user", parts=[self._types.Part.from_text(text=texto)])
        )
        resposta = self._cliente.models.generate_content(
            model=self._modelo,
            contents=contents,
            config=self._types.GenerateContentConfig(
                system_instruction=persona,
                temperature=0.7,
                max_output_tokens=512,
            ),
        )
        return resposta.text or ""


class OllamaProvider(AIProvider):
    def __init__(self) -> None:
        self._url = settings.ollama_url
        self._modelo = settings.ollama_model

    def completar(self, prompt: str, temperatura: float = 0.7) -> str:
        try:
            resp = requests.post(
                f"{self._url}/api/chat",
                json={
                    "model": self._modelo,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "options": {"temperature": temperatura, "num_predict": 256},
                    "format": "json",
                },
                timeout=30,
            )
            data = resp.json()
            return data.get("message", {}).get("content", "") or ""
        except requests.ConnectionError:
            raise ConnectionError("Ollama não está rodando")
        except Exception as e:
            raise RuntimeError(f"Erro no Ollama: {e}")

    def historico(
        self, texto: str, memoria: list[dict[str, str]], persona: str
    ) -> str:
        messages = [{"role": "system", "content": persona}]
        for item in memoria:
            messages.append({"role": "user", "content": item["u"]})
            messages.append({"role": "assistant", "content": item["d"]})
        mem = _memorias_msg()
        if mem:
            messages.append({"role": "system", "content": mem})
        messages.append({"role": "user", "content": texto})
        try:
            resp = requests.post(
                f"{self._url}/api/chat",
                json={
                    "model": self._modelo,
                    "messages": messages,
                    "stream": False,
                    "options": {"temperature": 0.7, "num_predict": 512},
                },
                timeout=60,
            )
            data = resp.json()
            return data.get("message", {}).get("content", "") or ""
        except requests.ConnectionError:
            raise ConnectionError("Ollama não está rodando")
        except Exception as e:
            raise RuntimeError(f"Erro no Ollama: {e}")


class OpenAICompatProvider(AIProvider):
    def __init__(self) -> None:
        self._base_url = (settings.openai_base_url or "http://localhost:20128/v1").rstrip("/")
        self._api_key = settings.openai_api_key
        self._modelo = settings.openai_model or ""

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    def _resolver_modelo(self) -> str:
        if self._modelo:
            return self._modelo
        try:
            resp = requests.get(
                f"{self._base_url}/models",
                headers=self._headers(),
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json() or {}
            items = data.get("data") or []
            if items and isinstance(items, list):
                first = items[0] or {}
                model_id = first.get("id") or first.get("name")
                if model_id:
                    self._modelo = str(model_id)
                    return self._modelo
        except Exception as e:
            log.warning("OpenAI-compatible: falha ao listar modelos (%s): %s", self._base_url, e)
        self._modelo = "gpt-3.5-turbo"
        return self._modelo

    def _chat(self, messages: list[dict[str, str]], temperature: float, max_tokens: int) -> str:
        model = self._resolver_modelo()
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        resp = requests.post(
            f"{self._base_url}/chat/completions",
            headers=self._headers(),
            json=payload,
            timeout=90,
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:300]}")
        data = resp.json() or {}
        choices = data.get("choices") or []
        if not choices:
            return ""
        msg = (choices[0] or {}).get("message") or {}
        content = msg.get("content")
        if isinstance(content, list):
            parts = []
            for part in content:
                if isinstance(part, dict):
                    parts.append(str(part.get("text") or part.get("content") or ""))
                else:
                    parts.append(str(part))
            return "".join(parts).strip()
        return (content or "").strip()

    def completar(self, prompt: str, temperatura: float = 0.3) -> str:
        try:
            return self._chat(
                [
                    {"role": "system", "content": "Você é um classificador de intenções. Responda APENAS com JSON puro: {\"intent\": \"nome_exato\", \"parametros\": {}}. Use EXATAMENTE estes nomes de intent: abrir_programa, buscar_web, fetch_page, previsao_tempo, noticias, lembrete, tocar_musica, comando_sistema, executar_cmd, diagnostico, ip_local, ip_publico, info_disco, info_so, info_processos, info_servicos, info_rede, configuracao, analisar_ecra, gerar_imagem, salvar_conhecimento, buscar_conhecimento, listar_conhecimento, audio_devices, capturar_webcam, gravar_tela, tirar_print, listar_janelas, alternar_janela, fechar_janela, listar_sessoes_audio, volume_app, programas_abertos, listar_servicos_windows, controle_servico, ler_registro, volume_total, info_hardware, matar_processo, verificar_programa, smarthome_dispositivos, smarthome_ligar, smarthome_desligar, smarthome_brilho, smarthome_temperatura, smarthome_cena, ajuda, sugestao_proativa, conversa. NUNCA invente nomes. Se não reconhecer, use 'conversa'. Sem markdown, sem explicações."},
                    {"role": "user", "content": prompt},
                ],
                temperature=temperatura,
                max_tokens=300,
            )
        except Exception as e:
            log.warning("OpenAI-compatible API error (%s): %s", self._base_url, e)
            raise

    def historico(
        self, texto: str, memoria: list[dict[str, str]], persona: str
    ) -> str:
        messages = [{"role": "system", "content": persona}]
        for item in memoria:
            messages.append({"role": "user", "content": item["u"]})
            messages.append({"role": "assistant", "content": item["d"]})
        mem = _memorias_msg()
        if mem:
            messages.append({"role": "system", "content": mem})
        messages.append({"role": "user", "content": texto})
        try:
            return self._chat(messages, temperature=0.9, max_tokens=512)
        except Exception as e:
            log.warning("OpenAI-compatible API error (%s): %s", self._base_url, e)
            raise


class FallbackProvider(AIProvider):
    """Provedor com fallback automático entre múltiplos provedores."""

    def __init__(self, providers: list[AIProvider] | None = None):
        self._providers = providers or []
        self._current_idx = 0
        self._last_failure: dict[str, float] = {}
        self._cooldown_seconds = 30

    def add_provider(self, provider: AIProvider):
        self._providers.append(provider)

    def _get_available_providers(self) -> list[AIProvider]:
        now = time.time()
        available = []
        for i, p in enumerate(self._providers):
            last_fail = self._last_failure.get(str(i), 0)
            if now - last_fail > self._cooldown_seconds:
                available.append(p)
            else:
                log.debug(f"Provider {i} em cooldown ({now - last_fail:.0f}s)")
        return available

    def _mark_failure(self, idx: int):
        self._last_failure[str(idx)] = time.time()
        log.warning(f"Provider {idx} falhou, cooldown de {self._cooldown_seconds}s")

    def _try_providers(self, method_name: str, *args, **kwargs) -> str:
        available = self._get_available_providers()
        if not available:
            log.error("Todos os provedores em cooldown, tentando o primeiro mesmo assim")
            available = self._providers

        last_error = None
        for i, provider in enumerate(available):
            try:
                method = getattr(provider, method_name)
                result = method(*args, **kwargs)
                if result and result.strip():
                    if i != self._current_idx:
                        log.info(f"Fallback para provider {i} ({type(provider).__name__})")
                        self._current_idx = i
                    return result
                else:
                    last_error = RuntimeError("Resposta vazia do provedor")
            except Exception as e:
                last_error = e
                original_idx = self._providers.index(provider) if provider in self._providers else i
                self._mark_failure(original_idx)
                log.warning(f"Provider {original_idx} ({type(provider).__name__}) falhou: {e}")
                continue

        if last_error:
            log.error(f"Todos os provedores falharam. Último erro: {last_error}")
        else:
            log.error("Todos os provedores retornaram resposta vazia")
        return '{"intent": "conversa", "parametros": {}, "resposta": "Desculpe, todos os provedores de IA estão indisponíveis no momento."}'

    def completar(self, prompt: str, temperatura: float = 0.3) -> str:
        return self._try_providers("completar", prompt, temperatura)

    def historico(
        self, texto: str, memoria: list[dict[str, str]], persona: str
    ) -> str:
        return self._try_providers("historico", texto, memoria, persona)

    def health_check_all(self) -> dict[str, bool]:
        results = {}
        for i, p in enumerate(self._providers):
            try:
                results[f"{i}_{type(p).__name__}"] = p.health_check()
            except Exception:
                results[f"{i}_{type(p).__name__}"] = False
        return results


_PROVIDERS: dict[str, type[AIProvider]] = {
    "groq": GroqProvider,
    "gemini": GeminiProvider,
    "ollama": OllamaProvider,
    "openai": OpenAICompatProvider,
    "openai_compat": OpenAICompatProvider,
    "custom": OpenAICompatProvider,
    "local": OpenAICompatProvider,
}


def criar_provedor(provider: str | None = None) -> AIProvider:
    nome = (provider or settings.ai_provider).lower()

    if nome == "fallback" or nome == "auto":
        providers = []
        # Endpoint OpenAI-compatible local/custom tem prioridade quando configurado
        if settings.openai_base_url:
            providers.append(OpenAICompatProvider())
        if settings.groq_api_key:
            providers.append(GroqProvider())
        if settings.gemini_api_key:
            providers.append(GeminiProvider())
        # Ollama não precisa de chave, tenta conectar
        try:
            ollama = OllamaProvider()
            if ollama.health_check():
                providers.append(ollama)
        except Exception:
            pass

        if not providers:
            log.warning("Nenhum provedor configurado para fallback, usando Groq")
            return GroqProvider()

        log.info(f"FallbackProvider iniciado com {len(providers)} provedores: {[type(p).__name__ for p in providers]}")
        return FallbackProvider(providers)

    classe = _PROVIDERS.get(nome)
    if not classe:
        log.warning(f"Provider desconhecido '{nome}', usando GroqProvider")
        return GroqProvider()
    return classe()
