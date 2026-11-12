from __future__ import annotations

import psutil

from core.voice import falar
from core.conversa import registrar


class DiagnosticoSistema:
    def relatorio_completo(self) -> str:
        falar("A verificar os sistemas centrais...")

        try:
            uso_cpu = psutil.cpu_percent(interval=1)

            memoria = psutil.virtual_memory()
            uso_ram = memoria.percent
            ram_livre_gb = memoria.available / (1024 ** 3)

            bateria = psutil.sensors_battery()
            info_bateria = ""
            if bateria:
                info_bateria = f" O nível de bateria é de {bateria.percent} por cento."
                if bateria.power_plugged:
                    info_bateria += " A máquina está ligada à corrente elétrica."
                else:
                    info_bateria += " A funcionar com energia da bateria."

            relatorio = (
                f"Os meus sensores térmicos diretos estão bloqueados pelo sistema operativo, "
                f"mas posso informar que o processador está a operar a {uso_cpu:.0f} por cento da capacidade de esforço. "
                f"A memória RAM está com {uso_ram:.0f} por cento de carga, "
                f"restando {ram_livre_gb:.1f} gigabytes livres."
                f"{info_bateria}"
            )

            registrar("assistente", f"[Diagnóstico] CPU: {uso_cpu}%, RAM: {uso_ram}%")
            falar(relatorio)
            return relatorio

        except Exception as e:
            erro = f"Não foi possível ler os sensores do sistema. Erro: {str(e)}"
            registrar("assistente", erro)
            falar("Ocorreu uma falha ao aceder aos sensores do sistema.")
            return "Ocorreu uma falha ao aceder aos sensores do sistema."
