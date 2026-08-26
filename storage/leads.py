"""
Armazenamento dos leads.

Por enquanto: um arquivo JSON local (leads.json). Simples, sem banco,
sem planilha. Suficiente para testar e para os primeiros leads reais.

TODO (quando o volume crescer): trocar por SQLite ou Postgres.
Só este arquivo muda — a interface (buscar / salvar / listar) continua igual.
"""

import json
import os
import threading

from core.models import Lead

ARQUIVO = os.getenv("ARQUIVO_LEADS", "leads.json")
_trava = threading.Lock()


def _ler_tudo():
    if not os.path.exists(ARQUIVO):
        return {}
    try:
        with open(ARQUIVO, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _gravar_tudo(dados):
    with open(ARQUIVO, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)


def buscar(telefone):
    """Devolve o Lead ou None."""
    dados = _ler_tudo().get(telefone)
    return Lead.from_dict(dados) if dados else None


def buscar_ou_criar(telefone):
    lead = buscar(telefone)
    if lead is None:
        lead = Lead(telefone=telefone)
        salvar(lead)
    return lead


def salvar(lead):
    with _trava:
        dados = _ler_tudo()
        dados[lead.telefone] = lead.to_dict()
        _gravar_tudo(dados)
    return lead


def listar(status=None):
    """Lista todos os leads, opcionalmente filtrando por status."""
    leads = [Lead.from_dict(d) for d in _ler_tudo().values()]
    if status:
        leads = [l for l in leads if l.status == status]
    return leads


def importar(telefones):
    """Cadastra uma lista de números como leads novos.

    Usado para carregar os contatos que manifestaram interesse.
    Devolve quantos foram criados de fato (ignora duplicados).
    """
    criados = 0
    for telefone in telefones:
        limpo = "".join(c for c in str(telefone) if c.isdigit())
        if not limpo:
            continue
        if buscar(limpo) is None:
            salvar(Lead(telefone=limpo))
            criados += 1
    return criados
