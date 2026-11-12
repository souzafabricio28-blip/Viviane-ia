from core.actions.context import ActionContext
from core.actions.dispatch import dispatch
from core.skills.pc_control import ControladorPC


def _ctx(comando: str) -> ActionContext:
    pc = ControladorPC()
    return ActionContext(
        intent="", comando=comando, params={"comando": comando},
        falar=lambda _t: None, pc=pc, lembretes=None, clima=None, noticias=None,
        diagnostico=None, info_sistema=None, conhecimento=None, voz=None,
        cerebro=None, status_db=lambda: "", encerrar=lambda: None,
    )


def test_palavra_comum_nao_vira_comando():
    pc = ControladorPC()
    assert pc.comando_valido("ações") is False
    assert pc.comando_valido("acoes permitidas") is False
    assert dispatch("executar_cmd", _ctx("acoes")) is None


def test_comando_real_executa_e_mantem_acentos():
    pc = ControladorPC()
    assert pc.comando_valido("Get-Date") is True
    assert pc.executar_comando("Write-Output 'ação não'") == "ação não"
    assert dispatch("executar_cmd", _ctx("Write-Output ok")).endswith("ok")
