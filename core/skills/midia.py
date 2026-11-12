from __future__ import annotations

import logging
import re
import subprocess
from pathlib import Path

from core.memoria import memoria as db_memoria
from core.voice import falar

log = logging.getLogger("Viviane")

_CREATE_NO_WINDOW = 0x08000000


def listar_audio_devices() -> str:
    try:
        ps = """
        $devices = @()
        $obj = Get-PnpDevice -Class AudioEndpoint -ErrorAction SilentlyContinue
        foreach ($d in $obj) {
            $devices += [PSCustomObject]@{
                Nome = $d.FriendlyName
                Status = $d.Status
                ID = $d.DeviceID
            }
        }
        $devices | ConvertTo-Json
        """
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True, text=True, timeout=15,
            creationflags=_CREATE_NO_WINDOW,
        )
        saida = result.stdout.strip()
        if saida:
            import json
            data = json.loads(saida)
            if not isinstance(data, list):
                data = [data]
            linhas = ["Dispositivos de audio:"]
            for d in data:
                status = "OK" if d.get("Status") == "OK" else d.get("Status", "?")
                linhas.append(f"- {d.get('Nome', '?')} [{status}]")
            db_memoria.registrar_comando("consulta", "audio_devices", str(linhas[:3]))
            return "\n".join(linhas)
        return "Nenhum dispositivo de audio encontrado."
    except Exception as e:
        log.warning(f"Erro ao listar audio: {e}")
        return f"Erro ao listar audio: {str(e)[:60]}"


def capturar_webcam() -> str:
    try:
        import cv2
        import numpy as np

        cam = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if not cam.isOpened():
            return "Nenhuma camera encontrada."

        cam.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        ret, frame = cam.read()
        cam.release()

        if not ret:
            return "Nao consegui capturar imagem da camera."

        pasta = Path.home() / "Pictures"
        pasta.mkdir(parents=True, exist_ok=True)
        caminho = pasta / "webcam_viviane.png"

        cv2.imwrite(str(caminho), frame)
        db_memoria.registrar_comando("webcam", "capturar", str(caminho))
        return f"Foto da webcam salva em {caminho}."

    except ImportError:
        return "Biblioteca de camera nao disponivel (opencv-python)."
    except Exception as e:
        log.warning(f"Erro na webcam: {e}")
        return f"Erro ao capturar webcam: {str(e)[:60]}"


def gravar_tela(duracao_seg: int = 5) -> str:
    try:
        import cv2
        import numpy as np
        import pyautogui
        import time

        pasta = Path.home() / "Videos"
        pasta.mkdir(parents=True, exist_ok=True)
        caminho = pasta / "gravacao_viviane.avi"

        screen_size = pyautogui.size()
        fourcc = cv2.VideoWriter_fourcc(*"XVID")
        fps = 10
        out = cv2.VideoWriter(str(caminho), fourcc, fps, screen_size)

        frames_total = max(1, duracao_seg * fps)
        for _ in range(frames_total):
            img = pyautogui.screenshot()
            frame = np.array(img)
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            out.write(frame)

        out.release()
        db_memoria.registrar_comando("screen_record", f"{duracao_seg}s", str(caminho))
        return f"Gravacao de {duracao_seg}s salva em {caminho}."

    except ImportError:
        return "Bibliotecas necessarias nao disponiveis."
    except Exception as e:
        log.warning(f"Erro na gravacao: {e}")
        return f"Erro ao gravar tela: {str(e)[:60]}"


def tirar_print() -> str:
    from core.skills.pc_control import ControladorPC
    pc = ControladorPC()
    pc._capturar_tela()
    return "Print salvo."
