from __future__ import annotations

import logging
import re
import threading
import time

import psutil

from core.actions.atalhos import eh_comando_parar, parar_tudo, resolver_atalho
from core.actions.context import ActionContext
from core.actions.dispatch import dispatch
from core.conhecimento import BaseConhecimento
from core.conversa import registrar
from core.llm.brain import Cerebro, _reclassificar_como_sistema, _tem_recusa
from core.memoria import memoria as db_memoria
from core.nucleus import nucleo
from core.settings import settings
from core.skills.clima import PrevisaoTempo
from core.skills.diagnostico import DiagnosticoSistema
from core.skills.lembretes import GerenciadorLembretes
from core.skills.noticias import Noticias
from core.skills.pc_control import ControladorPC
from core.skills.sistema import InfoSistema
from core.skills.wake_word import wake_word_manager
from core.skills.saber import saber
from core.voice import GravadorVoz, falar

log = logging.getLogger("Viviane")


def _desligar_tudo() -> None:
    import os
    os._exit(0)


class Assistente:
    def __init__(self, *, modo_web: bool = False) -> None:
        self.modo_web = modo_web
        self.cerebro = Cerebro()
        self.voz = GravadorVoz()
        self.pc = ControladorPC()
        self.lembretes = GerenciadorLembretes()
        self.clima = PrevisaoTempo()
        self.noticias = Noticias()
        self.diagnostico = DiagnosticoSistema()
        self.info_sistema = InfoSistema()
        self.conhecimento = BaseConhecimento()
        self.ativo = True
        self._ultima_fala = 0.0
        self._wake_word_ativo = False
        self.thread_lembretes = threading.Thread(
            target=self._verificar_lembretes, daemon=True
        )
        self.thread_monitorizacao = threading.Thread(
            target=self._monitorizar_sistema, daemon=True
        )
        self.thread_varredura = threading.Thread(
            target=self._varredura_programas, daemon=True
        )
        self._ultima_varredura: list[dict] = []
        try:
            nucleo.initialize()
        except Exception as exc:
            log.debug("Nucleo nao iniciou: %s", exc)

        # Wake word - apenas no modo console (não web)
        if not modo_web and wake_word_manager.enabled:
            wake_word_manager.set_activation_callback(self._on_wake_word)
            wake_word_manager.start()
            self._wake_word_ativo = True
            log.info("Wake word ativado: " + wake_word_manager.current_keyword)

    def iniciar(self) -> None:
        falar(f"Pronto.")
        self.thread_lembretes.start()
        self.thread_monitorizacao.start()
        self.thread_varredura.start()
        self._loop_principal()

    def _on_wake_word(self):
        """Callback quando wake word é detectada."""
        if not self.ativo:
            return
        log.info("Wake word detectada - ativando escuta")
        # Toca som de confirmação
        try:
            import ctypes
            ctypes.windll.winmm.Beep(880, 100)
        except Exception:
            pass
        # Escuta comando após wake word
        comando = self.voz.ouvir_comando()
        if comando:
            self._executar_comando(comando)

    def _loop_principal(self) -> None:
        print(f"\nViviane aguardando comandos... (Wake word: '{wake_word_manager.current_keyword}')")
        while self.ativo:
            try:
                if self._wake_word_ativo:
                    # Wake word ativo - o callback _on_wake_word cuida da escuta
                    time.sleep(0.5)
                else:
                    # Modo contínuo (sem wake word)
                    comando = self.voz.ouvir_comando()
                    if comando:
                        self._executar_comando(comando)
                    time.sleep(0.3)
            except KeyboardInterrupt:
                self.parar()
            except Exception as exc:
                log.warning(f"Erro no loop: {exc}")

    def executar_comando(self, comando: str, *, falar_resposta: bool | None = None) -> str:
        if falar_resposta is None:
            falar_resposta = not self.modo_web
        log.debug("executar_comando: %r falar=%s", comando, falar_resposta)
        result = self._executar_comando(comando, falar_resposta=falar_resposta)
        log.debug("resposta: %r", result)
        return result

    def _falar_se_ativo(self, texto: str, *, falar_resposta: bool) -> None:
        if not texto or not falar_resposta:
            return

        def _run() -> None:
            try:
                falar(texto)
                self._ultima_fala = time.time()
            except Exception as e:
                log.warning("Fala falhou: %s", e)

        threading.Thread(target=_run, daemon=True).start()

    def _executar_comando(self, comando: str, *, falar_resposta: bool = True) -> str:
        try:
            if not comando:
                return ""
            log.info("Comando recebido: %s", comando[:80])

            comando_processar = comando.lower().strip()

            # "PARE DE FALAR" deve executar ANTES de qualquer fala
            if eh_comando_parar(comando_processar):
                parar_tudo()
                return "Parei de falar."

            if not comando_processar:
                return self._oferecer_ajuda(falar_resposta=falar_resposta)

            registrar("usuario", comando)
            db_memoria.registrar_padrao(comando_processar)
            resposta = self._verificar_comandos_rapidos(
                comando_processar, falar_resposta=falar_resposta
            )
            if resposta:
                log.info("Comando rapido: %s", resposta)
                return resposta
            resultado = self._processar_com_ia(
                comando_processar, falar_resposta=falar_resposta
            )
            log.info("Resposta: %s", resultado[:80] if resultado else "")
            self._falar_se_ativo(resultado, falar_resposta=falar_resposta)
            return resultado or ""
        except Exception as e:
            log.exception("Falha na execucao")
            self._falar_se_ativo(
                "Desculpe, tive uma falha no sistema interno.",
                falar_resposta=falar_resposta,
            )
            return ""

    def _oferecer_ajuda(self, *, falar_resposta: bool = True) -> str:
        msg = "O que posso fazer por você?"
        self._falar_se_ativo(msg, falar_resposta=falar_resposta)
        return msg

    def _contexto(self, comando: str, params: dict, *, falar_resposta: bool) -> ActionContext:
        return ActionContext(
            intent="",
            comando=comando,
            params=params,
            falar=lambda texto: self._falar_se_ativo(texto, falar_resposta=falar_resposta),
            pc=self.pc,
            lembretes=self.lembretes,
            clima=self.clima,
            noticias=self.noticias,
            diagnostico=self.diagnostico,
            info_sistema=self.info_sistema,
            conhecimento=self.conhecimento,
            voz=self.voz,
            cerebro=self.cerebro,
            status_db=self._status_db,
            encerrar=_desligar_tudo,
        )

    def _verificar_comandos_rapidos(
        self, comando: str, *, falar_resposta: bool = True
    ) -> str:
        atalho = resolver_atalho(comando)
        if atalho is None:
            return ""
        if atalho.encerrar:
            self._falar_se_ativo("Desligando.", falar_resposta=falar_resposta)
            self.parar()
            _desligar_tudo()
            return "Desligando."
        if atalho.registrar:
            registrar("assistente", atalho.texto)
        if atalho.falar:
            self._falar_se_ativo(atalho.texto, falar_resposta=falar_resposta)
        return atalho.texto

    def _processar_com_ia(self, comando: str, *, falar_resposta: bool = True) -> str:
        try:
            intencao = self.cerebro.detectar_intencao(comando)
            intent = intencao.get("intent", "conversa")
            params = intencao.get("parametros", {}) or {}
            ctx = self._contexto(comando, params, falar_resposta=falar_resposta)
            acao = dispatch(intent, ctx)
            if acao is not None:
                return acao

            self.cerebro.aprendizado.registrar_desconhecido(comando)
            ctx_extra = ""
            conhecimentos = self.conhecimento.buscar(comando, limite=3)
            if conhecimentos:
                ctx_extra = "\nInformação da minha base de conhecimento:\n" + "\n".join(
                    f"- {c['titulo']}: {c['conteudo'][:300]}" for c in conhecimentos
                )
            visiveis = self.pc.programas_visiveis()
            if visiveis:
                ctx_extra += "\n[PROGRAMAS VISIVEIS NA TELA]\n" + "\n".join(
                    f"- {p['nome']}" for p in visiveis[:20]
                )
            resposta = intencao.get("resposta", "")
            if _tem_recusa(str(resposta)):
                reclass = _reclassificar_como_sistema(comando)
                if reclass:
                    ctx.params = reclass.get("parametros", {}) or {}
                    refeito = dispatch(reclass.get("intent", ""), ctx)
                    if refeito is not None:
                        return refeito

            if not resposta:
                if self._parece_pergunta_conhecimento(comando):
                    resposta = saber(
                        comando, self.conhecimento, self.cerebro, ctx.falar
                    )
                    if resposta:
                        registrar("assistente", resposta)
                        return resposta
                comando_completo = f"{comando}\n\n{ctx_extra}" if ctx_extra else comando
                resposta = self.cerebro.processar(comando_completo)
            if resposta:
                match = re.search(r"\[KNOWLEDGE:\s*(.*?)\|(.*?)\|(.*?)\]", resposta)
                if match:
                    titulo = match.group(1).strip()
                    conteudo = match.group(2).strip()
                    bloco = match.group(3).strip()
                    resposta = re.sub(r"\s*\[KNOWLEDGE:.*?\]", "", resposta).strip()
                    self.conhecimento.adicionar(titulo, conteudo, bloco)
                    log.info("Auto-conhecimento salvo: %s", titulo)
                registrar("assistente", resposta)
            return resposta or ""
        except Exception as exc:
            erro = str(exc)
            log.exception("Erro no processamento")
            registrar("assistente", f"Erro: {erro[:200]}")
            return f"Erro: {erro[:100]}"


    def _verificar_lembretes(self) -> None:
        while self.ativo:
            try:
                vencidos = self.lembretes.verificar()
                for lembrete in vencidos:
                    falar(f"Lembrete: {lembrete['texto']}")
            except Exception as exc:
                log.exception("Erro na verificacao de lembretes")
            time.sleep(10)

    def _monitorizar_sistema(self) -> None:
        while self.ativo:
            try:
                uso_cpu = psutil.cpu_percent(interval=1)
                if uso_cpu > 90.0:
                    alerta = f"CPU em {uso_cpu:.0f}%. Verifique os processos."
                    registrar("sistema", alerta)
                    falar(alerta)
                    time.sleep(300)
                else:
                    time.sleep(15)
            except Exception as exc:
                log.warning(f"Erro na monitorizacao: {exc}")
                time.sleep(60)

    def _varredura_programas(self) -> None:
        while self.ativo:
            try:
                dados = self.pc.escanear_programas()
                self._ultima_varredura = dados.get("processos", [])
                db_memoria.registrar_comando("varredura", f"{len(dados.get('janelas',[]))} janelas, {len(dados.get('processos',[]))} processos", "", success=True)
                time.sleep(50)
            except Exception as e:
                log.warning(f"Erro na varredura: {e}")
                time.sleep(50)

    def _status_db(self) -> str:
        mb = db_memoria.db_tamanho_mb()
        cont = db_memoria.db_contagem()
        return (f"Banco: {mb:.1f}MB. "
                f"{cont['conversas']} conversas, "
                f"{cont['memorias']} memorias, "
                f"{cont['comandos']} comandos, "
                f"{cont['padroes']} padroes.")

    def parar(self) -> None:
        self.ativo = False
        if self._wake_word_ativo:
            wake_word_manager.stop()
            self._wake_word_ativo = False
        self.lembretes.salvar()

    def _parece_pergunta_conhecimento(self, comando: str) -> bool:
        """Verifica se o comando parece uma pergunta que pode precisar de busca web."""
        c = comando.lower().strip()
        if len(c) < 8:
            return False
        # Palavras-chave que indicam busca de informação
        indicadores = (
            "o que ", "qual ", "quais ", "como ", "por que ", "porque ",
            "quando ", "onde ", "quem ", "o que e ", "o que eh ",
            "pesquise ", "busque ", "busca ", "procure ", "pesquisa ",
            "me fale ", "me diga ", "me explica ", "explique ",
            "sabe ", "sabe sobre ", "lembra ",
            "preco ", "preço ", "valor ", "cotacao ", "cotação ",
            "noticias ", "atual ", "hoje ", "agora ", "agora ",
            "clima ", "tempo ", "temperatura ",
            "melhor ", "pior ", "top ", "melhores ",
        )
        if any(p in c for p in indicadores):
            return True
        # Perguntas diretas com "?"
        if "?" in c:
            return True
        return False

