"""
Aviso ao atendente humano.

Quando um lead termina a qualificação (ou pede para falar com gente),
o atendente recebe no WhatsApp o nome, o número e o resumo das respostas.
"""

import config
from integrations import whatsapp_meta, chatwoot


def avisar_atendente(lead):
    """Dispara o resumo do lead para o número do atendente."""
    resumo = lead.resumo_para_atendente()

    if not config.ATENDENTE_WHATSAPP:
        print("\n[AVISO] ATENDENTE_WHATSAPP não configurado no .env.")
        print("Mensagem que seria enviada:\n")
        print(resumo, "\n")
        return {"enviado": False, "resumo": resumo}

    whatsapp_meta.enviar_texto(config.ATENDENTE_WHATSAPP, resumo)

    # Também deixa o resumo como nota interna na conversa do Chatwoot
    if lead.chatwoot_conversation_id:
        chatwoot.espelhar_mensagem(
            lead.chatwoot_conversation_id, resumo, do_bot=True, privada=True
        )
        rotulos = ["qualificado"]
        if lead.classificacao:
            rotulos.append(lead.classificacao.lower().replace(" ", "-"))
        chatwoot.marcar_rotulos(lead.chatwoot_conversation_id, rotulos)

    return {"enviado": True, "resumo": resumo}
