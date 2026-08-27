"""Cliente da API do Chatwoot usado pelo Agent Bot."""

import requests

import config


def ativo():
    return bool(config.CHATWOOT_URL and config.CHATWOOT_ACCOUNT_ID and config.CHATWOOT_API_TOKEN)


def _headers():
    return {"api_access_token": config.CHATWOOT_API_TOKEN, "Content-Type": "application/json"}


def _base():
    return f"{config.CHATWOOT_URL.rstrip('/')}/api/v1/accounts/{config.CHATWOOT_ACCOUNT_ID}"


def _post(caminho, payload=None):
    resposta = requests.post(
        f"{_base()}{caminho}", headers=_headers(), json=payload or {}, timeout=20
    )
    resposta.raise_for_status()
    return resposta.json() if resposta.content else None


def enviar_mensagem(conversation_id, texto, privada=False):
    """Envia uma resposta real ou cria uma nota privada na conversa."""
    if not ativo() or not conversation_id or not texto:
        return None
    return _post(
        f"/conversations/{conversation_id}/messages",
        {"content": texto, "message_type": "outgoing", "private": privada, "content_type": "text"},
    )


def nota_privada(conversation_id, texto):
    return enviar_mensagem(conversation_id, texto, privada=True)


def obter_rotulos(conversation_id):
    if not ativo() or not conversation_id:
        return []
    resposta = requests.get(
        f"{_base()}/conversations/{conversation_id}/labels", headers=_headers(), timeout=20
    )
    resposta.raise_for_status()
    return resposta.json().get("payload", [])


def adicionar_rotulos(conversation_id, novos_rotulos):
    """Adiciona labels sem apagar as que um atendente já aplicou."""
    atuais = obter_rotulos(conversation_id)
    rotulos = list(dict.fromkeys([*atuais, *[r for r in novos_rotulos if r]]))
    return _post(f"/conversations/{conversation_id}/labels", {"labels": rotulos})


def atualizar_atributos(conversation_id, atributos):
    limpos = {chave: valor for chave, valor in atributos.items() if valor is not None}
    if not ativo() or not conversation_id or not limpos:
        return None
    return _post(
        f"/conversations/{conversation_id}/custom_attributes", {"custom_attributes": limpos}
    )


def atribuir(conversation_id):
    """Atribui ao agente configurado ou, na ausência dele, à equipe."""
    if not ativo() or not conversation_id:
        return None
    payload = {}
    if config.CHATWOOT_ASSIGNEE_ID:
        payload["assignee_id"] = int(config.CHATWOOT_ASSIGNEE_ID)
    elif config.CHATWOOT_TEAM_ID:
        payload["team_id"] = int(config.CHATWOOT_TEAM_ID)
    else:
        return None
    return _post(f"/conversations/{conversation_id}/assignments", payload)


def alterar_status(conversation_id, status):
    if not ativo() or not conversation_id:
        return None
    return _post(f"/conversations/{conversation_id}/toggle_status", {"status": status})


def transferir_para_humano(lead):
    """Registra o resultado e libera a conversa para atendimento humano."""
    conversation_id = lead.chatwoot_conversation_id
    if not ativo() or not conversation_id:
        return None
    rotulos = ["interessado", "atendimento-humano"]
    if lead.classificacao:
        rotulos.append(lead.classificacao.lower().replace(" ", "-"))
    avisos = []
    operacoes = [
        ("labels", lambda: adicionar_rotulos(conversation_id, rotulos)),
        ("atributos", lambda: atualizar_atributos(conversation_id, {
            "nome_lead": lead.nome,
            "regiao": lead.regiao,
            "capital_disponivel": lead.capital_disponivel,
            "prazo": lead.prazo,
            "classificacao": lead.classificacao,
            "score": lead.score,
        })),
        ("nota", lambda: nota_privada(conversation_id, lead.resumo_para_atendente())),
        ("atribuição", lambda: atribuir(conversation_id)),
    ]
    for nome, operacao in operacoes:
        try:
            operacao()
        except requests.RequestException as erro:
            avisos.append(f"{nome}: {erro}")
    resultado = alterar_status(conversation_id, "open")
    return {"resultado": resultado, "avisos": avisos}


def encerrar_sem_interesse(lead):
    conversation_id = lead.chatwoot_conversation_id
    if not ativo() or not conversation_id:
        return None
    try:
        adicionar_rotulos(conversation_id, ["sem-interesse"])
    except requests.RequestException:
        pass
    return alterar_status(conversation_id, "resolved")
