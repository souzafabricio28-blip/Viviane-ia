"""Atalhos, bloqueio local e reclassificação, sem microfone nem API."""

from core.actions.atalhos import resolver_atalho
from core.actions.context import ActionContext
from core.actions.dispatch import dispatch
from core.llm.brain import _reclassificar_como_sistema
from core.settings import Settings, aplicar_modo_local, settings


def test_atalho_de_hora():
    atalho = resolver_atalho("que horas sao")
    assert atalho is not None
    assert ":" in atalho.texto
    assert atalho.encerrar is False


def test_atalho_de_saudacao():
    atalho = resolver_atalho("boa noite viviane")
    assert atalho is not None
    assert atalho.texto == "Boa noite"


def test_desligar_viviane_pede_encerramento():
    atalho = resolver_atalho("desligar viviane")
    assert atalho is not None
    assert atalho.encerrar is True


def test_modo_local_forca_loopback():
    cfg = object.__new__(Settings)
    cfg.local_only = True
    cfg.api_host = "0.0.0.0"
    cfg.allow_origins = "https://exemplo.invalid"
    aplicar_modo_local(cfg)
    assert cfg.api_host == "127.0.0.1"
    assert cfg.allow_origins == ""


def test_acao_sensivel_bloqueada(monkeypatch):
    monkeypatch.setattr(settings, "allow_system_actions", False)
    ctx = ActionContext(intent="matar_processo", comando="matar notepad", params={"nome": "notepad"})
    texto = dispatch("matar_processo", ctx)
    assert texto is not None
    assert "desativada" in texto


def test_conversa_nao_dispara_acao():
    ctx = ActionContext(intent="conversa", comando="conta uma piada", params={})
    assert dispatch("conversa", ctx) is None


def test_reclassifica_pasta_e_comando():
    pasta = _reclassificar_como_sistema("abrir a pasta documentos")
    assert pasta is not None
    assert pasta["intent"] == "abrir_pasta"
    assert "documentos" in pasta["parametros"]["caminho"]

    cmd = _reclassificar_como_sistema("executar ipconfig")
    assert cmd is not None
    assert cmd["intent"] == "executar_cmd"
    assert cmd["parametros"]["comando"] == "ipconfig"
