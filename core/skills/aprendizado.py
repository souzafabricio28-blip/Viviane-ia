from __future__ import annotations

import json
import logging
import re
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.routing.intents import chave_aprendivel, intent_valido, normalizar_intent, sanitizar_comandos
from core.settings import settings

log = logging.getLogger("Viviane.Aprendizado")


@dataclass
class ComandoAprendido:
    comando: str
    intent: str
    parametros: dict
    contexto: dict = field(default_factory=dict)  # hora, local, dispositivo ativo, etc
    contador: int = 1
    criado_em: float = field(default_factory=time.time)
    atualizado_em: float = field(default_factory=time.time)
    taxa_sucesso: float = 1.0
    feedback_positivo: int = 0
    feedback_negativo: int = 0


@dataclass
class PadraoUsuario:
    """Padrões de uso do usuário para personalização."""
    horarios_ativos: Counter = field(default_factory=Counter)  # hora -> frequência
    comandos_por_hora: dict[int, Counter] = field(default_factory=dict)  # hora -> {comando: count}
    apps_frequentes: Counter = field(default_factory=Counter)
    topicos_interesse: Counter = field(default_factory=Counter)
    frases_comuns: Counter = field(default_factory=Counter)
    preferencias: dict = field(default_factory=dict)
    ultima_atualizacao: float = field(default_factory=time.time)


