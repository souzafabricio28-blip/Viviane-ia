import numpy as np
import pytest

from core.escuta import EscutaContinua, eh_lixo, extrair_chamada, parece_nome


@pytest.mark.parametrize("texto,resto", [
    ("Viviane", ""),
    ("oi Viviane", ""),
    ("Viviane, que horas são?", "que horas são?"),
    ("ei viviane abre o chrome", "abre o chrome"),
    ("Vivian", ""),
    ("Vivi Ane", ""),
    ("Viviani. Qual a previsão do tempo?", "Qual a previsão do tempo?"),
])
def test_reconhece_o_nome(texto, resto):
    chamou, sobra = extrair_chamada(texto)
    assert chamou
    assert sobra == resto


@pytest.mark.parametrize("texto", [
    "que horas são",
    "oi tudo bem",
    "abre o navegador",
    "vivo na cidade de vitória",
    "o vinagre acabou",
])
def test_nao_chama_com_outras_palavras(texto):
    assert extrair_chamada(texto)[0] is False


def test_nome_curto_nao_dispara():
    assert not parece_nome("vi")
    assert not parece_nome("vivo")


def test_filtra_alucinacao_do_whisper():
    assert eh_lixo("Legendas pela comunidade Amara.org")
    assert eh_lixo(" . ")
    assert not eh_lixo("que horas são")


def _bloco(valor: int) -> np.ndarray:
    return np.full(480, valor, dtype=np.int16)


def test_recorta_uma_frase_entre_silencios():
    escuta = EscutaContinua(ao_estado=lambda e: None, ao_chamar=lambda: None, ao_comando=lambda t: None)
    escuta._rodando = True
    for _ in range(20):
        escuta._fila.put(_bloco(10))  # silêncio inicial
    for _ in range(40):
        escuta._fila.put(_bloco(3000))  # ~1,2 s de fala
    for _ in range(40):
        escuta._fila.put(_bloco(10))  # silêncio final

    audio = escuta._proximo_enunciado(espera_max=2.0)

    assert audio is not None
    segundos = len(audio) / 16000
    assert 1.2 <= segundos <= 2.4


def test_ignora_estalo_curto():
    escuta = EscutaContinua(ao_estado=lambda e: None, ao_chamar=lambda: None, ao_comando=lambda t: None)
    escuta._rodando = True
    for _ in range(10):
        escuta._fila.put(_bloco(10))
    for _ in range(4):
        escuta._fila.put(_bloco(4000))  # 120 ms: estalo
    for _ in range(40):
        escuta._fila.put(_bloco(10))

    assert escuta._proximo_enunciado(espera_max=0.5) is None


def test_chamada_sem_pedido_responde_e_escuta(monkeypatch):
    eventos = []
    escuta = EscutaContinua(
        ao_estado=lambda e: eventos.append(("estado", e)),
        ao_chamar=lambda: eventos.append(("chamar",)),
        ao_comando=lambda t: eventos.append(("comando", t)),
    )
    escuta._rodando = True
    monkeypatch.setattr(escuta, "_proximo_enunciado", lambda **k: np.ones(16000, dtype=np.int16))
    monkeypatch.setattr(escuta, "_transcrever", lambda audio: "que horas são")

    escuta._chamar()

    assert ("chamar",) in eventos
    assert ("comando", "que horas são") in eventos
