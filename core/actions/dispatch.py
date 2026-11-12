"""Registro de intenções. Cada ação devolve texto, ou None se for conversa."""

from __future__ import annotations

import logging
import os
import re
import tempfile
from typing import Callable

from core.actions.context import ActionContext
from core.settings import settings

log = logging.getLogger("Viviane.Acoes")

SENSITIVE_INTENTS = frozenset({
    "comando_sistema",
    "executar_cmd",
    "matar_processo",
    "controle_servico",
    "ler_registro",
    "desligar_assistente",
})

Handler = Callable[[ActionContext], str]


def _bloqueio() -> str:
    return "Ação de sistema desativada por configuração (ALLOW_SYSTEM_ACTIONS=false)."


def _abrir_programa(ctx: ActionContext) -> str:
    programa = ctx.params.get("programa", ctx.comando)
    ctx.pc.abrir_programa(programa)
    return f"A abrir {programa}."


def _buscar_web(ctx: ActionContext) -> str:
    from core.skills.saber import pesquisar_e_resumir

    termo = ctx.params.get("termo") or ctx.params.get("query") or ctx.comando
    ctx.falar("Pesquisando na internet.")
    return pesquisar_e_resumir(ctx.comando, ctx.cerebro, termo=termo)


def _fetch_page(ctx: ActionContext) -> str:
    from core.skills.web_search import fetch_page

    url = ctx.params.get("url", ctx.comando)
    ctx.falar(f"A aceder {url}.")
    return fetch_page(url)[:1000]


def _previsao(ctx: ActionContext) -> str:
    cidade = ctx.params.get("cidade") or "São Paulo"
    return ctx.clima.obter_previsao(cidade, falar_resultado=False)


def _noticias(ctx: ActionContext) -> str:
    return ctx.noticias.obter_noticias(ctx.params.get("assunto", ""))


