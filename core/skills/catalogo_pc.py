"""Catálogo de comandos do PC gravado na base de conhecimento da Viviane.

Cada tópico descreve um grupo de comandos que ela realmente executa, com frases
de exemplo. Listas de programas, sites e configurações vêm direto do código do
`ControladorPC`, então o catálogo acompanha o que existe de verdade.
Gravar é idempotente: rodar de novo apenas atualiza os tópicos.
"""

from __future__ import annotations

import logging

from core.skills.pc_control import _APPS_WEB, _PROGRAMAS, ControladorPC

log = logging.getLogger("Viviane")

BLOCO = "Comandos do PC"
DESCRICAO_BLOCO = "Tudo o que a Viviane sabe fazer no computador, com exemplos de como pedir."

_MARCAS_FERRAMENTA = (".msc", ".cpl", "control", "ms-settings", "regedit", "msinfo32", "resmon",
                      "perfmon", "cleanmgr", "dfrgui", "eventvwr", "taskmgr", "netplwiz")


def _lista(itens) -> str:
    return ", ".join(sorted(dict.fromkeys(itens)))


def _programas_e_ferramentas() -> tuple[list[str], list[str]]:
    programas, ferramentas = [], []
    for nome, comando in _PROGRAMAS.items():
        if not comando or nome in _APPS_WEB:
            continue
        if any(m in comando for m in _MARCAS_FERRAMENTA):
            ferramentas.append(nome)
        else:
            programas.append(nome)
    return programas, ferramentas


