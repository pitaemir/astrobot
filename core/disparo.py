"""
Disparo do template inicial para uma lista de leads.

Fica separado da rota HTTP para que o servidor (main.py) e o script de
linha de comando (importar_planilha.py) usem exatamente a mesma lógica.
"""

import config
import core.models as models
from core import conversation
from integrations import whatsapp_meta
from storage import leads as repo


def somente_digitos(valor):
    return "".join(c for c in str(valor or "") if c.isdigit())


def disparar_lote(telefones, parametros_por_telefone=None, forcar=False,
                  nomes_por_telefone=None):
    """Envia o template aprovado para cada telefone da lista.

    Devolve {"disparados": [...], "ignorados": [...], "erros": [...]}.

    Um lead que já está em conversa ou já foi transferido é ignorado,
    a não ser que forcar=True.
    """
    parametros_por_telefone = parametros_por_telefone or {}
    nomes_por_telefone = nomes_por_telefone or {}

    repo.importar(telefones)
    enviados, erros, ignorados = [], [], []

    for telefone in telefones:
        limpo = somente_digitos(telefone)
        if not limpo:
            continue

        try:
            lead = repo.buscar_ou_criar(limpo)

            if not forcar and lead.status not in (models.NOVO, models.SEM_RESPOSTA):
                ignorados.append({"telefone": limpo, "status": lead.status})
                continue

            # Nome vindo da planilha entra como ponto de partida
            nome = nomes_por_telefone.get(limpo)
            if nome and not lead.nome:
                lead.nome = nome
                repo.salvar(lead)

            conversation.iniciar(limpo)
            whatsapp_meta.enviar_template(
                limpo,
                config.META_TEMPLATE_NAME,
                config.META_TEMPLATE_LANGUAGE,
                parametros_por_telefone.get(limpo) or ([nome] if nome else None),
            )
            enviados.append(limpo)

        except Exception as erro:
            erros.append({"telefone": limpo, "erro": str(erro)})

    return {"disparados": enviados, "ignorados": ignorados, "erros": erros}
