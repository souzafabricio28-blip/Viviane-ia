"""Super Banco de Dados para Acumulação de Conhecimento."""
from __future__ import annotations

import json
import logging
import re
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from core.memoria import memoria as db_memoria

log = logging.getLogger("Viviane.Knowledge")

_PALAVRAS_CHAVE = [
    "choveu", "chuvoso", "sol", "solsticio", "primavera", "verao", "outono", "inverno",
    "economia", "dolar", "euro", "bitcoin", "preco", "producao", "fabricacao", "recebimento",
    "nf-e", "nfe", "inventario", "inventario", "validade", "lote", "ean", "ean",
]

_TABELA_ENTIDADES = """
CREATE TABLE IF NOT EXISTS conhecimento_entidades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo TEXT NOT NULL,
    nome TEXT NOT NULL,
    valor TEXT,
    contexto TEXT DEFAULT '',
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_ent_tipo ON conhecimento_entidades(tipo);
CREATE INDEX IF NOT EXISTS idx_ent_nome ON conhecimento_entidades(nome);
"""

_TABELA_RELACOES = """
CREATE TABLE IF NOT EXISTS conhecimento_relacoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entidade_a_id INTEGER NOT NULL,
    entidade_b_id INTEGER NOT NULL,
    tipo_relacao TEXT DEFAULT 'relacionado',
    intensidade REAL DEFAULT 0.5,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_rel_a ON conhecimento_relacoes(entidade_a_id);
CREATE INDEX IF NOT EXISTS idx_rel_b ON conhecimento_relacoes(entidade_b_id);
"""

_TABELA_SINTESE = """
CREATE TABLE IF NOT EXISTS conhecimento_sinteses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    titulo TEXT NOT NULL,
    conteudo TEXT NOT NULL,
    fonte TEXT DEFAULT 'conversa',
    insights TEXT DEFAULT '[]',
    criacao_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_sintese_criacao ON conhecimento_sinteses(criacao_em);
"""


