import pytest

from core.conhecimento import BaseConhecimento
from core.skills.catalogo_pc import BLOCO, montar_catalogo, registrar_comandos_pc


@pytest.fixture()
def base(tmp_path):
    b = BaseConhecimento()
    b.arquivo = tmp_path / "teste.db"
    b._inicializar()
    return b


def test_grava_todos_os_topicos(base):
    total = registrar_comandos_pc(base)

    assert total == len(montar_catalogo()) >= 14
    assert len(base.listar_por_bloco(BLOCO)) == total


def test_gravar_de_novo_nao_duplica(base):
    registrar_comandos_pc(base)
    registrar_comandos_pc(base)

    assert base.contar() == len(montar_catalogo())


@pytest.mark.parametrize("pergunta,titulo", [
    ("como desligar o pc", "Desligar, reiniciar e bloquear o PC"),
    ("comando de volume", "Volume e mídia"),
    ("abrir pasta downloads", "Abrir pastas"),
    ("configuração do wifi", "Configurações do Windows"),
    ("listar processos", "Processos e serviços"),
    ("executar comando powershell", "Executar comando no PowerShell"),
    ("tirar print da tela", "Print, webcam e gravação de tela"),
])
def test_encontra_comando_pela_pergunta(base, pergunta, titulo):
    registrar_comandos_pc(base)

    titulos = [r["titulo"] for r in base.buscar(pergunta, limite=5)]

    assert titulo in titulos


def test_lista_vem_do_codigo():
    texto = " ".join(c for _, c, _ in montar_catalogo()).lower()

    assert "calculadora" in texto and "youtube" in texto and "bluetooth" in texto
