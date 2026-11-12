"""Intents válidos e sanitização de comandos aprendidos."""
from __future__ import annotations

# Intents reconhecidos pelo assistente (brain + handlers extras)
VALID_INTENTS: frozenset[str] = frozenset({
    "abrir_programa",
    "buscar_web",
    "fetch_page",
    "previsao_tempo",
    "noticias",
    "lembrete",
    "tocar_musica",
    "comando_sistema",
    "executar_cmd",
    "diagnostico",
    "ip_local",
    "ip_publico",
    "info_disco",
    "info_so",
    "info_processos",
    "info_servicos",
    "info_rede",
    "configuracao",
    "analisar_ecra",
    "visualizar_ecra",
    "gerar_imagem",
    "salvar_conhecimento",
    "buscar_conhecimento",
    "listar_conhecimento",
    "audio_devices",
    "capturar_webcam",
    "gravar_tela",
    "tirar_print",
    "listar_janelas",
    "alternar_janela",
    "fechar_janela",
    "listar_sessoes_audio",
    "volume_app",
    "programas_abertos",
    "listar_servicos_windows",
    "controle_servico",
    "ler_registro",
    "volume_total",
    "info_hardware",
    "matar_processo",
    "verificar_programa",
    "abrir_pasta",
    "smarthome_dispositivos",
    "smarthome_ligar",
    "smarthome_desligar",
    "smarthome_brilho",
    "smarthome_temperatura",
    "smarthome_cena",
    "parar_fala",
    "desligar_assistente",
    "db_status",
    "conversa",
})

# Aliases gravados pela IA que devem ser corrigidos
INTENT_ALIASES: dict[str, str] = {
    "pesquisar_web": "buscar_web",
    "criar_imagem": "gerar_imagem",
    "visualizar_ecra": "analisar_ecra",
}

# Chaves muito curtas ou ruído de transcrição — nunca aprender
_CHAVES_IGNORAR: frozenset[str] = frozenset({
    "", ".", "c", "sim", "oi", "porque", "pare", "darkson", "realista", "digital",
    "cartoon", "anime", "aquarela", "fotografia", "cyberpunk", "fantasia",
    "steampunk", "mangá", "manga", "medieval", "gótico", "gótico", "sci-fi",
    "minimalista", "surrealista", "expressionista", "impressionista",
    "pintura a óleo", "digital art", "desenho animado", "cinematográfico",
    "pixel art", "3d render", "esboço a lápis", "carvão", "arte vetorial",
    "retro vintage", "pop art", "arte urbana (grafitti)", "low poly", "isométrico",
})


def intent_valido(intent: str) -> bool:
    return intent in VALID_INTENTS


def normalizar_intent(intent: str, parametros: dict) -> tuple[str, dict] | None:
    """Corrige alias e parâmetros. Retorna None se intent inválido."""
    intent = INTENT_ALIASES.get(intent, intent)
    if not intent_valido(intent):
        return None

    params = dict(parametros or {})

    if intent == "buscar_web":
        if "pesquisa" in params and "termo" not in params:
            params["termo"] = params.pop("pesquisa")

    if intent == "gerar_imagem":
        for chave in ("descricao", "objeto"):
            if chave in params and "prompt" not in params:
                params["prompt"] = params[chave]
                break

    return intent, params


def chave_aprendivel(comando: str) -> bool:
    c = comando.lower().strip()
    if c in _CHAVES_IGNORAR:
        return False
    if len(c) < 4:
        return False
    return True


def sanitizar_comandos(dados: dict) -> dict[str, dict]:
    """Remove entradas inválidas e normaliza as restantes."""
    limpo: dict[str, dict] = {}
    for comando, info in dados.items():
        if not isinstance(info, dict):
            continue
        chave = comando.lower().strip()
        if not chave_aprendivel(chave):
            continue
        intent = info.get("intent", "")
        params = info.get("parametros", {})
        norm = normalizar_intent(intent, params)
        if norm is None:
            continue
        intent_ok, params_ok = norm
        limpo[chave] = {"intent": intent_ok, "parametros": params_ok}
    return limpo
