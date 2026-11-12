"""
Viviane - Assistente local de voz
Provedores: Groq, Gemini, Ollama ou um endpoint na própria máquina.
"""

from __future__ import annotations

import sys

from core.settings import settings


def main() -> None:
    provider = settings.ai_provider

    if provider == "groq" and not settings.groq_api_key:
        print("=" * 60)
        print("  Viviane - Assistente local")
        print("=" * 60)
        print()
        print("  ERRO: Chave da API Groq não configurada!")
        print()
        print("  1. Abra https://console.groq.com/")
        print("  2. Crie uma API Key")
        print("  3. Coloque no .env: GROQ_API_KEY=sua_chave")
        print()
        print("=" * 60)
        sys.exit(1)
    elif provider == "gemini" and not settings.gemini_api_key:
        print("=" * 60)
        print("  ERRO: Chave da API Gemini não configurada!")
        print("=" * 60)
        sys.exit(1)

    from core.assistant import Assistente

    assistente = Assistente()
    print("=" * 60)
    print(f"  {settings.assistant_name} - Modo voz neste computador")
    print("  Fale um comando ou pressione Ctrl+C para sair")
    print("=" * 60)
    try:
        assistente.iniciar()
    except KeyboardInterrupt:
        assistente.parar()


if __name__ == "__main__":
    main()
