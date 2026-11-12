import pytest

from core import conhecimento as conh
from core.skills import saber as saber_mod
from core.skills import web_search


@pytest.fixture
def base(tmp_path, monkeypatch):
    monkeypatch.setattr(conh.settings, "data_dir", tmp_path)
    b = conh.BaseConhecimento()
    monkeypatch.setattr(web_search, "_base", b)
    return b


RESULTADOS = [
    {
        "title": "Tubarão-branco – Wikipédia",
        "body": "O tubarão-branco é um grande tubarão lamniforme encontrado em águas costeiras de todos os oceanos.",
        "href": "https://pt.wikipedia.org/wiki/Tubar%C3%A3o-branco",
    },
]


def test_busca_exige_todas_as_palavras(base):
    base.adicionar("Ciências naturais", "Estudo de animais e plantas", "Geral")
    assert base.buscar("tubarao branco animal marinho") == []


def test_pontuacao_nao_quebra_busca(base):
    assert base.buscar('o que é "tubarão"? (branco)') == []


def test_adicionar_nao_duplica(base):
    base.adicionar("Tubarão-branco", "texto antigo", "Web", tags="a")
    base.adicionar("tubarão-branco", "texto novo", "Web", tags="b")
    assert base.contar() == 1
    achado = base.buscar("tubarão branco")[0]
    assert achado["conteudo"] == "texto novo"


def test_nao_sabe_pesquisa_guarda_e_reusa(base, monkeypatch):
    chamadas = []

    def falso(query, num_resultados=5):
        chamadas.append(query)
        return RESULTADOS

    monkeypatch.setattr(saber_mod, "pesquisar_web", falso)
    falas = []

    primeira = saber_mod.saber("tubarao branco animal marinho", base, None, falas.append)
    assert chamadas == ["tubarao branco animal marinho"]
    assert "tubarão-branco" in primeira.lower()
    assert any("pesquisar na internet" in f for f in falas)
    assert base.contar() == 1

    segunda = saber_mod.saber("tubarao branco animal marinho", base, None, falas.append)
    assert len(chamadas) == 1, "segunda vez deve usar o que foi guardado"
    assert "já sabia" in segunda.lower()


def test_sem_internet_responde_honesto(base, monkeypatch):
    monkeypatch.setattr(saber_mod, "pesquisar_web", lambda *a, **k: [])
    resposta = saber_mod.saber("assunto inexistente xyz", base, None, None)
    assert "não achei" in resposta.lower()