class KnowledgeBase:
    """Super banco de conhecimento com entidades, relações, síntese e memórias."""

    def __init__(self, arquivo: Path | None = None) -> None:
        self.arquivo = arquivo or db_memoria.arquivo.parent / "super_conhecimento.db"
        self._lock = threading.Lock()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.arquivo))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA encoding='UTF-8'")
        return conn

    def init(self) -> None:
        with self._lock, self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS conhecimento_entidades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tipo TEXT NOT NULL,
                    nome TEXT NOT NULL,
                    valor TEXT,
                    contexto TEXT DEFAULT '',
                    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_ent_tipo ON conhecimento_entidades(tipo);
                CREATE INDEX IF NOT EXISTS idx_ent_nome ON conhecimento_entidades(nome);

                CREATE TABLE IF NOT EXISTS conhecimento_relacoes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    entidade_a_id INTEGER NOT NULL,
                    entidade_b_id INTEGER NOT NULL,
                    tipo_relacao TEXT DEFAULT 'relacionado',
                    intensidade REAL DEFAULT 0.5,
                    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_rel_a ON conhecimento_relacoes(entidade_a_id);
                CREATE INDEX IF NOT EXISTS idx_rel_b ON conhecimento_relacoes(entidade_b_id);

                CREATE TABLE IF NOT EXISTS conhecimento_sinteses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    titulo TEXT NOT NULL,
                    conteudo TEXT NOT NULL,
                    fonte TEXT DEFAULT 'conversa',
                    insights TEXT DEFAULT '[]',
                    criacao_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_sintese_criacao ON conhecimento_sinteses(criacao_em);

                CREATE TABLE IF NOT EXISTS conhecimento_metricas (
                    chave TEXT PRIMARY KEY,
                    valor TEXT NOT NULL,
                    atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()

    # ── Entidades ────────────────────────────────────────────────────

    def salvar_entidade(self, tipo: str, nome: str, valor: str = "", contexto: str = "") -> int:
        with self._lock, self._conn() as conn:
            cur = conn.execute(
                """INSERT INTO conhecimento_entidades (tipo, nome, valor, contexto)
                   VALUES (?, ?, ?, ?)""",
                (tipo, nome, valor, contexto),
            )
            row_id = cur.lastrowid
            conn.execute(
                "UPDATE conhecimento_entidades SET atualizado_em = CURRENT_TIMESTAMP WHERE id = ?",
                (row_id,),
            )
            conn.commit()
            return row_id

    def buscar_entidade(self, nome: str, tipo: str = "") -> list[dict[str, Any]]:
        with self._lock, self._conn() as conn:
            if tipo:
                rows = conn.execute(
                    "SELECT id, tipo, nome, valor, contexto FROM conhecimento_entidades WHERE tipo = ? AND nome LIKE ?",
                    (tipo, f"%{nome}%"),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, tipo, nome, valor, contexto FROM conhecimento_entidades WHERE nome LIKE ?",
                    (f"%{nome}%",),
                ).fetchall()
            return [
                {"id": r[0], "tipo": r[1], "nome": r[2], "valor": r[3], "contexto": r[4]}
                for r in rows
            ]

    # ── Relações ──────────────────────────────────────────────────────

    def adicionar_relacao(self, id_a: int, id_b: int, tipo_relacao: str = "relacionado", intensidade: float = 0.5) -> int:
        with self._lock, self._conn() as conn:
            cur = conn.execute(
                """INSERT INTO conhecimento_relacoes (entidade_a_id, entidade_b_id, tipo_relacao, intensidade)
                   VALUES (?, ?, ?, ?)""",
                (id_a, id_b, tipo_relacao, intensidade),
            )
            conn.commit()
            return cur.lastrowid

    def relacoes_entidade(self, id_ent: int) -> list[dict[str, Any]]:
        with self._lock, self._conn() as conn:
            rows = conn.execute(
                """SELECT r.id, r.tipo_relacao, r.intensidade, e1.nome, e2.nome, e2.valor
                   FROM conhecimento_relacoes r
                   JOIN conhecimento_entidades e1 ON e1.id = r.entidade_a_id
                   JOIN conhecimento_entidades e2 ON e2.id = r.entidade_b_id
                   WHERE r.entidade_a_id = ? OR r.entidade_b_id = ?""",
                (id_ent, id_ent),
            ).fetchall()
            return [
                {
                    "id": r[0], "tipo": r[1], "intensidade": r[2],
                    "a": r[3], "b": r[4], "b_valor": r[5],
                }
                for r in rows
            ]

    # ── Síntese / Resumo ──────────────────────────────────────────────

    def salvar_sintese(self, titulo: str, conteudo: str, fonte: str = "conversa", insights: list[str] | None = None) -> int:
        with self._lock, self._conn() as conn:
            cur = conn.execute(
                """INSERT INTO conhecimento_sinteses (titulo, conteudo, fonte, insights)
                   VALUES (?, ?, ?, ?)""",
                (titulo, conteudo, fonte, json.dumps(insights or [], ensure_ascii=False)),
            )
            row_id = cur.lastrowid
            conn.commit()
            return row_id

    def listar_sinteses(self, limite: int = 20) -> list[dict[str, Any]]:
        with self._lock, self._conn() as conn:
            rows = conn.execute(
                "SELECT id, titulo, conteudo, fonte, insights, criacao_em FROM conhecimento_sinteses ORDER BY criacao_em DESC LIMIT ?",
                (limite,),
            ).fetchall()
            return [
                {
                    "id": r[0], "titulo": r[1], "conteudo": r[2], "fonte": r[3],
                    "insights": json.loads(r[4] or "[]"), "criado": r[5],
                }
                for r in rows
            ]

    # ── Métricas / Stats ─────────────────────────────────────────────

    def registrar_metrica(self, chave: str, valor: float) -> None:
        with self._lock, self._conn() as conn:
            conn.execute(
                """INSERT INTO conhecimento_metricas (chave, valor, atualizado_em)
                   VALUES (?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor, atualizado_em = CURRENT_TIMESTAMP""",
                (chave, str(valor)),
            )
            conn.commit()

    def metricas(self) -> dict[str, float]:
        with self._lock, self._conn() as conn:
            rows = conn.execute("SELECT chave, valor FROM conhecimento_metricas").fetchall()
            return {r[0]: float(r[1]) for r in rows if r[1]}

    # ── Sugestões de aprendizado ──────────────────────────────────────

    def sugerir_aprendizado(self, conversa: str) -> list[str]:
        """Gera sugestões de conhecimento a partir de uma conversa recente."""
        sugerencias = []
        linhas = [l for l in conversa.split("\n") if "|" in l or "[" in l]
        for l in linhas:
            l = l.strip()
            if l and len(l) > 20 and not l.startswith(("User", "AI", "ASSISTENTE", "ASSISTENTE")):
                sugerencias.append(l[:500])
        return sugerencias

    def processar_conversa(self, conversa: dict[str, str]) -> list[dict[str, Any]]:
        """Processa uma conversa e cria síntese automática de conhecimentos."""
        try:
            resumo = self._gerar_sintese_conversa(conversa)
            if resumo:
                titulo = f"Síntese: {conversa.get('u', 'Conversa')[:40]}"
                sintese_id = self.salvar_sintese(titulo, resumo, fonte="conversa_auto")
                return [{"sintese_id": sintese_id, "resumo": resumo}]
            return []
        except Exception as e:
            log.warning(f"Erro ao sintetizar conversa: {e}")
            return []

    def _gerar_sintese_conversa(self, conversa: dict[str, str]) -> str | None:
        texto = f"{conversa.get('u', '')}\n{conversa.get('d', '')}".strip()
        if len(texto) < 30:
            return None
        # Extrai fatos significativos (heurística simples)
        fatos = []
        for sent in re.split(r"[.!?]", texto):
            sent = sent.strip()
            if len(sent) > 20 and not sent.startswith(("Oi", "Ola", "Ola", "O", "A", "Sim", "Nao", "Não", "OK", "Ok", "Beleza", "beleza")):
                fatos.append(sent)
        return f"Fatos identificados: {' '.join(fatos)[:400]}" if fatos else None


kb = KnowledgeBase()
kb.init()
