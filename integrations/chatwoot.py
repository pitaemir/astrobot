"""
=============================================================================
 CHATWOOT
=============================================================================

"""

import requests

import config


def ativo():
    return bool(config.CHATWOOT_URL and config.CHATWOOT_API_TOKEN)


def _headers():
    return {"api_access_token": config.CHATWOOT_API_TOKEN,
            "Content-Type": "application/json"}


def _base():
    return f"{config.CHATWOOT_URL}/api/v1/accounts/{config.CHATWOOT_ACCOUNT_ID}"


def criar_contato(telefone, nome=None):
    """Cria (ou recupera) o contato no Chatwoot. Devolve o source_id."""
    if not ativo():
        return None

    resposta = requests.post(
        f"{_base()}/contacts",
        headers=_headers(),
        json={
            "inbox_id": config.CHATWOOT_INBOX_ID,
            "name": nome or f"Lead +{telefone}",
            "phone_number": f"+{telefone}",
        },
        timeout=20,
    )

    # 422 = contato já existe; nesse caso buscamos pelo telefone
    if resposta.status_code == 422:
        return _buscar_contato(telefone)

    resposta.raise_for_status()
    payload = resposta.json()["payload"]["contact_inboxes"][0]
    return payload["source_id"]


def _buscar_contato(telefone):
    resposta = requests.get(
        f"{_base()}/contacts/search",
        headers=_headers(),
        params={"q": telefone},
        timeout=20,
    )
    resposta.raise_for_status()
    itens = resposta.json().get("payload", [])
    if not itens:
        return None
    inboxes = itens[0].get("contact_inboxes") or []
    return inboxes[0]["source_id"] if inboxes else None


def abrir_conversa(telefone, nome=None):
    """Abre uma conversa no Chatwoot e devolve o conversation_id."""
    if not ativo():
        return None

    source_id = criar_contato(telefone, nome)
    if not source_id:
        return None

    resposta = requests.post(
        f"{_base()}/conversations",
        headers=_headers(),
        json={
            "source_id": source_id,
            "inbox_id": config.CHATWOOT_INBOX_ID,
        },
        timeout=20,
    )
    resposta.raise_for_status()
    return resposta.json()["id"]


def espelhar_mensagem(conversation_id, texto, do_bot=True, privada=False):
    """Registra uma mensagem na conversa do Chatwoot.

    do_bot=True  → aparece como mensagem enviada (outgoing)
    do_bot=False → aparece como mensagem do lead (incoming)
    privada=True → nota interna, o lead não vê
    """
    if not ativo() or not conversation_id:
        return None

    resposta = requests.post(
        f"{_base()}/conversations/{conversation_id}/messages",
        headers=_headers(),
        json={
            "content": texto,
            "message_type": "outgoing" if do_bot else "incoming",
            "private": privada,
        },
        timeout=20,
    )
    resposta.raise_for_status()
    return resposta.json()


def marcar_rotulos(conversation_id, rotulos):
    """Aplica labels na conversa (ex: ['quente', 'sp', 'capital'])."""
    if not ativo() or not conversation_id:
        return None

    resposta = requests.post(
        f"{_base()}/conversations/{conversation_id}/labels",
        headers=_headers(),
        json={"labels": rotulos},
        timeout=20,
    )
    resposta.raise_for_status()
    return resposta.json()