def _lembrete(ctx: ActionContext) -> str:
    texto = ctx.params.get("texto", ctx.comando)
    match = re.search(r"(\d+)\s*(minutos?|min|horas?|h|segundos?|seg|s)", texto, re.IGNORECASE)
    if match:
        valor = int(match.group(1))
        unidade = match.group(2).lower()
        if unidade.startswith("h"):
            minutos = valor * 60
        elif unidade.startswith("s"):
            minutos = max(1, valor // 60)
        else:
            minutos = valor
        texto = re.sub(
            r"\s*(?:em|daqui|após|dentro\s*de)?\s*\d+\s*(?:minutos?|min|horas?|h|segundos?|seg|s)\s*",
            "",
            texto,
            flags=re.IGNORECASE,
        ).strip()
    else:
        minutos = int(ctx.params.get("minutos", 5))
    ctx.lembretes.criar(texto, minutos)
    return f"Lembrete criado para daqui a {minutos} minutos: {texto}."


def _tocar_musica(ctx: ActionContext) -> str:
    ctx.pc.abrir_programa("spotify")
    return "A abrir o Spotify."


def _comando_sistema(ctx: ActionContext) -> str:
    acao = ctx.params.get("acao", "")
    ctx.pc.executar_comando_sistema(acao)
    if acao == "listar processos":
        return ctx.pc.obter_processos()
    return f"{acao} executado."


def _abrir_pasta(ctx: ActionContext) -> str:
    caminho = ctx.params.get("caminho") or ctx.comando
    if ctx.pc.abrir_pasta(caminho):
        return f"Pasta {caminho} aberta."
    return f"Não consegui abrir a pasta {caminho}."


def _diagnostico(ctx: ActionContext) -> str:
    return ctx.diagnostico.relatorio_completo()


def _info(ctx: ActionContext) -> str:
    mapa = {
        "ip_local": ctx.info_sistema.ip_local,
        "ip_publico": ctx.info_sistema.ip_publico,
        "info_disco": ctx.info_sistema.disco,
        "info_so": ctx.info_sistema.sistema_operacional,
        "info_rede": ctx.info_sistema.rede,
    }
    return mapa[ctx.intent]()


def _executar_cmd(ctx: ActionContext) -> str | None:
    cmd = (ctx.params.get("comando") or ctx.comando).strip()
    if not ctx.pc.comando_valido(cmd):
        log.info("executar_cmd ignorado, não é comando: %r", cmd)
        return None
    resultado = ctx.pc.executar_comando(cmd)
    if resultado:
        return f"Comando executado. {resultado[:200]}"
    return "Comando executado."


def _configuracao(ctx: ActionContext) -> str:
    pagina = ctx.params.get("pagina", "")
    ctx.pc.abrir_configuracao(pagina)
    if pagina:
        return f"A abrir configuração de {pagina}."
    return "A abrir configurações."


def _info_processos(ctx: ActionContext) -> str:
    return ctx.pc.obter_processos()


def _info_servicos(ctx: ActionContext) -> str:
    return ctx.pc.obter_servicos()


def _db_status(ctx: ActionContext) -> str:
    return ctx.status_db()


def _parar_fala(_ctx: ActionContext) -> str:
    from core.voice import parar_fala
    parar_fala()
    return "Parei de falar."


def _salvar_conhecimento(ctx: ActionContext) -> str:
    titulo = ctx.params.get("titulo") or ctx.params.get("assunto") or ctx.comando
    conteudo = ctx.params.get("conteudo") or ctx.params.get("descricao") or ""
    bloco = ctx.params.get("bloco") or ctx.params.get("categoria") or "Geral"
    tags = ctx.params.get("tags", "")
    if not conteudo and ctx.voz is not None:
        ctx.falar("Qual a informacao?")
        conteudo = ctx.voz.ouvir_comando() or ""
    if conteudo and len(conteudo) > 10:
        ctx.conhecimento.adicionar(titulo, conteudo, bloco, tags)
        return f"Salvo em {bloco}: {titulo}."
    return "Conteudo muito curto."


def _buscar_conhecimento(ctx: ActionContext) -> str:
    from core.skills.saber import saber

    termo = ctx.params.get("termo") or ctx.params.get("assunto") or ctx.comando
    return saber(ctx.comando, ctx.conhecimento, ctx.cerebro, ctx.falar, termo=termo)


def _listar_conhecimento(ctx: ActionContext) -> str:
    bloco_nome = ctx.params.get("bloco") or ctx.params.get("categoria") or ""
    if bloco_nome:
        items = ctx.conhecimento.listar_por_bloco(bloco_nome)
        if items:
            nomes = [i["titulo"] for i in items[:10]]
            return f"Bloco '{bloco_nome}': " + ", ".join(nomes)
        return f"Bloco '{bloco_nome}' vazio."
    blocos = ctx.conhecimento.listar_blocos()
    if blocos:
        return "Blocos: " + ", ".join(f"{b['nome']}({b['topicos']})" for b in blocos)
    return "Base de conhecimento vazia."


def _audio_devices(_ctx: ActionContext) -> str:
    from core.skills.midia import listar_audio_devices
    return listar_audio_devices()


def _capturar_webcam(ctx: ActionContext) -> str:
    from core.skills.midia import capturar_webcam
    resultado = capturar_webcam()
    ctx.falar(resultado)
    return resultado


def _gravar_tela(ctx: ActionContext) -> str:
    from core.skills.midia import gravar_tela
    nums = re.findall(r"(\d+)", ctx.comando)
    segundos = int(nums[0]) if nums else 5
    resultado = gravar_tela(segundos)
    ctx.falar(resultado)
    return resultado


def _tirar_print(_ctx: ActionContext) -> str:
    from core.skills.pc_control import ControladorPC
    ControladorPC()._capturar_tela()
    return "Print salvo."


def _listar_janelas(ctx: ActionContext) -> str:
    janelas = ctx.pc.listar_janelas()
    if not janelas:
        return "Nenhuma janela aberta."
    return "Janelas abertas:\n" + "\n".join(
        f"{'[ATIVA]' if j['ativa'] else ''} {j['titulo'][:60]}"
        for j in janelas[:15]
    )


def _alternar_janela(ctx: ActionContext) -> str:
    termo = ctx.params.get("termo", ctx.comando)
    if ctx.pc.alternar_para_janela(termo):
        return f"Alternado para {termo}."
    return f"Janela '{termo}' nao encontrada."


def _fechar_janela(ctx: ActionContext) -> str:
    termo = ctx.params.get("termo", ctx.comando)
    if ctx.pc.fechar_janela(termo):
        return f"Janela '{termo}' fechada."
    return f"Janela '{termo}' nao encontrada."


def _listar_sessoes_audio(ctx: ActionContext) -> str:
    sessoes = ctx.pc.listar_sessoes_audio()
    if not sessoes:
        return "Nenhuma sessao de audio ativa."
    return "Sessoes de audio:\n" + "\n".join(
        f"{s['processo']}: volume {s['volume']:.0%}{' (MUTADO)' if s['mutado'] else ''}"
        for s in sessoes[:10]
    )


def _volume_app(ctx: ActionContext) -> str:
    return ctx.pc.volume_app(ctx.params.get("processo", ctx.comando))


def _programas_abertos(ctx: ActionContext) -> str:
    monitores = ctx.pc.programas_por_monitor()
    if not monitores:
        return "Nenhum programa visivel na tela."
    linhas = []
    for mon in monitores:
        if mon["programas"]:
            linhas.append(f"Monitor {mon['monitor']}:")
            linhas.extend(f"  - {p['nome']}" for p in mon["programas"][:10])
    return "\n".join(linhas) if linhas else "Nenhum programa visivel na tela."


def _listar_servicos(ctx: ActionContext) -> str:
    servicos = ctx.pc.listar_servicos_windows()
    if not servicos:
        return "Nenhum servico encontrado."
    return "Servicos do Windows:\n" + "\n".join(
        f"{s['exibicao']} [{s['status']}]" for s in servicos[:15]
    )


def _controle_servico(ctx: ActionContext) -> str:
    return ctx.pc.controle_servico(ctx.params.get("nome", ""), ctx.params.get("acao", "iniciar"))


def _ler_registro(ctx: ActionContext) -> str:
    return ctx.pc.ler_registro(ctx.params.get("chave", ctx.comando))


def _resolver_entity(params: dict, smarthome) -> str:
    entity_id = params.get("entity_id") or params.get("dispositivo", "")
    if entity_id:
        return entity_id
    alvo = (params.get("dispositivo") or "").lower()
    if not alvo:
        return ""
    for dispositivo in smarthome.get_devices():
        if alvo in dispositivo.name.lower():
            return dispositivo.id
    return ""


def _smarthome_dispositivos(ctx: ActionContext) -> str:
    from core.skills.smarthome import smarthome
    tipo = ctx.params.get("tipo", "")
    comodo = ctx.params.get("comodo", "")
    dispositivos = smarthome.get_devices(tipo, comodo)
    if not dispositivos:
        return "Nenhum dispositivo encontrado" + (f" em {comodo}" if comodo else "")
    linhas = [
        f"{d.name} ({d.type}) - {'Ligado' if d.is_on() else 'Desligado'}"
        for d in dispositivos
    ]
    return "Dispositivos:" + (" em " + comodo if comodo else "") + "\n" + "\n".join(linhas)


def _smarthome_ligar(ctx: ActionContext) -> str:
    from core.skills.smarthome import smarthome
    entity_id = _resolver_entity(ctx.params, smarthome)
    if smarthome.turn_on(entity_id, **ctx.params):
        return f"Ligado: {entity_id}"
    return f"Não foi possível ligar {entity_id}"


def _smarthome_desligar(ctx: ActionContext) -> str:
    from core.skills.smarthome import smarthome
    entity_id = _resolver_entity(ctx.params, smarthome)
    if smarthome.turn_off(entity_id):
        return f"Desligado: {entity_id}"
    return f"Não foi possível desligar {entity_id}"


def _smarthome_brilho(ctx: ActionContext) -> str:
    from core.skills.smarthome import smarthome
    entity_id = ctx.params.get("entity_id") or ctx.params.get("dispositivo", "")
    brilho = ctx.params.get("brilho", ctx.params.get("valor", 100))
    if smarthome.set_brightness(entity_id, int(brilho)):
        return f"Brilho ajustado para {brilho}%"
    return f"Não foi possível ajustar brilho de {entity_id}"


def _smarthome_temperatura(ctx: ActionContext) -> str:
    from core.skills.smarthome import smarthome
    entity_id = ctx.params.get("entity_id") or ctx.params.get("dispositivo", "")
    temp = ctx.params.get("temperatura", ctx.params.get("valor", 22))
    if smarthome.set_climate_temp(entity_id, float(temp)):
        return f"Temperatura ajustada para {temp}°C"
    return f"Não foi possível ajustar temperatura de {entity_id}"


def _smarthome_cena(ctx: ActionContext) -> str:
    cena = ctx.params.get("cena", ctx.comando).lower()
    if "cinema" in cena or "filme" in cena:
        return "Modo cinema ativado (configure automação no Home Assistant)"
    if "dormir" in cena or "boa noite" in cena:
        return "Modo dormir ativado (configure automação no Home Assistant)"
    if "manha" in cena or "acordar" in cena:
        return "Modo manhã ativado (configure automação no Home Assistant)"
    return f"Cena '{cena}' não reconhecida. Disponíveis: cinema, dormir, manhã"


def _volume_total(ctx: ActionContext) -> str:
    try:
        from pycaw.pycaw import AudioUtilities
        devices = AudioUtilities.GetSpeakers()
        if hasattr(devices, "EndpointVolume"):
            volume = devices.EndpointVolume
        elif hasattr(devices, "Activate"):
            from ctypes import POINTER, cast
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import IAudioEndpointVolume
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))
        else:
            return "Erro: API de áudio não suportada"
        atual = volume.GetMasterVolumeLevelScalar()
        comando = ctx.comando
        if "aumentar" in comando:
            novo = min(1.0, atual + 0.1)
            volume.SetMasterVolumeLevelScalar(novo, None)
            return f"Volume aumentado para {novo:.0%}"
        if "diminuir" in comando or "abaixar" in comando:
            novo = max(0.0, atual - 0.1)
            volume.SetMasterVolumeLevelScalar(novo, None)
            return f"Volume reduzido para {novo:.0%}"
        if "mutar" in comando or "silenciar" in comando:
            volume.SetMute(1, None)
            return "Volume mutado."
        if "ativar" in comando:
            volume.SetMute(0, None)
            return "Volume ativado."
        return f"Volume atual: {atual:.0%}"
    except Exception as exc:
        log.warning("Erro no controle de volume: %s", exc)
        return "Erro ao controlar volume do sistema"


