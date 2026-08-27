"""
=============================================================================
 WHATSAPP — META CLOUD API
=============================================================================

 Esta integração é usada apenas para enviar o template inicial aprovado.

 Enquanto META_TOKEN estiver vazio, o modo simulação fica ligado: as
 mensagens são impressas no terminal em vez de enviadas. Assim dá para
 testar o fluxo inteiro sem número registrado.
=============================================================================
"""

import requests

import config


def modo_simulacao():
    return not (config.META_TOKEN and config.META_PHONE_NUMBER_ID)


def _url():
    return (
        f"https://graph.facebook.com/{config.META_API_VERSION}/"
        f"{config.META_PHONE_NUMBER_ID}/messages"
    )


def enviar_template(telefone, nome_template, idioma="pt_BR", parametros=None):
    """Envia um template aprovado.

    Necessário para INICIAR conversa com um lead que nunca falou com o
    número (janela de 24h da Meta). É por aqui que a abordagem inicial
    dos leads importados deve sair, em produção.

    TODO: cadastrar o template de abordagem no Gerenciador da Meta e
          colocar o nome dele aqui.
    """
    if modo_simulacao():
        print(f"\n[SIMULAÇÃO template '{nome_template}'] → +{telefone}\n")
        return {"simulado": True}

    componentes = []
    if parametros:
        componentes.append({
            "type": "body",
            "parameters": [{"type": "text", "text": p} for p in parametros],
        })

    resposta = requests.post(
        _url(),
        headers={
            "Authorization": f"Bearer {config.META_TOKEN}",
            "Content-Type": "application/json",
        },
        json={
            "messaging_product": "whatsapp",
            "to": telefone,
            "type": "template",
            "template": {
                "name": nome_template,
                "language": {"code": idioma},
                "components": componentes,
            },
        },
        timeout=20,
    )
    resposta.raise_for_status()
    return resposta.json()


def extrair_mensagem(payload):
    """Lê o webhook da Meta e devolve (telefone, texto) ou (None, None).

    Ignora eventos que não são mensagem de texto (status de entrega,
    confirmações de leitura, áudios, imagens etc).
    """
    try:
        valor = payload["entry"][0]["changes"][0]["value"]
        mensagem = valor["messages"][0]
    except (KeyError, IndexError, TypeError):
        return None, None

    if mensagem.get("type") != "text":
        return mensagem.get("from"), None

    return mensagem["from"], mensagem["text"]["body"]
