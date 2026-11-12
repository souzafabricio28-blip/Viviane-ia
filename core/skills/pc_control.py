from __future__ import annotations

import glob
import logging
import os
import re
import subprocess
import webbrowser
from pathlib import Path
from typing import Any

try:
    import keyboard
    import pyautogui
except ImportError:
    keyboard = None
    pyautogui = None

from core.voice import falar
from core.memoria import memoria as db_memoria

log = logging.getLogger("Viviane")

_CREATE_NO_WINDOW = 0x08000000

# ── Programas comuns (nome -> comando/exe) ─────────────────────────
_PROGRAMAS: dict[str, str | None] = {
    "chrome": "chrome",
    "firefox": "firefox",
    "edge": "msedge",
    "opera": "opera",
    "brave": "brave",
    "calculadora": "calc",
    "bloco de notas": "notepad",
    "notas": "notepad",
    "cmd": "cmd",
    "terminal": "cmd",
    "powershell": "powershell",
    "explorador de arquivos": "explorer",
    "arquivos": "explorer",
    "paint": "mspaint",
    "word": "winword",
    "excel": "excel",
    "powerpoint": "powerpt",
    "outlook": "outlook",
    "visual studio": "devenv",
    "vscode": "code",
    "code": "code",
    "spotify": "spotify",
    "discord": "discord",
    "telegram": "telegram",
    "whatsapp": "whatsapp",
    "obs studio": "obs64",
    "steam": "steam",
    "epic games": "com.epicgames.launcher",
    "slack": "slack",
    "zoom": "zoom",
    "teams": "teams",
    "notion": "notion",
    "obsidian": "obsidian",
    "vlc": "vlc",
    "winrar": "winrar",
    "7zip": "7zfm",
    "photoshop": "photoshop",
    "illustrator": "illustrator",
    "sublime text": "sublime_text",
    "intellij": "idea",
    "android studio": "studio",
    "docker": "docker",
    "postman": "postman",
    "insomnia": "insomnia",
    "git bash": "git-bash",
    "wsl": "wsl",
    "task manager": "taskmgr",
    "gerenciador de tarefas": "taskmgr",
    "painel de controle": "control",
    "configuracoes": "ms-settings:",
    "configuração": "ms-settings:",
    "regedit": "regedit",
    "editor de registro": "regedit",
    "servicos": "services.msc",
    "serviços": "services.msc",
    "gerenciador de dispositivos": "devmgmt.msc",
    "monitor de recursos": "resmon",
    "monitor de desempenho": "perfmon",
    "limpeza de disco": "cleanmgr",
    "desfragmentador": "dfrgui",
    "gerenciamento de disco": "diskmgmt.msc",
    "informacoes do sistema": "msinfo32",
    "politica de grupo": "gpedit.msc",
    "firewall": "wf.msc",
    "agendador de tarefas": "taskschd.msc",
    "visualizador de eventos": "eventvwr",
    "prompt de comando": "cmd",
    "hyper-v": "virtmgmt.msc",
    "gerenciamento do computador": "compmgmt.msc",
    "impressoras": "control printers",
    "som": "mmsys.cpl",
    "teclado": "control keyboard",
    "mouse": "control mouse",
    "data e hora": "timedate.cpl",
    "fontes": "control fonts",
    "contas de usuario": "netplwiz",
    "programas e recursos": "appwiz.cpl",
    "opcoes de energia": "powercfg.cpl",
    "personalizacao": "control desktop",
    "facilidade de acesso": "control accessibility",
    "cortana": None,
    "youtube": None,
    "netflix": None,
    "prime video": None,
    "twitch": None,
    "twitter": None,
    "x": None,
    "instagram": None,
    "facebook": None,
    "linkedin": None,
    "github": None,
    "gmail": None,
    "hotmail": None,
    "outlook web": None,
    "google drive": None,
    "onedrive": None,
    "dropbox": None,
    "whatsapp web": None,
    "telegram web": None,
}