def _info_hardware(_ctx: ActionContext) -> str:
    import platform
    import psutil
    so = platform.system()
    versao = platform.version()
    cpu = psutil.cpu_count(logical=False)
    ram = round(psutil.virtual_memory().total / (1024**3), 1)
    return f"Sistema: {so} {versao[:20]}, CPU: {cpu} nucleos, RAM: {ram}GB"


def _matar_processo(ctx: ActionContext) -> str:
    import psutil
    termo = ctx.params.get("nome", ctx.comando)
    mortos = []
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            if termo.lower() in proc.info["name"].lower():
                proc.kill()
                mortos.append(proc.info["name"])
        except Exception:
            pass
    if mortos:
        return f"Processo(s) encerrados: {', '.join(mortos[:5])}"
    return f"Processo '{termo}' nao encontrado."


def _verificar_programa(ctx: ActionContext) -> str:
    programa = ctx.params.get("programa", ctx.comando).lower().strip()
    for visivel in ctx.pc.programas_visiveis():
        if programa in visivel["nome"].lower() or programa in visivel["titulo"].lower():
            return f"Sim, {visivel['nome']} esta aberto na tela."
    try:
        from core.skills.visao import analisar_ecra
        resultado = analisar_ecra(
            f"O programa {programa} esta visivel na tela? Responda apenas sim ou nao e o nome."
        )
        if "sim" in resultado.lower():
            return resultado
    except Exception:
        pass
    return f"Nao encontrei {programa} na tela."


