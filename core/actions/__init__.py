"""Ações da Viviane: atalhos locais e despacho de intenções."""

from core.actions.atalhos import resolver_atalho
from core.actions.context import ActionContext
from core.actions.dispatch import dispatch

__all__ = ["ActionContext", "dispatch", "resolver_atalho"]
