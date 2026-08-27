"""Handoff do lead qualificado para a equipe humana no Chatwoot."""

from integrations import chatwoot


def avisar_atendente(lead):
    """Entrega a conversa no Chatwoot; não dispara um segundo WhatsApp."""
    if not lead.chatwoot_conversation_id:
        resumo = lead.resumo_para_atendente()
        print("\n[HANDOFF] Conversa sem ID do Chatwoot. Resumo:\n")
        print(resumo, "\n")
        return {"enviado": False, "resumo": resumo}
    chatwoot.transferir_para_humano(lead)
    return {"enviado": True, "resumo": lead.resumo_para_atendente()}