def _analisar_ecra(ctx: ActionContext) -> str:
    from core.skills.visao import analisar_ecra
    return analisar_ecra(ctx.params.get("pergunta", ctx.comando))


def _desligar_assistente(ctx: ActionContext) -> str:
    ctx.falar("Desligando.")
    ctx.encerrar()
    return "Encerrando..."


def _abrir_lista_estilos() -> None:
    from core.skills.gerar_imagem import ESTILOS_DISPONIVEIS
    linhas = "".join(f"    <li><strong>{estilo}</strong></li>\n" for estilo in ESTILOS_DISPONIVEIS)
    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"><title>Estilos Viviane</title>
<style>
  body {{ font: 16px/1.6 Arial; background: #111; color: #eee; max-width: 500px; margin: 40px auto; padding: 20px; }}
  h1 {{ color: #0ff; }}
  li {{ padding: 4px 0; }}
</style></head>
<body><h1>Estilos de Imagem</h1><ul>{linhas}</ul></body></html>"""
    path = os.path.join(tempfile.gettempdir(), "viviane_estilos.html")
    with open(path, "w", encoding="utf-8") as arquivo:
        arquivo.write(html)
    os.startfile(path)


def _gerar_imagem(ctx: ActionContext) -> str:
    from core.skills.gerar_imagem import ESTILOS_DISPONIVEIS, gerar_imagem
    prompt = ctx.params.get("prompt") or ctx.params.get("descricao") or ctx.comando
    estilo = None
    try:
        from core.llm.brain import carregar_perfil, salvar_perfil
        perfil = carregar_perfil()
        ultimo_estilo = perfil.get("ultimo_estilo")
        _abrir_lista_estilos()
        ctx.falar("Escolha um estilo na lista que abri, ou diga o nome.")
        resp_estilo = ctx.voz.ouvir_comando() if ctx.voz is not None else None
        if resp_estilo:
            resp_lower = resp_estilo.lower().strip()
            for item in ESTILOS_DISPONIVEIS:
                if item.lower() in resp_lower or resp_lower in item.lower():
                    estilo = item
                    break
            if not estilo and ultimo_estilo:
                estilo = ultimo_estilo
                ctx.falar(f"A usar o último estilo: {estilo}.")
        if estilo:
            salvar_perfil("ultimo_estilo", estilo)
            ctx.cerebro.aprendizado.aprender(
                f"estilo {estilo.lower()}",
                "gerar_imagem",
                {"prompt": prompt, "descricao": prompt},
            )
    except Exception:
        pass
    return gerar_imagem(prompt, estilo)


HANDLERS: dict[str, Handler] = {
    "parar_fala": _parar_fala,
    "abrir_programa": _abrir_programa,
    "buscar_web": _buscar_web,
    "fetch_page": _fetch_page,
    "previsao_tempo": _previsao,
    "noticias": _noticias,
    "lembrete": _lembrete,
    "tocar_musica": _tocar_musica,
    "comando_sistema": _comando_sistema,
    "abrir_pasta": _abrir_pasta,
    "diagnostico": _diagnostico,
    "ip_local": _info,
    "ip_publico": _info,
    "info_disco": _info,
    "info_so": _info,
    "info_rede": _info,
    "executar_cmd": _executar_cmd,
    "configuracao": _configuracao,
    "info_processos": _info_processos,
    "info_servicos": _info_servicos,
    "db_status": _db_status,
    "salvar_conhecimento": _salvar_conhecimento,
    "buscar_conhecimento": _buscar_conhecimento,
    "listar_conhecimento": _listar_conhecimento,
    "audio_devices": _audio_devices,
    "capturar_webcam": _capturar_webcam,
    "gravar_tela": _gravar_tela,
    "tirar_print": _tirar_print,
    "listar_janelas": _listar_janelas,
    "alternar_janela": _alternar_janela,
    "fechar_janela": _fechar_janela,
    "listar_sessoes_audio": _listar_sessoes_audio,
    "volume_app": _volume_app,
    "programas_abertos": _programas_abertos,
    "listar_servicos_windows": _listar_servicos,
    "controle_servico": _controle_servico,
    "ler_registro": _ler_registro,
    "smarthome_dispositivos": _smarthome_dispositivos,
    "smarthome_ligar": _smarthome_ligar,
    "smarthome_desligar": _smarthome_desligar,
    "smarthome_brilho": _smarthome_brilho,
    "smarthome_temperatura": _smarthome_temperatura,
    "smarthome_cena": _smarthome_cena,
    "volume_total": _volume_total,
    "info_hardware": _info_hardware,
    "matar_processo": _matar_processo,
    "verificar_programa": _verificar_programa,
    "analisar_ecra": _analisar_ecra,
    "visualizar_ecra": _analisar_ecra,
    "desligar_assistente": _desligar_assistente,
    "gerar_imagem": _gerar_imagem,
}


def dispatch(intent: str, ctx: ActionContext) -> str | None:
    """Executa a ação. None significa que o assistente deve conversar."""
    if intent in SENSITIVE_INTENTS and not settings.allow_system_actions:
        return _bloqueio()
    handler = HANDLERS.get(intent)
    if handler is None:
        return None
    ctx.intent = intent
    resultado = handler(ctx)
    if resultado is None and intent == "executar_cmd":
        return None
    return resultado if isinstance(resultado, str) else ""