def montar_catalogo() -> list[tuple[str, str, str]]:
    """Devolve (titulo, conteudo, tags) de cada grupo de comandos."""
    programas, ferramentas = _programas_e_ferramentas()
    configuracoes = _lista(ControladorPC.CONFIGURACOES)

    return [
        (
            "Comandos do PC: visão geral",
            "Eu controlo o computador por voz ou texto. Grupos de comandos: abrir programas e sites, "
            "ferramentas do Windows, desligar/reiniciar/bloquear, volume e mídia, janelas e programas "
            "abertos, print/webcam/gravação de tela, pastas, configurações do Windows, informações do "
            "sistema, processos e serviços, e executar comandos no PowerShell. Pergunte por exemplo "
            "'quais comandos de volume você tem?' ou 'como eu abro uma pasta?'. "
            "Ações de sistema (desligar, matar processo, serviços, registro, PowerShell) só funcionam "
            "com ALLOW_SYSTEM_ACTIONS ligado.",
            "comandos, pc, computador, lista, ajuda, o que você faz, quais comandos, funções, capacidades",
        ),
        (
            "Abrir programas",
            "Diga 'abrir <programa>' ou 'abre o <programa>'. Se não estiver na lista, procuro o "
            "executável no PATH, no Menu Iniciar e em Arquivos de Programas. "
            f"Programas que conheço: {_lista(programas)}.",
            "abrir programa, abre, executar programa, iniciar aplicativo, abrir app, chrome, "
            "spotify, vscode, calculadora, bloco de notas, discord",
        ),
        (
            "Abrir sites e serviços web",
            "Diga 'abrir <site>' e eu abro no navegador padrão. "
            f"Sites e serviços: {_lista(_APPS_WEB)}. "
            "Também posso pesquisar na internet: 'pesquise na internet sobre <assunto>'.",
            "abrir site, youtube, gmail, github, chatgpt, netflix, whatsapp web, navegador, internet",
        ),
        (
            "Ferramentas do Windows",
            "Diga 'abrir <ferramenta>'. Disponíveis: " + _lista(ferramentas) + ". "
            "Exemplos: 'abrir gerenciador de tarefas', 'abrir painel de controle', "
            "'abrir gerenciador de dispositivos', 'abrir editor de registro'.",
            "gerenciador de tarefas, painel de controle, regedit, serviços, firewall, "
            "gerenciamento de disco, monitor de recursos, limpeza de disco, agendador de tarefas",
        ),
        (
            "Desligar, reiniciar e bloquear o PC",
            "Comandos de energia: 'desligar o pc' (30 s), 'desligar agora' (5 s), "
            "'desligar em 30 minutos', 'cancelar desligamento', 'reiniciar o computador' (30 s), "
            "'bloquear a tela', 'hibernar', 'suspender' ou 'dormir pc', 'sair da conta' (logoff).",
            "desligar, reiniciar, bloquear, hibernar, suspender, logoff, energia, shutdown, "
            "dormir, cancelar desligamento, timer, desligar pc, desligar computador",
        ),
        (
            "Volume e mídia",
            "Volume geral: 'aumentar o volume', 'diminuir o volume', 'mutar', 'ativar o som', "
            "'volume em 50%', 'deixe o volume em 100%', 'qual o volume'. "
            "Volume por aplicativo: 'volume do chrome', 'mutar spotify', 'listar sessões de áudio'. "
            "Mídia: 'pausar' ou 'play', 'próxima música', 'faixa anterior'. "
            "Também 'listar dispositivos de áudio'.",
            "volume, som, mutar, silenciar, aumentar volume, diminuir volume, pausar, play, "
            "próxima música, faixa anterior, áudio, mídia, spotify, volume por app",
        ),
        (
            "Janelas e programas abertos",
            "Gerenciar janelas: 'minimizar tudo' ou 'mostrar área de trabalho', 'fechar janela', "
            "'fechar aba', 'alternar janela', 'alternar para <nome>', 'fechar a janela <nome>'. "
            "Consultar: 'listar janelas', 'quais programas estão abertos' (agrupados por monitor), "
            "'o <programa> está aberto?' e 'o que tem na minha tela' (analiso a tela por imagem).",
            "janelas, minimizar tudo, fechar janela, alternar janela, programas abertos, monitor, "
            "tela, aba, o que está aberto, analisar tela",
        ),
        (
            "Print, webcam e gravação de tela",
            "'tirar print' ou 'capturar a tela' salva em Imagens (print_viviane.png). "
            "'capturar webcam' tira uma foto pela câmera. 'gravar a tela por 10 segundos' grava a tela. "
            "'listar dispositivos de áudio' mostra microfones e alto-falantes.",
            "print, screenshot, captura de tela, webcam, câmera, gravar tela, gravação, foto da tela",
        ),
        (
            "Abrir pastas",
            "Diga 'abrir a pasta <nome ou caminho>'. Atalhos: documentos, downloads, imagens, vídeos, "
            "área de trabalho (desktop), appdata, windows, programas (Program Files), steam, jogos. "
            "Também aceito caminhos completos como 'abrir a pasta C:\\Projetos'. "
            "Se a pasta não existir, abro a pasta de cima.",
            "pasta, diretório, abrir pasta, documentos, downloads, imagens, vídeos, área de trabalho, "
            "explorador de arquivos, caminho",
        ),
        (
            "Configurações do Windows",
            "Diga 'abrir configuração de <assunto>'. Assuntos: " + configuracoes + ".",
            "configurações, configuração, wifi, bluetooth, tela, som, bateria, rede, vpn, "
            "windows update, segurança, energia, tema, impressora, idioma, ms-settings",
        ),
        (
            "Informações do sistema",
            "Posso informar: 'qual meu ip' (local e público), 'espaço em disco', 'qual o sistema "
            "operacional', 'informações da rede', 'informações do hardware' (CPU e RAM), "
            "'diagnóstico do sistema' (relatório completo), 'status do banco de dados'. "
            "Também monitoro o sistema em segundo plano e aviso quando algo estiver crítico.",
            "ip, ip local, ip público, disco, espaço em disco, sistema operacional, rede, hardware, "
            "cpu, memória, ram, diagnóstico, status, informações do sistema",
        ),
        (
            "Processos e serviços",
            "'listar processos' mostra o que está rodando. 'encerrar o processo <nome>' ou "
            "'matar <nome>' finaliza (ação sensível). 'listar serviços' mostra os serviços do Windows. "
            "'iniciar/parar/reiniciar/pausar o serviço <nome>' controla um serviço (ação sensível). "
            "'ler a chave do registro <caminho>' consulta o registro (ação sensível).",
            "processos, serviços, matar processo, encerrar processo, task, serviço, registro, "
            "regedit, parar serviço, iniciar serviço, listar processos",
        ),
        (
            "Executar comando no PowerShell",
            "Diga 'executar <comando>' (ou 'rode', 'cmd') para rodar um comando no PowerShell. "
            "Só executo se a primeira palavra for um comando real do Windows; frases comuns são "
            "tratadas como conversa. A saída é limitada e o tempo máximo é 30 segundos. "
            "Exemplo: 'executar Get-Date', 'executar ipconfig'.",
            "powershell, cmd, terminal, executar comando, rodar comando, prompt, script, shell",
        ),
        (
            "Controle da própria Viviane",
            "'pare' ou 'cala a boca' interrompe minha fala (também o botão PARAR ou a tecla Esc). "
            "Com o microfone ligado, diga 'Viviane' e depois o pedido. O botão da esquerda liga e "
            "desliga o microfone. 'desligar a viviane' ou 'desligar o assistente' fecha o programa. "
            "Para desligar o computador use os comandos de energia.",
            "parar, pare, calar, microfone, wake word, viviane, desligar assistente, desligar viviane, esc",
        ),
    ]


def registrar_comandos_pc(conhecimento) -> int:
    """Grava/atualiza o catálogo na base de conhecimento. Devolve quantos tópicos foram gravados."""
    try:
        conhecimento.criar_bloco(BLOCO, DESCRICAO_BLOCO)
        total = 0
        for titulo, conteudo, tags in montar_catalogo():
            conhecimento.adicionar(
                titulo, conteudo, BLOCO, f"{tags}, comando, comandos, pc, computador", fonte="catalogo_pc",
            )
            total += 1
        return total
    except Exception as exc:
        log.warning("Não consegui gravar o catálogo de comandos do PC: %s", exc)
        return 0
