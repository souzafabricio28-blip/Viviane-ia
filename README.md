# Viviane IA

Assistente pessoal para Windows. Roda neste computador: janela, voz e automação local. Não há deploy em nuvem neste momento.

## Como abrir
- `run_viviane.bat` ou `python interface_viviane.py` — janela
- `python main.py` — voz no console
- `iniciar.bat` — menu (voz ou janela)

## Configuração
1. Copie `.env.example` para `.env` e preencha as chaves.
2. `pip install -r requirements.txt`
3. Deixe `LOCAL_ONLY=true`. Com isso o endereço de rede, se existir, é ignorado e o processo fica em `127.0.0.1`.

## Variáveis
- `LOCAL_ONLY=true` — trava a Viviane neste PC
- `AI_PROVIDER=groq|gemini|ollama|fallback|auto` — o modelo pode ser remoto; a aplicação em si não abre porta pública
- `GROQ_API_KEY`, `GEMINI_API_KEY`, `REPLICATE_API_KEY`
- `ENABLE_LOCAL_WEB=false` — painel opcional, só em localhost
- `ALLOW_SYSTEM_ACTIONS=true|false` — ações no PC (desligar, processo, registro, comando)

## Arquitetura
- `interface_viviane.py` / `main.py` — entradas
- `core/assistant.py` — escuta, fala e conversa
- `core/actions/` — atalhos e o registro de intenções
- `core/llm/` — provedores e classificação
- `core/routing/` — regras locais em `rules.yaml`
- `core/skills/` — PC, mídia, web, clima, visão, casa
- `core/memoria.py` — SQLite em `data/`
- `ui/web_app.py` — saúde do painel local, desligado por padrão

## Segurança
- Com `ALLOW_SYSTEM_ACTIONS=false`, intenções sensíveis são recusadas.
- Não versionar `.env`, `data/` nem chaves.