# ── URLs para programas que abrem no navegador ──────────────────────
_APPS_WEB: dict[str, str] = {
    "youtube": "https://youtube.com",
    "netflix": "https://netflix.com",
    "prime video": "https://primevideo.com",
    "twitch": "https://twitch.tv",
    "twitter": "https://twitter.com",
    "x": "https://x.com",
    "instagram": "https://instagram.com",
    "facebook": "https://facebook.com",
    "linkedin": "https://linkedin.com",
    "github": "https://github.com",
    "gmail": "https://mail.google.com",
    "hotmail": "https://outlook.live.com",
    "outlook web": "https://outlook.office.com",
    "google drive": "https://drive.google.com",
    "onedrive": "https://onedrive.live.com",
    "dropbox": "https://dropbox.com",
    "whatsapp web": "https://web.whatsapp.com",
    "telegram web": "https://web.telegram.org",
    "chatgpt": "https://chatgpt.com",
    "claude": "https://claude.ai",
    "gemini": "https://gemini.google.com",
    "deepseek": "https://chat.deepseek.com",
    "perplexity": "https://perplexity.ai",
}

# ── Comandos do PowerShell para ações do Windows ────────────────────
_CMD_PS: dict[str, str] = {
    "listar processos": "Get-Process | Select-Object Name, Id, CPU, WorkingSet | ConvertTo-Json",
    "listar servicos": "Get-Service | Where-Object {$_.Status -eq 'Running'} | Select-Object Name, DisplayName, Status | ConvertTo-Json",
    "listar unidades": "Get-PSDrive -PSProvider FileSystem | Select-Object Name, Root, Used, Free | ConvertTo-Json",
    "ip config": "ipconfig | Select-String IPv4",
    "wifi senha": "netsh wlan show profiles | Select-String 'Perfil'",
    "wifi redes": "netsh wlan show networks",
    "info sistema": "Get-ComputerInfo | ConvertTo-Json",
    "info hardware": "Get-CimInstance Win32_ComputerSystem | Select-Object Manufacturer, Model, TotalPhysicalMemory | ConvertTo-Json",
    "bateria": "powercfg /batteryreport",
    "usb devices": "Get-PnPDevice | Where-Object {$_.Class -eq 'USB'} | Select-Object FriendlyName, Status | ConvertTo-Json",
}


