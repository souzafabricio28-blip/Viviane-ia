import threading
import time

import pytest

from core import voice
from core.actions.atalhos import eh_comando_parar, resolver_atalho


@pytest.mark.parametrize("frase", [
    "pare", "Pare!", "para de falar", "viviane pare agora", "cala a boca",
    "silêncio", "chega de falar", "pare aí", "stop",
])
def test_reconhece_pedido_de_parar(frase):
    assert eh_comando_parar(frase)


@pytest.mark.parametrize("frase", [
    "para que serve o python",
    "parar assistente",
    "qual a capital da frança",
    "me explica o que é um parafuso",
    "pare de baixar o arquivo e abra o chrome",
])
def test_nao_confunde_com_outros_comandos(frase):
    assert not eh_comando_parar(frase)


def test_atalho_parar_nao_fala_de_volta():
    atalho = resolver_atalho("pare")
    assert atalho is not None
    assert atalho.falar is False


def test_fala_na_fila_e_cancelada_quando_pedem_pare(monkeypatch):
    faladas = []
    monkeypatch.setattr(voice, "_tocar_com_amplitude", lambda texto, engine="": faladas.append(texto))

    voice._tts_lock.acquire()  # simula uma fala em andamento
    th = threading.Thread(target=voice.falar, args=("isto não deve ser falado",))
    th.start()
    time.sleep(0.2)
    voice.parar_fala()
    voice._tts_lock.release()
    th.join(timeout=3)

    assert faladas == []

    voice.falar("depois do pare volta a falar")
    assert faladas == ["depois do pare volta a falar"]


def test_parar_corta_reproducao_em_andamento(monkeypatch):
    """O laço de reprodução precisa sair assim que o 'pare' chega."""
    voice._stop_event.clear()
    inicio = time.time()

    def reproduz(texto, engine=""):
        while not voice._stop_event.is_set() and time.time() - inicio < 5:
            time.sleep(0.02)

    monkeypatch.setattr(voice, "_tocar_com_amplitude", reproduz)
    th = threading.Thread(target=voice.falar, args=("uma resposta bem longa",))
    th.start()
    time.sleep(0.3)
    assert voice.esta_falando()
    voice.parar_fala()
    th.join(timeout=2)

    assert not th.is_alive()
    assert time.time() - inicio < 2
    assert not voice.esta_falando()
