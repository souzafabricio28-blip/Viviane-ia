"""Microfone sempre ligado: ouve, espera ouvir "Viviane" e atende o pedido sem apertar nada."""

from __future__ import annotations

import collections
import logging
import queue
import re
import threading
import time
import unicodedata
from difflib import SequenceMatcher
from typing import Callable

import numpy as np

log = logging.getLogger("Viviane.Escuta")

TAXA = 16000
BLOCO = 480  # 30 ms
SEG_POR_BLOCO = BLOCO / TAXA

# Textos que o Whisper inventa quando só há ruído
_ALUCINACOES = (
    "amara.org", "legendas", "inscreva-se", "obrigado por assistir", "obrigada por assistir",
    "até a próxima", "ate a proxima", "tchau tchau", "música", "musica",
)
_APELIDOS_CHAMADA = frozenset({"oi", "ei", "ola", "olá", "hey", "ok", "e", "ai", "aí", "opa", "fala"})


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^\w]", "", s)


def parece_nome(palavra: str, nome: str = "viviane") -> bool:
    p = _norm(palavra)
    if len(p) < 4:
        return False
    return p == nome or SequenceMatcher(None, p, nome).ratio() >= 0.78


def extrair_chamada(texto: str, nome: str = "viviane") -> tuple[bool, str]:
    """Procura o nome dela na frase. Devolve (chamou, resto_depois_do_nome).

    'Viviane, que horas são?' -> (True, 'que horas são?')
    'oi Vivi Ane'             -> (True, '')
    """
    palavras = texto.split()
    for i, palavra in enumerate(palavras):
        achou, usadas = False, 1
        if parece_nome(palavra, nome):
            achou = True
        elif i + 1 < len(palavras) and parece_nome(palavra + palavras[i + 1], nome):
            achou, usadas = True, 2  # "Vivi Ane"
        if not achou:
            continue
        resto = " ".join(palavras[i + usadas:]).lstrip(" ,.:;!?-–—")
        return True, resto.strip()
    return False, ""


def eh_lixo(texto: str) -> bool:
    t = (texto or "").strip().lower()
    if len(re.sub(r"[\W_]", "", t)) < 2:
        return True
    return any(a in t for a in _ALUCINACOES)