class AprendizadoContinuo:
    """
    Sistema de aprendizado contínuo que melhora a cada interação.
    - Aprende comandos e intents
    - Detecta padrões de uso
    - Personaliza respostas
    - Auto-corige baseado em feedback
    """

    def __init__(self) -> None:
        self.caminho = settings.data_dir / "comandos_aprendidos.json"
        self.caminho_padroes = settings.data_dir / "padroes_usuario.json"
        self.pendentes = settings.data_dir / "comandos_pendentes.txt"
        self.feedback_log = settings.data_dir / "feedback_log.jsonl"

        self.comandos: dict[str, ComandoAprendido] = {}
        self.padroes = PadraoUsuario()
        self._carregar()
        self._sanitizar()

    # -------------------------------------------------------------------------
    # Persistência
    # -------------------------------------------------------------------------

    def _carregar(self):
        try:
            if self.caminho.exists():
                with open(self.caminho, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for k, v in data.items():
                    if isinstance(v, dict) and "intent" in v:
                        self.comandos[k] = ComandoAprendido(
                            comando=k,
                            intent=v.get("intent", "conversa"),
                            parametros=v.get("parametros", {}),
                            contexto=v.get("contexto", {}),
                            contador=v.get("contador", 1),
                            criado_em=v.get("criado_em", time.time()),
                            atualizado_em=v.get("atualizado_em", time.time()),
                            taxa_sucesso=v.get("taxa_sucesso", 1.0),
                            feedback_positivo=v.get("feedback_positivo", 0),
                            feedback_negativo=v.get("feedback_negativo", 0),
                        )
                    elif isinstance(v, dict):  # formato antigo
                        self.comandos[k] = ComandoAprendido(
                            comando=k, intent=v.get("intent", "conversa"), parametros=v.get("parametros", {})
                        )
        except Exception as e:
            log.warning(f"Erro ao carregar comandos aprendidos: {e}")

        try:
            if self.caminho_padroes.exists():
                with open(self.caminho_padroes, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.padroes.horarios_ativos = Counter(data.get("horarios_ativos", {}))
                self.padroes.comandos_por_hora = {
                    int(k): Counter(v) for k, v in data.get("comandos_por_hora", {}).items()
                }
                self.padroes.apps_frequentes = Counter(data.get("apps_frequentes", {}))
                self.padroes.topicos_interesse = Counter(data.get("topicos_interesse", {}))
                self.padroes.frases_comuns = Counter(data.get("frases_comuns", {}))
                self.padroes.preferencias = data.get("preferencias", {})
                self.padroes.ultima_atualizacao = data.get("ultima_atualizacao", time.time())
        except Exception as e:
            log.warning(f"Erro ao carregar padrões: {e}")

    def _salvar(self):
        try:
            data = {}
            for k, v in self.comandos.items():
                data[k] = {
                    "intent": v.intent,
                    "parametros": v.parametros,
                    "contexto": v.contexto,
                    "contador": v.contador,
                    "criado_em": v.criado_em,
                    "atualizado_em": v.atualizado_em,
                    "taxa_sucesso": v.taxa_sucesso,
                    "feedback_positivo": v.feedback_positivo,
                    "feedback_negativo": v.feedback_negativo,
                }
            with open(self.caminho, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            log.warning(f"Erro ao salvar comandos: {e}")

        try:
            data = {
                "horarios_ativos": dict(self.padroes.horarios_ativos),
                "comandos_por_hora": {str(k): dict(v) for k, v in self.padroes.comandos_por_hora.items()},
                "apps_frequentes": dict(self.padroes.apps_frequentes),
                "topicos_interesse": dict(self.padroes.topicos_interesse),
                "frases_comuns": dict(self.padroes.frases_comuns),
                "preferencias": self.padroes.preferencias,
                "ultima_atualizacao": self.padroes.ultima_atualizacao,
            }
            with open(self.caminho_padroes, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            log.warning(f"Erro ao salvar padrões: {e}")

    def _sanitizar(self):
        original = len(self.comandos)
        self.comandos = sanitizar_comandos(self.comandos)
        if len(self.comandos) != original:
            log.info(f"Sanitização: {original - len(self.comandos)} entradas removidas")
            self._salvar()

    def carregar(self) -> dict:
        """Compatibilidade: retorna dict simples para código antigo."""
        return {k: {"intent": v.intent, "parametros": v.parametros} for k, v in self.comandos.items()}

    # -------------------------------------------------------------------------
    # Aprendizado de Comandos
    # -------------------------------------------------------------------------

    def aprender(self, comando: str, intent: str, parametros: dict, contexto: dict | None = None) -> bool:
        """Aprende ou reforça um comando."""
        chave = comando.lower().strip()
        if not chave_aprendivel(chave):
            return False

        norm = normalizar_intent(intent, parametros)
        if norm is None:
            return False

        intent_ok, params_ok = norm
        if not intent_valido(intent_ok):
            return False

        agora = time.time()
        hora_atual = time.localtime().tm_hour

        if chave in self.comandos:
            c = self.comandos[chave]
            c.contador += 1
            c.atualizado_em = agora
            # Atualiza intent se diferente e confiança alta
            if c.intent != intent_ok and c.contador > 3:
                c.intent = intent_ok
                c.parametros = params_ok
        else:
            c = ComandoAprendido(
                comando=chave,
                intent=intent_ok,
                parametros=params_ok,
                contexto=contexto or {},
                criado_em=agora,
                atualizado_em=agora,
            )
            self.comandos[chave] = c

        # Atualiza padrões de uso
        self.padroes.horarios_ativos[hora_atual] += 1
        if hora_atual not in self.padroes.comandos_por_hora:
            self.padroes.comandos_por_hora[hora_atual] = Counter()
        self.padroes.comandos_por_hora[hora_atual][chave] += 1

        # Extrai tópicos de interesse
        self._extrair_topicos(comando)

        self._salvar()
        log.info(f"Comando aprendido/reforçado: {chave[:50]} -> {intent_ok}")
        return True

    def _extrair_topicos(self, texto: str):
        """Extrai palavras-chave relevantes do texto."""
        stopwords = {"o", "a", "os", "as", "um", "uma", "de", "do", "da", "dos", "das", "em", "no", "na", "nos", "nas",
                     "para", "por", "com", "sem", "sob", "sobre", "entre", "após", "até", "desde", "como", "que", "qual",
                     "quais", "quando", "onde", "porque", "porquê", "por quê", "e", "ou", "mas", "se", "então", "logo",
                     "meu", "minha", "meus", "minhas", "seu", "sua", "seus", "suas", "nosso", "nossa", "nossos", "nossas",
                     "teu", "tua", "teus", "tuas", "dele", "dela", "deles", "delas", "isto", "isso", "aquilo", "aqui", "ali",
                     "lá", "cá", "agora", "hoje", "amanhã", "ontem", "sempre", "nunca", "já", "ainda", "também", "bem", "mal",
                     "muito", "pouco", "mais", "menos", "tudo", "nada", "algo", "alguém", "ninguém", "cada", "todo", "toda"}
        palavras = re.findall(r"\b[a-záéíóúâêôãõç]{3,}\b", texto.lower())
        for p in palavras:
            if p not in stopwords and len(p) > 3:
                self.padroes.topicos_interesse[p] += 1
        # Frases curtas comuns
        if len(texto.split()) <= 6:
            self.padroes.frases_comuns[texto.lower().strip()] += 1

    def registrar_desconhecido(self, comando: str) -> None:
        if not chave_aprendivel(comando):
            return
        try:
            with open(self.pendentes, "a", encoding="utf-8") as f:
                f.write(f"{comando}\n")
        except Exception:
            pass

    def obter_sugestao(self, comando_parcial: str, limite: int = 5) -> list[str]:
        """Sugere comandos baseados no histórico e contexto atual."""
        hora = time.localtime().tm_hour
        chave = comando_parcial.lower().strip()

        sugestoes = []

        # 1. Comandos que começam com o parcial
        for cmd in self.comandos:
            if cmd.startswith(chave) and cmd != chave:
                sugestoes.append(cmd)

        # 2. Comandos frequentes na hora atual
        if hora in self.padroes.comandos_por_hora:
            for cmd, _ in self.padroes.comandos_por_hora[hora].most_common(3):
                if cmd not in sugestoes and cmd.startswith(chave):
                    sugestoes.append(cmd)

        # 3. Comandos globais mais frequentes
        for cmd, c in sorted(self.comandos.items(), key=lambda x: x[1].contador, reverse=True)[:10]:
            if cmd not in sugestoes and cmd.startswith(chave):
                sugestoes.append(cmd)

        return sugestoes[:limite]

    def prever_proximo_comando(self, contexto: dict | None = None) -> list[str]:
        """Prevê próximo comando baseado em padrões."""
        hora = time.localtime().tm_hour
        sugestoes = []

        if hora in self.padroes.comandos_por_hora:
            for cmd, _ in self.padroes.comandos_por_hora[hora].most_common(5):
                sugestoes.append(cmd)

        # Apps frequentes
        for app, _ in self.padroes.apps_frequentes.most_common(3):
            sugestoes.append(f"abrir {app}")

        return sugestoes[:5]

    # -------------------------------------------------------------------------
    # Feedback e Auto-correção
    # -------------------------------------------------------------------------

    def registrar_feedback(self, comando: str, positivo: bool) -> None:
        """Registra feedback do usuário para ajustar confiança."""
        chave = comando.lower().strip()
        if chave not in self.comandos:
            return

        c = self.comandos[chave]
        if positivo:
            c.feedback_positivo += 1
        else:
            c.feedback_negativo += 1

        total = c.feedback_positivo + c.feedback_negativo
        if total > 0:
            c.taxa_sucesso = c.feedback_positivo / total
            # Se taxa baixa, marca para revisão
            if c.taxa_sucesso < 0.3 and c.contador > 5:
                log.warning(f"Comando com baixa taxa de sucesso: {chave} ({c.taxa_sucesso:.0%})")

        self._salvar()
        self._log_feedback(chave, positivo)

    def _log_feedback(self, comando: str, positivo: bool):
        try:
            entry = {
                "timestamp": time.time(),
                "comando": comando,
                "positivo": positivo,
            }
            with open(self.feedback_log, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def auto_corrigir(self) -> int:
        """Remove ou corrige comandos com performance consistentemente ruim."""
        removidos = 0
        for chave, c in list(self.comandos.items()):
            if c.contador >= 10 and c.taxa_sucesso < 0.2:
                # Comando consistentemente falhando
                del self.comandos[chave]
                removidos += 1
                log.info(f"Auto-removido comando falho: {chave}")
        if removidos:
            self._salvar()
        return removidos

    # -------------------------------------------------------------------------
    # Personalização
    # -------------------------------------------------------------------------

    def registrar_app_uso(self, app: str):
        self.padroes.apps_frequentes[app.lower()] += 1
        self.padroes.ultima_atualizacao = time.time()
        if self.padroes.apps_frequentes.total() % 10 == 0:
            self._salvar()

    def registrar_topico(self, topico: str):
        self.padroes.topicos_interesse[topico.lower()] += 1
        self.padroes.ultima_atualizacao = time.time()

    def definir_preferencia(self, chave: str, valor: Any):
        self.padroes.preferencias[chave] = valor
        self._salvar()

    def obter_preferencia(self, chave: str, default: Any = None) -> Any:
        return self.padroes.preferencias.get(chave, default)

    def obter_estatisticas(self) -> dict:
        return {
            "comandos_aprendidos": len(self.comandos),
            "comandos_pendentes": self._contar_pendentes(),
            "horario_mais_ativo": self.padroes.horarios_ativos.most_common(1)[0] if self.padroes.horarios_ativos else None,
            "topicos_top": self.padroes.topicos_interesse.most_common(10),
            "apps_top": self.padroes.apps_frequentes.most_common(10),
            "frases_comuns": self.padroes.frases_comuns.most_common(10),
            "taxa_sucesso_media": sum(c.taxa_sucesso for c in self.comandos.values()) / len(self.comandos) if self.comandos else 0,
        }

    def _contar_pendentes(self) -> int:
        try:
            if self.pendentes.exists():
                return len(self.pendentes.read_text().strip().split("\n"))
        except Exception:
            pass
        return 0

    def exportar_conhecimento(self) -> dict:
        """Exporta todo o aprendizado para backup/migração."""
        return {
            "comandos": {k: {
                "intent": v.intent,
                "parametros": v.parametros,
                "contador": v.contador,
                "taxa_sucesso": v.taxa_sucesso,
            } for k, v in self.comandos.items()},
            "padroes": {
                "horarios_ativos": dict(self.padroes.horarios_ativos),
                "topicos": dict(self.padroes.topicos_interesse.most_common(50)),
                "apps": dict(self.padroes.apps_frequentes.most_common(20)),
                "preferencias": self.padroes.preferencias,
            },
            "exportado_em": time.time(),
        }

    def importar_conhecimento(self, data: dict) -> int:
        """Importa conhecimento de backup."""
        count = 0
        for k, v in data.get("comandos", {}).items():
            if k not in self.comandos:
                self.comandos[k] = ComandoAprendido(
                    comando=k,
                    intent=v.get("intent", "conversa"),
                    parametros=v.get("parametros", {}),
                    contador=v.get("contador", 1),
                    taxa_sucesso=v.get("taxa_sucesso", 1.0),
                )
                count += 1
        for k, v in data.get("padroes", {}).get("topicos", {}).items():
            self.padroes.topicos_interesse[k] += v
        for k, v in data.get("padroes", {}).get("apps", {}).items():
            self.padroes.apps_frequentes[k] += v
        for k, v in data.get("padroes", {}).get("preferencias", {}).items():
            self.padroes.preferencias[k] = v
        self._salvar()
        return count


# Instância global
aprendizado = AprendizadoContinuo()


# Funções de compatibilidade com código antigo
def carregar() -> dict:
    return {k: {"intent": v.intent, "parametros": v.parametros} for k, v in aprendizado.comandos.items()}


def aprender(comando: str, intent: str, parametros: dict) -> bool:
    return aprendizado.aprender(comando, intent, parametros)


def registrar_desconhecido(comando: str) -> None:
    aprendizado.registrar_desconhecido(comando)