from core.skills.clima import _limpar_cidade


def test_limpa_pontuacao_e_estado():
    assert _limpar_cidade("Sao Paulo?") == "Sao Paulo"
    assert _limpar_cidade("São Paulo, SP.") == "São Paulo"
    assert _limpar_cidade("em Curitiba!") == "Curitiba"
    assert _limpar_cidade("") == "São Paulo"