class EscutaContinua:
    def __init__(
        self,
        *,
        ao_estado: Callable[[str], None],
        ao_chamar: Callable[[], None],
        ao_comando: Callable[[str], None],
        nome: str = "viviane",
        janela_conversa: float = 7.0,
    ) -> None:
        self.ao_estado = ao_estado
        self.ao_chamar = ao_chamar
        self.ao_comando = ao_comando
        self.nome = nome.lower()
        self.janela_conversa = janela_conversa

        self._fila: queue.Queue[np.ndarray] = queue.Queue()
        self._rodando = False
        self._pausado = False
        self._thread: threading.Thread | None = None
        self._ruido = 60.0
        self._conversa_ate = 0.0
        self.ultimo_erro = ""

    # ── controle ───────────────────────────────────────────────────────

    @property
    def ligado(self) -> bool:
        return self._rodando and not self._pausado

    def iniciar(self) -> None:
        if self._rodando:
            return
        self._rodando = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="escuta")
        self._thread.start()

    def parar(self) -> None:
        self._rodando = False

    def pausar(self) -> None:
        self._pausado = True
        self._drenar()

    def retomar(self) -> None:
        self._drenar()
        self._pausado = False

    # ── áudio ──────────────────────────────────────────────────────────

    def _drenar(self) -> None:
        try:
            while True:
                self._fila.get_nowait()
        except queue.Empty:
            pass

    def _limiar(self, falando: bool) -> float:
        base = max(self._ruido * 3.0, 220.0)
        return max(base, 600.0) if falando else base

    def _proximo_enunciado(
        self, *, espera_max: float | None = None, silencio_fim: float = 0.7, max_dur: float = 14.0,
    ) -> np.ndarray | None:
        """Bloqueia até uma frase terminar. None se esperou demais ou foi pausada."""
        from core.voice import esta_falando

        inicio_espera = time.time()
        pre: collections.deque[np.ndarray] = collections.deque(maxlen=10)
        voz: list[np.ndarray] = []
        falando = False
        seguidos = 0
        silencio = 0.0

        while self._rodando:
            if self._pausado:
                self._drenar()
                time.sleep(0.05)
                inicio_espera = time.time()
                return None
            try:
                bloco = self._fila.get(timeout=0.1)
            except queue.Empty:
                if not falando and espera_max and time.time() - inicio_espera > espera_max:
                    return None
                continue

            rms = float(np.sqrt(np.mean(bloco.astype(np.float32) ** 2)))
            limiar = self._limiar(esta_falando())

            if not falando:
                if rms < limiar:
                    self._ruido = 0.98 * self._ruido + 0.02 * rms
                pre.append(bloco)
                seguidos = seguidos + 1 if rms > limiar else 0
                if seguidos >= 3:
                    falando = True
                    voz = list(pre)
                    silencio = 0.0
                elif espera_max and time.time() - inicio_espera > espera_max:
                    return None
                continue

            voz.append(bloco)
            silencio = 0.0 if rms > limiar * 0.7 else silencio + SEG_POR_BLOCO
            duracao = len(voz) * SEG_POR_BLOCO
            if silencio >= silencio_fim or duracao >= max_dur:
                if duracao - silencio < 0.35:  # estalo, tosse: ignora e continua esperando
                    falando, voz, seguidos, silencio = False, [], 0, 0.0
                    pre.clear()
                    continue
                return np.concatenate(voz)
        return None

    def _transcrever(self, audio: np.ndarray) -> str:
        from core.transcricao import transcrever_audio

        try:
            return transcrever_audio(audio, prompt="Viviane, assistente pessoal.")
        except Exception as exc:
            log.warning("Falha ao transcrever: %s", exc)
            self.ultimo_erro = str(exc)
            return ""

    # ── laço principal ─────────────────────────────────────────────────

    def _loop(self) -> None:
        import sounddevice as sd

        while self._rodando:
            try:
                with sd.InputStream(
                    samplerate=TAXA, channels=1, dtype="int16", blocksize=BLOCO,
                    callback=lambda indata, *_: self._fila.put(indata[:, 0].copy()),
                ):
                    log.info("Microfone aberto, escutando por '%s'", self.nome)
                    self.ao_estado("ouvindo")
                    self._ciclo()
            except Exception as exc:
                self.ultimo_erro = str(exc)
                log.warning("Microfone indisponível: %s", exc)
                self.ao_estado("sem_microfone")
                time.sleep(3)

    def _ciclo(self) -> None:
        from core.actions.atalhos import eh_comando_parar
        from core.voice import esta_falando, parar_fala

        while self._rodando:
            if self._pausado:
                time.sleep(0.1)
                continue

            falando = esta_falando()
            audio = self._proximo_enunciado(espera_max=1.0)
            if audio is None:
                continue

            duracao = len(audio) * SEG_POR_BLOCO
            if falando or esta_falando():
                # É provavelmente a própria voz dela; só interessa um "pare" curtinho.
                if duracao > 2.5:
                    continue
                texto = self._transcrever(audio)
                if texto and eh_comando_parar(texto):
                    log.info("Pare por voz: %r", texto)
                    parar_fala()
                continue

            texto = self._transcrever(audio)
            if not texto or eh_lixo(texto):
                continue
            log.info("Ouvi: %r", texto)

            chamou, resto = extrair_chamada(texto, self.nome)
            em_conversa = time.time() < self._conversa_ate
            if chamou:
                if len(re.sub(r"[\W_]", "", resto)) >= 3:
                    self._executar(resto)
                else:
                    self._chamar()
            elif em_conversa:
                self._executar(texto)

    def _chamar(self) -> None:
        """Ouviu só o nome: responde 'sim?' e escuta o pedido."""
        self.ao_estado("chamada")
        try:
            self.ao_chamar()
        except Exception as exc:
            log.warning("Falha ao responder a chamada: %s", exc)
        self._drenar()
        time.sleep(0.25)
        self._drenar()

        audio = self._proximo_enunciado(espera_max=8.0, silencio_fim=0.9)
        if audio is None:
            self.ao_estado("ouvindo")
            return
        self.ao_estado("transcrevendo")
        texto = self._transcrever(audio)
        if not texto or eh_lixo(texto):
            self.ao_estado("ouvindo")
            return
        log.info("Pedido: %r", texto)
        _, resto = extrair_chamada(texto, self.nome)
        self._executar(resto if len(resto) >= 3 else texto)

    def _executar(self, texto: str) -> None:
        self.ao_estado("processando")
        try:
            self.ao_comando(texto)
        except Exception as exc:
            log.warning("Falha ao executar comando por voz: %s", exc)
        self._drenar()
        time.sleep(0.3)
        self._drenar()
        self._conversa_ate = time.time() + self.janela_conversa
        self.ao_estado("ouvindo")
