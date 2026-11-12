from __future__ import annotations

import json
import re
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from core.settings import settings

_lock = threading.Lock()

_PATTERN_KNOWLEDGE = re.compile(r'\[KNOWLEDGE:\s*(.+?)\|(.+?)(?:\|(.+?))?\]')


class Memoria:
    def __init__(self) -> None:
        self.arquivo: Path = settings.data_dir / "memoria.db"
        self._inicializar()

    def _inicializar(self) -> None:
        with _lock, sqlite3.connect(str(self.arquivo)) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA encoding='UTF-8'")
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS conversas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role TEXT NOT NULL,
                    conteudo TEXT NOT NULL,
                    metadata TEXT DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS memorias (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    titulo TEXT NOT NULL,
                    conteudo TEXT NOT NULL,
                    tipo TEXT DEFAULT 'facto',
                    tags TEXT DEFAULT '',
                    importancia INTEGER DEFAULT 1,
                    fonte TEXT DEFAULT '',
                    access_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS perfil (
                    chave TEXT PRIMARY KEY,
                    valor TEXT NOT NULL,
                    tipo TEXT DEFAULT 'texto',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS padroes_uso (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    comando TEXT NOT NULL,
                    intent TEXT DEFAULT '',
                    success INTEGER DEFAULT 1,
                    hora INTEGER,
                    dia_semana INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE VIRTUAL TABLE IF NOT EXISTS memorias_fts USING fts5(
                    titulo, conteudo, tags,
                    content='memorias',
                    content_rowid='id'
                );

                CREATE INDEX IF NOT EXISTS idx_conversas_data ON conversas(created_at);
                CREATE INDEX IF NOT EXISTS idx_memorias_tipo ON memorias(tipo);
                CREATE INDEX IF NOT EXISTS idx_memorias_importancia ON memorias(importancia);
                CREATE INDEX IF NOT EXISTS idx_padroes_comando ON padroes_uso(comando);

                CREATE TABLE IF NOT EXISTS comandos_executados (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tipo TEXT NOT NULL,
                    comando TEXT NOT NULL,
                    resultado TEXT DEFAULT '',
                    detalhes TEXT DEFAULT '',
                    success INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_comandos_data ON comandos_executados(created_at);
                CREATE INDEX IF NOT EXISTS idx_comandos_tipo ON comandos_executados(tipo);
            """)
            conn.commit()

    # ── Conversas ──────────────────────────────────────────────────────

    def registrar_conversa(self, role: str, conteudo: str, metadata: dict | None = None) -> int:
        with _lock, sqlite3.connect(str(self.arquivo)) as conn:
            cur = conn.execute(
                "INSERT INTO conversas (role, conteudo, metadata) VALUES (?, ?, ?)",
                (role, conteudo, json.dumps(metadata or {}, ensure_ascii=False)),
            )
            conn.commit()
            return cur.lastrowid

    def historico_conversas(self, limite: int = 50) -> list[dict]:
        with _lock, sqlite3.connect(str(self.arquivo)) as conn:
            rows = conn.execute(
                "SELECT id, role, conteudo, created_at FROM conversas ORDER BY id DESC LIMIT ?",
                (limite,),
            ).fetchall()
            return [
                {"id": r[0], "role": r[1], "conteudo": r[2], "data": r[3]}
                for r in reversed(rows)
            ]

    def limpar_conversas(self) -> None:
        with _lock, sqlite3.connect(str(self.arquivo)) as conn:
            conn.execute("DELETE FROM conversas")
            conn.commit()

    # ── Memórias ───────────────────────────────────────────────────────

    def salvar_memoria(
        self,
        titulo: str,
        conteudo: str,
        tipo: str = "facto",
        tags: str = "",
        importancia: int = 1,
        fonte: str = "",
    ) -> int:
        with _lock, sqlite3.connect(str(self.arquivo)) as conn:
            cur = conn.execute(
                """INSERT INTO memorias (titulo, conteudo, tipo, tags, importancia, fonte)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (titulo, conteudo, tipo, tags, importancia, fonte),
            )
            row_id = cur.lastrowid
            if row_id:
                try:
                    conn.execute(
                        "INSERT INTO memorias_fts (rowid, titulo, conteudo, tags) VALUES (?, ?, ?, ?)",
                        (row_id, titulo, conteudo, tags),
                    )
                except sqlite3.OperationalError:
                    pass
            conn.commit()
            return row_id

    def buscar_memorias(self, termo: str, limite: int = 10) -> list[dict]:
        with _lock, sqlite3.connect(str(self.arquivo)) as conn:
            try:
                rows = conn.execute(
                    """SELECT m.id, m.titulo, m.conteudo, m.tipo, m.tags,
                              m.importancia, m.fonte, m.access_count, m.created_at
                       FROM memorias_fts f
                       JOIN memorias m ON f.rowid = m.id
                       WHERE memorias_fts MATCH ?
                       ORDER BY rank
                       LIMIT ?""",
                    (termo, limite),
                ).fetchall()
            except sqlite3.OperationalError:
                rows = conn.execute(
                    """SELECT m.id, m.titulo, m.conteudo, m.tipo, m.tags,
                              m.importancia, m.fonte, m.access_count, m.created_at
                       FROM memorias m
                       WHERE m.titulo LIKE ? OR m.conteudo LIKE ? OR m.tags LIKE ?
                       ORDER BY m.importancia DESC
                       LIMIT ?""",
                    (f"%{termo}%", f"%{termo}%", f"%{termo}%", limite),
                ).fetchall()

            resultados = []
            for r in rows:
                conn.execute("UPDATE memorias SET access_count = access_count + 1 WHERE id = ?", (r[0],))
                resultados.append({
                    "id": r[0],
                    "titulo": r[1],
                    "conteudo": r[2],
                    "tipo": r[3],
                    "tags": r[4],
                    "importancia": r[5],
                    "fonte": r[6],
                    "acessos": r[7] + 1,
                    "criado": r[8],
                })
            conn.commit()
            return resultados

    def listar_memorias(self, tipo: str | None = None, limite: int = 50) -> list[dict]:
        with _lock, sqlite3.connect(str(self.arquivo)) as conn:
            if tipo:
                rows = conn.execute(
                    """SELECT id, titulo, conteudo, tipo, tags, importancia, fonte, access_count, created_at
                       FROM memorias WHERE tipo = ? ORDER BY importancia DESC, access_count DESC LIMIT ?""",
                    (tipo, limite),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT id, titulo, conteudo, tipo, tags, importancia, fonte, access_count, created_at
                       FROM memorias ORDER BY importancia DESC, access_count DESC LIMIT ?""",
                    (limite,),
                ).fetchall()
            return [
                {
                    "id": r[0],
                    "titulo": r[1],
                    "conteudo": r[2],
                    "tipo": r[3],
                    "tags": r[4],
                    "importancia": r[5],
                    "fonte": r[6],
                    "acessos": r[7],
                    "criado": r[8],
                }
                for r in rows
            ]

    def remover_memoria(self, memoria_id: int) -> bool:
        with _lock, sqlite3.connect(str(self.arquivo)) as conn:
            conn.execute("DELETE FROM memorias_fts WHERE rowid = ?", (memoria_id,))
            conn.execute("DELETE FROM memorias WHERE id = ?", (memoria_id,))
            conn.commit()
            return conn.total_changes > 0

    # ── Perfil ─────────────────────────────────────────────────────────

    def definir_perfil(self, chave: str, valor: Any, tipo: str = "texto") -> None:
        str_valor = json.dumps(valor, ensure_ascii=False) if tipo == "json" else str(valor)
        with _lock, sqlite3.connect(str(self.arquivo)) as conn:
            conn.execute(
                """INSERT INTO perfil (chave, valor, tipo, updated_at)
                   VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(chave) DO UPDATE SET
                       valor = excluded.valor,
                       tipo = excluded.tipo,
                       updated_at = CURRENT_TIMESTAMP""",
                (chave, str_valor, tipo),
            )
            conn.commit()

    def obter_perfil(self, chave: str, default: Any = None) -> Any:
        with _lock, sqlite3.connect(str(self.arquivo)) as conn:
            row = conn.execute(
                "SELECT valor, tipo FROM perfil WHERE chave = ?", (chave,)
            ).fetchone()
            if row:
                if row[1] == "json":
                    return json.loads(row[0])
                return row[0]
            return default

    def listar_perfil(self) -> dict[str, Any]:
        with _lock, sqlite3.connect(str(self.arquivo)) as conn:
            rows = conn.execute(
                "SELECT chave, valor, tipo FROM perfil ORDER BY chave"
            ).fetchall()
            resultado = {}
            for r in rows:
                if r[2] == "json":
                    resultado[r[0]] = json.loads(r[1])
                else:
                    resultado[r[0]] = r[1]
            return resultado

    def remover_perfil(self, chave: str) -> bool:
        with _lock, sqlite3.connect(str(self.arquivo)) as conn:
            conn.execute("DELETE FROM perfil WHERE chave = ?", (chave,))
            conn.commit()
            return conn.total_changes > 0

    # ── Padrões de Uso ────────────────────────────────────────────────

    def registrar_padrao(self, comando: str, intent: str = "", success: bool = True) -> None:
        agora = datetime.now()
        with _lock, sqlite3.connect(str(self.arquivo)) as conn:
            conn.execute(
                """INSERT INTO padroes_uso (comando, intent, success, hora, dia_semana)
                   VALUES (?, ?, ?, ?, ?)""",
                (comando, intent, 1 if success else 0, agora.hour, agora.weekday()),
            )
            conn.commit()

    def comandos_frequentes(self, limite: int = 20) -> list[dict]:
        with _lock, sqlite3.connect(str(self.arquivo)) as conn:
            rows = conn.execute(
                """SELECT comando, intent, COUNT(*) as freq,
                          SUM(CASE WHEN success=1 THEN 1 ELSE 0 END) as sucessos,
                          ROUND(AVG(success)*100, 1) as taxa_sucesso
                   FROM padroes_uso
                   GROUP BY comando
                   ORDER BY freq DESC
                   LIMIT ?""",
                (limite,),
            ).fetchall()
            return [
                {
                    "comando": r[0],
                    "intent": r[1],
                    "frequencia": r[2],
                    "sucessos": r[3],
                    "taxa_sucesso": r[4],
                }
                for r in rows
            ]

    # ── Comandos Executados ─────────────────────────────────────────────

    def registrar_comando(self, tipo: str, comando: str, resultado: str = "", detalhes: str = "", success: bool = True) -> int:
        with _lock, sqlite3.connect(str(self.arquivo)) as conn:
            cur = conn.execute(
                """INSERT INTO comandos_executados (tipo, comando, resultado, detalhes, success)
                   VALUES (?, ?, ?, ?, ?)""",
                (tipo, comando, resultado[:500], detalhes[:500], 1 if success else 0),
            )
            conn.commit()
            return cur.lastrowid

    def ultimos_comandos(self, limite: int = 20) -> list[dict]:
        with _lock, sqlite3.connect(str(self.arquivo)) as conn:
            rows = conn.execute(
                """SELECT id, tipo, comando, resultado, detalhes, success, created_at
                   FROM comandos_executados ORDER BY id DESC LIMIT ?""",
                (limite,),
            ).fetchall()
            return [
                {"id": r[0], "tipo": r[1], "comando": r[2], "resultado": r[3],
                 "detalhes": r[4], "success": bool(r[5]), "data": r[6]}
                for r in rows
            ]

    # ── Gerenciamento de Espaço ─────────────────────────────────────────

    def db_tamanho_mb(self) -> float:
        try:
            return self.arquivo.stat().st_size / (1024 * 1024)
        except Exception:
            return 0.0

    def db_contagem(self) -> dict[str, int]:
        with _lock, sqlite3.connect(str(self.arquivo)) as conn:
            return {
                "conversas": conn.execute("SELECT COUNT(*) FROM conversas").fetchone()[0],
                "memorias": conn.execute("SELECT COUNT(*) FROM memorias").fetchone()[0],
                "comandos": conn.execute("SELECT COUNT(*) FROM comandos_executados").fetchone()[0],
                "padroes": conn.execute("SELECT COUNT(*) FROM padroes_uso").fetchone()[0],
            }

    # ── Utilitários ─────────────────────────────────────────────────────

    def contexto_para_ia(self, limite_conversas: int = 10, limite_memorias: int = 5) -> str:
        """Gera um bloco de contexto para injetar no prompt da IA."""
        partes = []

        # Perfil
        perfil = self.listar_perfil()
        if perfil:
            partes.append("[PERFIL DO USUARIO]")
            for k, v in perfil.items():
                partes.append(f"  {k}: {v}")
            partes.append("")

        # Memorias relevantes recentes
        memorias = self.listar_memorias(limite=limite_memorias)
        if memorias:
            partes.append("[MEMORIAS APRENDIDAS]")
            for m in memorias:
                if m["tipo"] == "facto":
                    partes.append(f"  - {m['titulo']}: {m['conteudo']}")
                elif m["tipo"] == "preferencia":
                    partes.append(f"  - Preferencia: {m['titulo']} -> {m['conteudo']}")
                elif m["tipo"] == "pessoa":
                    partes.append(f"  - Sobre {m['titulo']}: {m['conteudo']}")
                else:
                    partes.append(f"  - [{m['tipo']}] {m['titulo']}: {m['conteudo']}")
            partes.append("")

        # Últimas conversas
        conversas = self.historico_conversas(limite=limite_conversas)
        if conversas:
            partes.append("[ULTIMAS CONVERSAS]")
            for c in conversas:
                prefixo = "USUARIO" if c["role"] == "user" else settings.assistant_name
                partes.append(f"  {prefixo}: {c['conteudo']}")
            partes.append("")

        return "\n".join(partes)

    @staticmethod
    def extrair_knowledge(texto: str) -> list[dict[str, str]]:
        """Extrai marcadores [KNOWLEDGE: titulo|conteudo|bloco] do texto."""
        resultados = []
        for match in _PATTERN_KNOWLEDGE.finditer(texto):
            titulo = match.group(1).strip()
            conteudo = match.group(2).strip()
            bloco = (match.group(3) or "Geral").strip()
            resultados.append({"titulo": titulo, "conteudo": conteudo, "bloco": bloco})
        return resultados

    @staticmethod
    def remover_knowledge(texto: str) -> str:
        """Remove os marcadores [KNOWLEDGE] do texto."""
        return _PATTERN_KNOWLEDGE.sub("", texto).strip()

    def auto_aprender(self, resposta_ia: str, fonte: str = "conversa") -> list[str]:
        """Processa a resposta da IA, extrai [KNOWLEDGE] e salva como memória."""
        conhecimentos = self.extrair_knowledge(resposta_ia)
        salvos = []
        for k in conhecimentos:
            tipo = self._detectar_tipo(k["titulo"], k["bloco"])
            self.salvar_memoria(
                titulo=k["titulo"],
                conteudo=k["conteudo"],
                tipo=tipo,
                tags=k["bloco"],
                importancia=3 if tipo == "preferencia" else 2,
                fonte=fonte,
            )
            salvos.append(k["titulo"])
        return salvos

    @staticmethod
    def _detectar_tipo(titulo: str, bloco: str) -> str:
        bloco_lower = bloco.lower()
        titulo_lower = titulo.lower()
        if "preferencia" in bloco_lower or "gosto" in bloco_lower:
            return "preferencia"
        if "pessoa" in bloco_lower or "familia" in bloco_lower or "amigo" in bloco_lower:
            return "pessoa"
        if "data" in bloco_lower or "evento" in bloco_lower or "aniversario" in bloco_lower:
            return "data"
        if titulo_lower.startswith("comando ") or "comando" in bloco_lower:
            return "comando"
        return "facto"


# Instância global
memoria = Memoria()
