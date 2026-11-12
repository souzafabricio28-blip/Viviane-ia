from __future__ import annotations

import platform
import socket

import psutil

from core.conversa import registrar
from core.voice import falar
from core.memoria import memoria as db_memoria


class InfoSistema:
    def ip_local(self) -> str:
        try:
            hostname = socket.gethostname()
            ip = socket.gethostbyname(hostname)
            texto = f"O nome da sua máquina é {hostname} e o IP local é {ip}."
            registrar("assistente", f"[IP] {hostname} - {ip}")
            db_memoria.registrar_comando("consulta", "ip_local", texto)
            falar(texto)
            return texto
        except Exception as e:
            erro = f"Erro ao obter IP: {str(e)[:60]}"
            falar(erro)
            return erro

    def ip_publico(self) -> str:
        try:
            import requests
            resp = requests.get("https://api.ipify.org?format=json", timeout=5)
            ip = resp.json().get("ip", "desconhecido")
            texto = f"O seu IP público é {ip}."
            registrar("assistente", f"[IP Público] {ip}")
            db_memoria.registrar_comando("consulta", "ip_publico", texto)
            falar(texto)
            return texto
        except Exception as e:
            erro = f"Não consegui obter o IP público: {str(e)[:60]}"
            falar(erro)
            return erro

    def disco(self) -> str:
        try:
            partes = []
            for part in psutil.disk_partitions():
                if part.fstype and "fixed" in part.opts.lower():
                    uso = psutil.disk_usage(part.mountpoint)
                    livre_gb = uso.free / (1024 ** 3)
                    total_gb = uso.total / (1024 ** 3)
                    if total_gb > 1:
                        partes.append(
                            f"{part.mountpoint}: {total_gb:.0f}GB total, {livre_gb:.0f}GB livres"
                        )
            texto = ". ".join(partes)
            registrar("assistente", f"[Disco] {texto}")
            db_memoria.registrar_comando("consulta", "disco", texto)
            falar(texto)
            return texto
        except Exception as e:
            erro = f"Erro ao ler discos: {str(e)[:60]}"
            falar(erro)
            return erro

    def sistema_operacional(self) -> str:
        try:
            so = platform.system()
            versao = platform.version()
            arquitectura = platform.machine()
            texto = f"Seu sistema operacional é {so} versão {versao}, arquitetura {arquitectura}."
            registrar("assistente", f"[SO] {so} {versao} {arquitectura}")
            db_memoria.registrar_comando("consulta", "sistema_operacional", texto)
            falar(texto)
            return texto
        except Exception as e:
            erro = f"Erro ao obter info do SO: {str(e)[:60]}"
            falar(erro)
            return erro

    def rede(self) -> str:
        try:
            hostname = socket.gethostname()
            interfaces = []
            import psutil
            net = psutil.net_if_addrs()
            stats = psutil.net_if_stats()
            for nome, addrs in net.items():
                for addr in addrs:
                    if addr.family == socket.AF_INET:
                        status = "ativada" if nome in stats and stats[nome].isup else "desativada"
                        interfaces.append(f"{nome}: {addr.address} ({status})")
                        break
            texto = f"Informações de rede:\n" + "\n".join(interfaces) if interfaces else "Nenhuma interface encontrada."
            registrar("assistente", f"[Rede] {hostname}: {texto}")
            falar(f"Encontrei {len(interfaces)} interface(s) de rede.")
            return texto
        except Exception as e:
            texto = f"Não consegui obter informações de rede: {str(e)[:80]}"
            falar(texto)
            return texto
