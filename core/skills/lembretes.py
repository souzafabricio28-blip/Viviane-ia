from __future__ import annotations

import json
import subprocess
import sys
import webbrowser
from datetime import datetime, timedelta
from pathlib import Path

from core.settings import settings


class GerenciadorLembretes:
    def __init__(self) -> None:
        self.arquivo = settings.data_dir / "lembretes.json"
        self.lembretes: list[dict] = []
        self._carregar()

    def _carregar(self) -> None:
        if self.arquivo.exists():
            dados = json.loads(self.arquivo.read_text(encoding="utf-8"))
            self.lembretes = dados.get("lembretes", [])

    def salvar(self) -> None:
        self.arquivo.write_text(
            json.dumps({"lembretes": self.lembretes}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def criar(self, texto: str, minutos: int) -> None:
        hora = datetime.now() + timedelta(minutes=minutos)
        self.lembretes.append({
            "texto": texto,
            "hora": hora.isoformat(),
            "criado": datetime.now().isoformat(),
        })
        self.salvar()

    def verificar(self) -> list[dict]:
        agora = datetime.now()
        ativos = []
        vencidos = []
        for l in self.lembretes:
            if datetime.fromisoformat(l["hora"]) <= agora:
                vencidos.append(l)
            else:
                ativos.append(l)
        self.lembretes = ativos
        self.salvar()
        return vencidos