class ControladorPC:
    # ── ABRIR PROGRAMAS ────────────────────────────────────────────
    def abrir_programa(self, nome: str) -> bool | None:
        nome = nome.lower().strip()

        # Tenta match exato ou parcial na lista
        for chave, comando in _PROGRAMAS.items():
            if nome == chave or nome in chave or chave in nome:
                if chave in _APPS_WEB:
                    webbrowser.open(_APPS_WEB[chave])
                    falar(f"Abrindo {chave}.")
                    db_memoria.registrar_comando("programa", chave, "Web")
                    return True
                if comando:
                    try:
                        subprocess.Popen(comando, shell=True, creationflags=_CREATE_NO_WINDOW)
                        falar(f"Abrindo {chave}.")
                        db_memoria.registrar_comando("programa", chave, comando)
                        return True
                    except Exception:
                        pass

        # Tenta achar o executavel no PATH
        encontrado = self._achar_exe(nome)
        if encontrado:
            try:
                subprocess.Popen(encontrado, shell=True, creationflags=_CREATE_NO_WINDOW)
                falar(f"Abrindo {nome}.")
                db_memoria.registrar_comando("programa", nome, encontrado)
                return True
            except Exception:
                pass

        falar(f"Nao encontrei o programa {nome}.")
        db_memoria.registrar_comando("programa", nome, "Nao encontrado", success=False)
        return False

    def _achar_exe(self, nome: str) -> str | None:
        """Busca um executavel no PATH e em locais comuns."""
        nome = nome.strip().lower()

        # PATH
        for path_dir in os.environ.get("PATH", "").split(os.pathsep):
            for ext in ["", ".exe", ".cmd", ".bat", ".lnk"]:
                caminho = os.path.join(path_dir, f"{nome}{ext}")
                if os.path.isfile(caminho):
                    return caminho

        # Start Menu
        start_menu = os.path.expanduser(
            r"~\AppData\Roaming\Microsoft\Windows\Start Menu\Programs"
        )
        for root, _dirs, files in os.walk(start_menu):
            for f in files:
                if nome in f.lower() and f.endswith((".lnk", ".url")):
                    return os.path.join(root, f)

        # Common locations
        locais_comuns = [
            r"C:\Program Files",
            r"C:\Program Files (x86)",
            r"C:\Program Files\WindowsApps",
            os.path.expanduser(r"~\AppData\Local"),
        ]
        for base in locais_comuns:
            if os.path.isdir(base):
                pattern = f"{base}/**/{nome}.exe"
                matches = glob.glob(pattern, recursive=True)
                if matches:
                    return matches[0]

        return None

    # ── COMANDO GENERICO (PowerShell / CMD) ────────────────────────
    def comando_valido(self, comando: str) -> bool:
        """True se a primeira palavra for um comando real (cmdlet, alias, programa ou caminho)."""
        texto = (comando or "").strip()
        if not texto:
            return False
        if texto[0] in "&.$(@\"'" or "\\" in texto.split()[0] or "/" in texto.split()[0]:
            return True
        primeiro = texto.split()[0]
        if not re.fullmatch(r"[A-Za-z0-9_.\-]+", primeiro):
            return False
        try:
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 f"if (Get-Command -Name '{primeiro}' -ErrorAction SilentlyContinue) {{ 'ok' }}"],
                capture_output=True, text=True, timeout=10,
                creationflags=_CREATE_NO_WINDOW,
            )
            return "ok" in (r.stdout or "")
        except Exception:
            return False

    def executar_comando(self, comando: str) -> str:
        """Executa qualquer comando no PowerShell e retorna a saida."""
        try:
            preparado = (
                "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; "
                "$OutputEncoding=[System.Text.Encoding]::UTF8; " + comando
            )
            resultado = subprocess.run(
                ["powershell", "-NoProfile", "-Command", preparado],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
                creationflags=_CREATE_NO_WINDOW,
            )
            saida = (resultado.stdout or resultado.stderr or "").strip()
            if saida:
                db_memoria.registrar_comando("powershell", comando, saida[:500])
                return saida[:2000]
            db_memoria.registrar_comando("powershell", comando, "Sem saida")
            return "Comando executado (sem saída)."
        except subprocess.TimeoutExpired:
            db_memoria.registrar_comando("powershell", comando, "Timeout", success=False)
            return "Comando excedeu o tempo limite."
        except Exception as e:
            db_memoria.registrar_comando("powershell", comando, str(e), success=False)
            return f"Erro ao executar: {e}"

    def obter_processos(self) -> str:
        return self.executar_comando(
            "Get-Process | Select-Object Name, Id, CPU, WorkingSet | ConvertTo-Json"
        )

    def obter_servicos(self) -> str:
        return self.executar_comando(
            "Get-Service | Where-Object {$_.Status -eq 'Running'} | Select-Object Name, DisplayName, Status | ConvertTo-Json"
        )

    # ── COMANDOS DE SISTEMA ────────────────────────────────────────
    def executar_comando_sistema(self, acao: str) -> None:
        acao = acao.lower().strip()
        for palavras, handler in self._COMANDOS_SISTEMA:
            if any(p in acao for p in palavras):
                handler(self, acao)
                return
        falar(f"Comando de sistema '{acao}' nao reconhecido.")

    def _cmd_desligar_pc(self, acao: str) -> None:
        subprocess.Popen("shutdown /s /t 30", shell=True, creationflags=_CREATE_NO_WINDOW)
        falar("Desligando o computador em trinta segundos.")

    def _cmd_cancelar_desligamento(self, acao: str) -> None:
        subprocess.Popen("shutdown /a", shell=True, creationflags=_CREATE_NO_WINDOW)
        falar("Desligamento cancelado.")

    def _cmd_reiniciar(self, acao: str) -> None:
        subprocess.Popen("shutdown /r /t 30", shell=True, creationflags=_CREATE_NO_WINDOW)
        falar("Reiniciando o computador em trinta segundos.")

    def _cmd_bloquear(self, acao: str) -> None:
        subprocess.Popen("rundll32.exe user32.dll,LockWorkStation", shell=True, creationflags=_CREATE_NO_WINDOW)
        falar("Bloqueando a tela.")

    def _cmd_hibernar(self, acao: str) -> None:
        subprocess.Popen("shutdown /h", shell=True, creationflags=_CREATE_NO_WINDOW)
        falar("Hibernando o sistema.")

    def _cmd_suspender(self, acao: str) -> None:
        subprocess.Popen("rundll32.exe powrprof.dll,SetSuspendState 0,1,0", shell=True, creationflags=_CREATE_NO_WINDOW)
        falar("Suspendendo o computador.")

    def _cmd_logoff(self, acao: str) -> None:
        subprocess.Popen("shutdown /l", shell=True, creationflags=_CREATE_NO_WINDOW)
        falar("Encerrando sessao.")

    def _cmd_desligar_agora(self, acao: str) -> None:
        subprocess.Popen("shutdown /s /t 5", shell=True, creationflags=_CREATE_NO_WINDOW)
        falar("Desligando agora.")

    def _cmd_desligar_timer(self, acao: str) -> None:
        nums = re.findall(r"(\d+)", acao)
        if nums:
            minutos = int(nums[0])
            segundos = max(minutos * 60, 10)
            subprocess.Popen(f"shutdown /s /t {segundos}", shell=True, creationflags=_CREATE_NO_WINDOW)
            falar(f"Desligando em {minutos} minuto(s).")
        else:
            falar("Quanto tempo? Ex: desligar em 30 minutos.")

    def _cmd_mutar(self, acao: str) -> None:
        keyboard.send("volume mute")
        falar("Audio mutado.")

    def _cmd_volume_up(self, acao: str) -> None:
        for _ in range(5):
            keyboard.send("volume up")
        falar("Volume aumentado.")

    def _cmd_volume_down(self, acao: str) -> None:
        for _ in range(5):
            keyboard.send("volume down")
        falar("Volume reduzido.")

    def _cmd_play_pause(self, acao: str) -> None:
        keyboard.send("play/pause media")
        falar("Play / pause.")

    def _cmd_proxima(self, acao: str) -> None:
        keyboard.send("next track")
        falar("Proxima faixa.")

    def _cmd_anterior(self, acao: str) -> None:
        keyboard.send("previous track")
        falar("Faixa anterior.")

    def _cmd_minimizar_tudo(self, acao: str) -> None:
        keyboard.send("windows+d")
        falar("Mostrando area de trabalho.")

    def _cmd_fechar_janela(self, acao: str) -> None:
        keyboard.send("alt+f4")
        falar("Fechando janela.")

    def _cmd_fechar_aba(self, acao: str) -> None:
        keyboard.send("ctrl+w")
        falar("Aba fechada.")

    def _cmd_alternar_janela(self, acao: str) -> None:
        keyboard.send("alt+tab")
        falar("Alternando janela.")

    def _cmd_print(self, acao: str) -> None:
        self._capturar_tela()

    def _cmd_listar_processos(self, acao: str) -> None:
        processos = self.obter_processos()
        falar(f"Processos: {processos[:300]}")

    def _cmd_listar_janelas_sistema(self, acao: str) -> None:
        janelas = self.listar_janelas()
        if not janelas:
            falar("Nenhuma janela aberta.")
            return
        falar(f"Janelas: {len(janelas)} abertas. {janelas[0]['titulo'][:60]}")

    def _cmd_executar(self, acao: str) -> None:
        cmd = re.sub(r"^(executar|rode|roda|cmd)\s+", "", acao).strip()
        if cmd:
            saida = self.executar_comando(cmd)
            falar(f"Comando executado. {saida[:100]}")
        else:
            falar("Qual comando deseja executar?")

    _COMANDOS_SISTEMA: list[tuple[list[str], Any]] = [
        (["desligar pc", "desligar computador", "desligar o pc"], _cmd_desligar_pc),
        (["cancelar desligamento", "cancelar shutdown"], _cmd_cancelar_desligamento),
        (["reiniciar pc", "reiniciar computador", "reiniciar"], _cmd_reiniciar),
        (["bloquear pc", "bloquear computador", "trancar pc", "bloquear tela"], _cmd_bloquear),
        (["hibernar"], _cmd_hibernar),
        (["suspender", "dormir pc"], _cmd_suspender),
        (["sair da conta", "logoff", "logout", "encerrar sessao"], _cmd_logoff),
        (["desligar agora", "desliga agora", "desligar ja"], _cmd_desligar_agora),
        (["desligar em ", "desligar daqui"], _cmd_desligar_timer),
        (["mutar", "silenciar", "sem som", "mudo"], _cmd_mutar),
        (["aumentar volume", "aumentar som", "volume mais alto"], _cmd_volume_up),
        (["diminuir volume", "diminuir som", "volume mais baixo", "abaixar volume"], _cmd_volume_down),
        (["pausar", "pausa", "parar musica", "play pause", "play/pause"], _cmd_play_pause),
        (["proxima musica", "proxima faixa", "pular musica", "proxima"], _cmd_proxima),
        (["anterior", "voltar faixa", "faixa anterior"], _cmd_anterior),
        (["minimizar tudo", "mostrar area de trabalho", "limpar tela"], _cmd_minimizar_tudo),
        (["fechar janela", "fechar programa"], _cmd_fechar_janela),
        (["fechar aba"], _cmd_fechar_aba),
        (["alternar janela", "trocar janela", "mudar de janela"], _cmd_alternar_janela),
        (["print", "capturar tela", "tirar print", "screenshot", "foto da tela"], _cmd_print),
        (["listar processos", "listar programmes", "listar aplicativos", "listar apps", "listar windows"], _cmd_listar_processos),
        (["listar janelas", "listar windows", "listar aplicativos abertos"], _cmd_listar_janelas_sistema),
        (["executar ", "rode ", "roda ", "cmd "], _cmd_executar),
    ]

    # ── PRINT ──
    def _capturar_tela(self) -> None:
        try:
            pasta = Path.home() / "Pictures"
            pasta.mkdir(parents=True, exist_ok=True)
            caminho = pasta / "print_viviane.png"
            pyautogui.screenshot(str(caminho))
            falar("Print salvo em Imagens.")
        except Exception:
            falar("Nao consegui salvar o print.")

    # ── ABRIR PASTA / DIRETORIO ─────────────────────────────────────
    def abrir_pasta(self, caminho: str) -> bool:
        """Abre um pasta/diretorio no Explorador de Arquivos."""
        caminho = caminho.strip().strip('"').strip("'")
        if not caminho:
            falar("Qual pasta?")
            return False

        # Resolve caminhos relativos comuns
        caminho_lower = caminho.lower()
        pasta_home = str(Path.home())
        substituicoes = {
            "documentos": "Documents",
            "downloads": "Downloads",
            "imagens": "Pictures",
            "videos": "Videos",
            "area de trabalho": "Desktop",
            "desktop": "Desktop",
            "appdata": "AppData",
            "sistema": "C:\\Windows",
            "windows": "C:\\Windows",
            "programas": "C:\\Program Files",
            "program files": "C:\\Program Files",
            "origin": "C:\\Program Files (x86)",
            "steam": "C:\\Program Files (x86)\\Steam",
            "jogos": "D:\\Jogos",
        }
        for chave, pasta in substituicoes.items():
            if caminho_lower == chave:
                caminho = os.path.join(pasta_home, pasta)
                break
            if caminho_lower.startswith(chave + "\\") or caminho_lower.startswith(chave + "/"):
                resto = caminho[len(chave):].lstrip("\\/").strip()
                caminho = os.path.join(pasta_home, pasta, resto)
                break

        # Se não tem drive nem barra, tenta resolver relativo à home
        if not re.match(r"^[A-Za-z]:[\\/]", caminho) and not caminho.startswith("\\\\"):
            if not os.path.isabs(caminho):
                candidato = os.path.join(pasta_home, caminho)
                if os.path.isdir(candidato):
                    caminho = candidato

        try:
            if os.path.isdir(caminho):
                subprocess.Popen(
                    f'explorer "{caminho}"',
                    shell=True, creationflags=_CREATE_NO_WINDOW,
                )
                falar(f"Abrindo {caminho}.")
                db_memoria.registrar_comando("pasta", caminho, "OK")
                return True
            # Último recurso: abre o pai
            pai = os.path.dirname(caminho.rstrip("\\/"))
            if pai and os.path.isdir(pai):
                subprocess.Popen(
                    f'explorer "{pai}"',
                    shell=True, creationflags=_CREATE_NO_WINDOW,
                )
                falar(f"A pasta {caminho} não existe. Abrindo {pai}.")
                db_memoria.registrar_comando("pasta", caminho, f"Pai: {pai}")
                return True
            falar(f"Não encontrei a pasta {caminho}.")
            db_memoria.registrar_comando("pasta", caminho, "Nao encontrada", success=False)
            return False
        except Exception as e:
            falar(f"Erro ao abrir pasta: {e}")
            db_memoria.registrar_comando("pasta", caminho, str(e), success=False)
            return False

    # ── ABRIR CONFIGURACAO DO WINDOWS ──
    def abrir_configuracao(self, pagina: str) -> None:
        uri = self._mapear_configuracao(pagina)
        if uri:
            subprocess.Popen(f"start {uri}", shell=True, creationflags=_CREATE_NO_WINDOW)
            falar(f"Abrindo configuracao de {pagina}.")
            db_memoria.registrar_comando("configuracao", pagina, uri)
        else:
            falar(f"Nao encontrei configuracao para {pagina}.")
            db_memoria.registrar_comando("configuracao", pagina, "Nao mapeado", success=False)

    CONFIGURACOES: dict[str, str] = {
            "wifi": "ms-settings:network-wifi",
            "bluetooth": "ms-settings:bluetooth",
            "tela": "ms-settings:display",
            "display": "ms-settings:display",
            "resolucao": "ms-settings:display",
            "som": "ms-settings:sound",
            "audio": "ms-settings:sound",
            "notificacao": "ms-settings:notifications",
            "aplicativos": "ms-settings:appsfeatures",
            "programas": "ms-settings:appsfeatures",
            "bateria": "ms-settings:batterysaver",
            "armazenamento": "ms-settings:storagesense",
            "armazenamento": "ms-settings:storagepolicies",
            "tema": "ms-settings:themes",
            "plano de fundo": "ms-settings:personalization-background",
            "fundo": "ms-settings:personalization-background",
            "cores": "ms-settings:personalization-colors",
            "tela de bloqueio": "ms-settings:lockscreen",
            "barra de tarefas": "ms-settings:taskbar",
            "iniciar": "ms-settings:personalization-start",
            "acessibilidade": "ms-settings:easeofaccess",
            "teclado": "ms-settings:keyboard",
            "mouse": "ms-settings:mousetouchpad",
            "idioma": "ms-settings:regionlanguage",
            "data": "ms-settings:dateandtime",
            "conta": "ms-settings:accounts",
            "rede": "ms-settings:network-status",
            "vpn": "ms-settings:network-vpn",
            "proxy": "ms-settings:network-proxy",
            "area de trabalho remota": "ms-settings:remotedesktop",
            "jogos": "ms-settings:gaming-gamebar",
            "impressora": "ms-settings:printers",
            "usb": "ms-settings:usb",
            "telefone": "ms-settings:phone",
            "windows update": "ms-settings:windowsupdate",
            "seguranca": "ms-settings:windowsdefender",
            "backup": "ms-settings:backup",
            "recuperacao": "ms-settings:recovery",
            "solucao de problemas": "ms-settings:troubleshoot",
            "energia": "ms-settings:powersleep",
    }

    @staticmethod
    def _mapear_configuracao(pagina: str) -> str | None:
        return ControladorPC.CONFIGURACOES.get(pagina.lower().strip())

    # ── JANELAS ───────────────────────────────────────────────────
    def listar_janelas(self) -> list[dict]:
        import sys

        if sys.platform != "win32":
            return []
        try:
            import pygetwindow as gw
        except ImportError:
            return []
        wins = gw.getAllTitles()
        wins = [w for w in wins if w.strip() and w != "Program Manager"]
        ativo = gw.getActiveWindow()
        ativo_titulo = ativo.title if ativo else ""
        resultado = []
        for w in wins:
            resultado.append({
                "titulo": w,
                "ativa": w == ativo_titulo,
            })
        return resultado

    def alternar_para_janela(self, termo: str) -> bool:
        import sys

        if sys.platform != "win32":
            return False
        try:
            import pygetwindow as gw
        except ImportError:
            return False
        termo_lower = termo.lower()
        wins = gw.getWindowsWithTitle(termo)
        if not wins:
            for w in gw.getAllWindows():
                if termo_lower in w.title.lower():
                    wins.append(w)
        if wins:
            try:
                wins[0].activate()
                return True
            except Exception:
                try:
                    wins[0].minimize()
                    wins[0].restore()
                    return True
                except Exception:
                    pass
        return False

    def fechar_janela(self, termo: str) -> bool:
        import sys

        if sys.platform != "win32":
            return False
        try:
            import pygetwindow as gw
        except ImportError:
            return False
        termo_lower = termo.lower()
        for w in gw.getAllWindows():
            if termo_lower in w.title.lower():
                try:
                    w.close()
                    return True
                except Exception:
                    pass
        return False

    # ── VOLUME POR APP ────────────────────────────────────────────
    def listar_sessoes_audio(self) -> list[dict]:
        from pycaw.pycaw import AudioUtilities
        sessoes = []
        for s in AudioUtilities.GetAllSessions():
            if s.Process and s.Process.name():
                vol = s.SimpleAudioVolume
                sessoes.append({
                    "processo": s.Process.name(),
                    "volume": vol.GetMasterVolume(),
                    "mutado": vol.GetMute(),
                })
        return sessoes

    def volume_app(self, processo: str, nivel: float | None = None, mutar: bool | None = None) -> str:
        from pycaw.pycaw import AudioUtilities
        processo_lower = processo.lower()
        for s in AudioUtilities.GetAllSessions():
            if s.Process and s.Process.name() and processo_lower in s.Process.name().lower():
                vol = s.SimpleAudioVolume
                if nivel is not None:
                    vol.SetMasterVolume(max(0.0, min(1.0, nivel)), None)
                if mutar is not None:
                    vol.SetMute(mutar, None)
                return f"{s.Process.name()}: volume {vol.GetMasterVolume():.0%}"
        return f"Processo '{processo}' nao encontrado."

    # ── PROGRAMAS VISIVEIS (barra de tarefas / tela) ──────────────
    def programas_visiveis(self) -> list[dict]:
        """Retorna apenas programas com janela visivel na tela/barra de tarefas."""
        import sys

        if sys.platform != "win32":
            return []
        try:
            import pygetwindow as gw
        except ImportError:
            return []
        wins = gw.getAllTitles()
        wins = [w.strip() for w in wins if w.strip() and w != "Program Manager"]
        vistos: set[str] = set()
        resultado = []
        for titulo in wins:
            nome = self._extrair_nome_janela(titulo)
            if nome and nome not in vistos:
                vistos.add(nome)
                resultado.append({"nome": nome, "titulo": titulo})
        return resultado

    # ── PROGRAMAS POR MONITOR ────────────────────────────────────
    @staticmethod
    def _get_monitors() -> list[dict]:
        """Retorna lista de monitores com bounding boxes (left, top, right, bottom)."""
        import ctypes
        from ctypes import wintypes

        monitors: list[dict] = []

        class RECT(ctypes.Structure):
            _fields_ = [
                ("left", wintypes.LONG),
                ("top", wintypes.LONG),
                ("right", wintypes.LONG),
                ("bottom", wintypes.LONG),
            ]

        def callback(hmonitor, hdc, lprcMonitor, dwData):
            rect = ctypes.cast(lprcMonitor, ctypes.POINTER(RECT)).contents
            monitors.append({
                "left": rect.left,
                "top": rect.top,
                "right": rect.right,
                "bottom": rect.bottom,
            })
            return 1

        MONITORENUMPROC = ctypes.WINFUNCTYPE(
            wintypes.BOOL,
            wintypes.HANDLE,
            wintypes.HDC,
            ctypes.POINTER(RECT),
            wintypes.LPARAM,
        )
        ctypes.windll.user32.EnumDisplayMonitors(
            None, None, MONITORENUMPROC(callback), 0
        )
        return monitors

    def programas_por_monitor(self) -> list[dict]:
        """Agrupa janelas visiveis por monitor. Cada monitor lista os programas abertos nele."""
        import sys

        if sys.platform != "win32":
            return []
        try:
            import pygetwindow as gw
        except ImportError:
            return []
        monitors = self._get_monitors()
        all_windows = gw.getAllWindows()
        # Filtra apenas janelas com titulo visivel
        windows = [w for w in all_windows if w.title.strip() and w.title != "Program Manager"]

        result = []
        for i, mon in enumerate(monitors):
            janelas_no_mon = []
            for w in windows:
                # Centro da janela
                cx = w.left + w.width // 2
                cy = w.top + w.height // 2
                if mon["left"] <= cx <= mon["right"] and mon["top"] <= cy <= mon["bottom"]:
                    # Extrai nome legivel do titulo
                    nome = self._extrair_nome_janela(w.title)
                    if nome and not any(j["nome"] == nome for j in janelas_no_mon):
                        janelas_no_mon.append({"nome": nome, "titulo": w.title[:60]})
            result.append({
                "monitor": i + 1,
                "bounds": mon,
                "programas": janelas_no_mon[:15],
            })
        return result

    @staticmethod
    def _extrair_nome_janela(titulo: str) -> str:
        """Extrai nome legivel do programa a partir do titulo da janela."""
        _MAP_BROWSER = {
            "google chrome": "Chrome", "microsoft edge": "Edge",
            "mozilla firefox": "Firefox", "microsoft outlook": "Outlook",
            "windows explorer": "Explorador de Arquivos", "file explorer": "Explorador de Arquivos",
            "task manager": "Gerenciador de Tarefas", "windows task manager": "Gerenciador de Tarefas",
            "prompt de comando": "cmd", "command prompt": "cmd",
            "windows powershell": "PowerShell", "visual studio code": "VSCode",
            "visual studio": "Visual Studio", "android studio": "Android Studio",
            "spotify free": "Spotify", "slack": "Slack", "discord": "Discord",
            "telegram desktop": "Telegram", "whatsapp": "WhatsApp",
            "notion": "Notion", "obsidian": "Obsidian",
            "vlc media player": "VLC", "paint": "Paint", "calculadora": "Calculadora",
            "calculator": "Calculadora", "word": "Word", "excel": "Excel",
            "powerpoint": "PowerPoint", "outlook": "Outlook", "onenote": "OneNote",
            "steam": "Steam", "epic games launcher": "Epic Games",
            "photoshop": "Photoshop", "illustrator": "Illustrator",
            "sublime text": "Sublime Text", "intellij idea": "IntelliJ",
            "postman": "Postman", "docker desktop": "Docker",
            "git bash": "Git Bash", "wsl": "WSL",
            "viviane": "Viviane",
            "alexia": "Viviane",
        }
        t = titulo.lower()
        for chave, nome in _MAP_BROWSER.items():
            if chave in t:
                return nome
        for sep in [" - ", " — ", " – ", " | ", " :: "]:
            if sep in titulo:
                partes = titulo.rsplit(sep, 1)
                candidato = partes[-1].strip()
                if len(candidato) < 40:
                    return candidato
        for suffix, nome in [(" - Google Chrome", "Chrome"), (" — Mozilla Firefox", "Firefox"),
                              (" - Microsoft Edge", "Edge"), (" — Brave", "Brave"),
                              (" - Opera", "Opera"), (" — Vivaldi", "Vivaldi")]:
            if titulo.endswith(suffix):
                return nome
        import re
        sem_parenteses = re.sub(r'\s*\([^)]*\)', '', titulo).strip()
        if sem_parenteses and len(sem_parenteses) < 40:
            return sem_parenteses
        return titulo[:40]

    # ── VARREDURA DE PROGRAMAS (todos os processos + janelas) ────
    def escanear_programas(self) -> dict:
        import psutil
        wins = self.listar_janelas()
        processos = []
        for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
            try:
                pinfo = p.info
                if pinfo["name"]:
                    processos.append({
                        "pid": pinfo["pid"],
                        "nome": pinfo["name"],
                        "cpu": pinfo["cpu_percent"] or 0.0,
                        "memoria": round(pinfo["memory_percent"] or 0.0, 1),
                    })
            except Exception:
                pass
        return {"janelas": wins[:20], "processos": sorted(processos, key=lambda x: x["cpu"], reverse=True)[:20]}

    # ── CONTROLE DE SERVICOS ──────────────────────────────────────
    def listar_servicos_windows(self) -> list[dict]:
        ps = "Get-Service | Select-Object Name, DisplayName, Status, StartType | ConvertTo-Json"
        try:
            r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                               capture_output=True, text=True, timeout=15,
                               creationflags=_CREATE_NO_WINDOW)
            import json
            data = json.loads(r.stdout)
            if not isinstance(data, list):
                data = [data]
            return [{"nome": d["Name"], "exibicao": d["DisplayName"],
                      "status": d["Status"], "inicio": d["StartType"]} for d in data]
        except Exception:
            return []

    def controle_servico(self, nome: str, acao: str) -> str:
        acoes_validas = {"iniciar": "Start-Service", "parar": "Stop-Service",
                         "reiniciar": "Restart-Service", "pausar": "Suspend-Service"}
        cmd = acoes_validas.get(acao)
        if not cmd:
            return f"Acao '{acao}' invalida. Use: iniciar, parar, reiniciar, pausar"
        try:
            subprocess.run(["powershell", "-NoProfile", "-Command",
                           f"{cmd} -Name '{nome}' -ErrorAction Stop"],
                           capture_output=True, text=True, timeout=30,
                           creationflags=_CREATE_NO_WINDOW, check=True)
            return f"Servico '{nome}' {acao}do com sucesso."
        except subprocess.CalledProcessError as e:
            return f"Erro ao {acao} servico '{nome}': {e.stderr[:100]}"

    # ── REGISTRO DO WINDOWS ───────────────────────────────────────
    def ler_registro(self, chave: str, valor: str = "") -> str:
        try:
            ps = f"""
            $path = '{chave}'
            if ('{valor}') {{
                Get-ItemProperty -Path $path -Name '{valor}' -ErrorAction Stop | Select-Object -ExpandProperty '{valor}'
            }} else {{
                Get-ItemProperty -Path $path -ErrorAction Stop | Format-List
            }}
            """
            r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                               capture_output=True, text=True, timeout=15,
                               creationflags=_CREATE_NO_WINDOW)
            saida = (r.stdout or r.stderr or "").strip()
            return saida[:500] if saida else "Chave nao encontrada."
        except Exception as e:
            return f"Erro ao ler registro: {str(e)[:60]}"
