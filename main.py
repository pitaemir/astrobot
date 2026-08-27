"""Servidor HTTP do AstroBot integrado como Agent Bot do Chatwoot.

Endpoints:
    POST /webhook/chatwoot  -> eventos enviados pelo Agent Bot
    POST /disparar          -> inicia contatos com template aprovado da Meta
    GET  /leads             -> lista os leads e seus estados
    GET  /saude             -> checagem rápida da configuração
"""

from concurrent.futures import ThreadPoolExecutor
import hashlib
import hmac
import time

from flask import Flask, jsonify, request

import config
from core import conversation
import core.models as models
from core import disparo
from integrations import chatwoot, google_sheets, notificacao, whatsapp_meta
from storage import events
from storage import leads as repo


app = Flask(__name__)
executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="astrobot")


def _somente_digitos(valor):
    return "".join(c for c in str(valor or "") if c.isdigit())


def _assinatura_valida(corpo_bruto, cabecalhos):
    """Valida a assinatura HMAC emitida pelo Chatwoot, quando configurada."""
    segredo = config.CHATWOOT_WEBHOOK_SECRET
    if not segredo:
        return True

    assinatura = cabecalhos.get("X-Chatwoot-Signature", "")
    timestamp = cabecalhos.get("X-Chatwoot-Timestamp", "")
    if not assinatura or not timestamp:
        return False
    try:
        if abs(time.time() - int(timestamp)) > 300:
            return False
    except ValueError:
        return False

    mensagem = timestamp.encode("utf-8") + b"." + corpo_bruto
    calculada = "sha256=" + hmac.new(
        segredo.encode("utf-8"), mensagem, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(assinatura, calculada)


def _extrair_evento_chatwoot(payload):
    """Normaliza um message_created incoming do Agent Bot."""
    if not isinstance(payload, dict) or payload.get("event") != "message_created":
        return None
    if payload.get("private"):
        return None
    if payload.get("message_type") not in ("incoming", 0):
        return None

    conversa = payload.get("conversation") or {}
    status = conversa.get("status")
    if config.CHATWOOT_BOT_ONLY_PENDING and status != "pending":
        return None

    inbox_id = conversa.get("inbox_id") or (payload.get("inbox") or {}).get("id")
    if config.CHATWOOT_INBOX_ID and str(inbox_id) != str(config.CHATWOOT_INBOX_ID):
        return None

    remetente = payload.get("sender") or {}
    if not remetente:
        remetente = ((conversa.get("meta") or {}).get("sender") or {})
    telefone = _somente_digitos(remetente.get("phone_number"))
    texto = (payload.get("content") or "").strip()
    conversation_id = conversa.get("id") or payload.get("conversation_id")
    event_id = payload.get("id")

    if not all((event_id, conversation_id, telefone, texto)):
        return None
    return {
        "event_id": str(event_id),
        "conversation_id": int(conversation_id),
        "telefone": telefone,
        "texto": texto,
    }


def _processar_evento(evento):
    event_id = evento["event_id"]
    try:
        lead = repo.buscar_ou_criar(evento["telefone"])
        primeira_mensagem_desta_conversa = (
            lead.chatwoot_conversation_id != evento["conversation_id"]
        )
        lead.chatwoot_conversation_id = evento["conversation_id"]
        repo.salvar(lead)

        if primeira_mensagem_desta_conversa and lead.status not in (
            models.TRANSFERIDO,
            models.SEM_INTERESSE,
        ):
            try:
                chatwoot.adicionar_rotulos(evento["conversation_id"], ["ia-atendendo"])
            except Exception as erro:
                app.logger.warning("não foi possível aplicar label inicial: %s", erro)

        lead, resposta = conversation.processar(evento["telefone"], evento["texto"])
        if resposta:
            chatwoot.enviar_mensagem(evento["conversation_id"], resposta)

        if lead.status == models.TRANSFERIDO:
            notificacao.avisar_atendente(lead)
            google_sheets.marcar_lead(lead, google_sheets.QUALIFICADO)
        elif lead.status == models.SEM_INTERESSE:
            chatwoot.encerrar_sem_interesse(lead)
            google_sheets.marcar_lead(lead, google_sheets.SEM_INTERESSE)
        elif primeira_mensagem_desta_conversa:
            google_sheets.marcar_lead(lead, google_sheets.RESPONDEU)

        events.concluir(event_id)
    except Exception as erro:
        events.liberar(event_id)
        app.logger.exception("erro processando evento %s: %s", event_id, erro)


@app.post("/webhook/chatwoot")
def receber_evento_chatwoot():
    corpo_bruto = request.get_data(cache=True)
    if not _assinatura_valida(corpo_bruto, request.headers):
        return jsonify({"erro": "assinatura inválida"}), 401

    evento = _extrair_evento_chatwoot(request.get_json(silent=True))
    if not evento:
        return jsonify({"ok": True, "ignorado": True}), 200
    if not events.reservar(evento["event_id"]):
        return jsonify({"ok": True, "duplicado": True}), 200

    executor.submit(_processar_evento, evento)
    return jsonify({"ok": True}), 200


@app.post("/disparar")
def disparar():
    """Envia um template aprovado para uma lista de leads com opt-in.

    Body mínimo: {"telefones": ["5511999999999"]}
    Opcional:
        "parametros": {"5511999999999": ["Bruno"]}   variáveis do template
        "nomes":      {"5511999999999": "Bruno"}     nome vindo da planilha
        "linhas":     {"5511999999999": 2}           linha de origem na planilha
        "pausa":      3                              segundos entre mensagens

    Este é o ÚNICO lugar que grava no leads.json durante um disparo. A
    varredura da planilha (astrobot-sync) chama esta rota em vez de mexer
    no arquivo — dois processos escrevendo o mesmo JSON se atropelam.
    """
    if not config.META_TEMPLATE_NAME:
        return jsonify({"erro": "META_TEMPLATE_NAME não configurado"}), 503

    corpo = request.get_json(silent=True) or {}
    resultado = disparo.disparar_lote(
        corpo.get("telefones") or [],
        corpo.get("parametros") or {},
        forcar=bool(corpo.get("forcar", False)),
        nomes_por_telefone=corpo.get("nomes") or {},
        linhas_por_telefone=corpo.get("linhas") or {},
        pausa_segundos=float(corpo.get("pausa") or 0),
    )
    erros = resultado["erros"]

    status_http = 207 if erros else 200
    return jsonify(resultado), status_http


@app.get("/leads")
def listar_leads():
    status = request.args.get("status")
    return jsonify([
        {
            "telefone": lead.telefone,
            "nome": lead.nome,
            "status": lead.status,
            "score": lead.score,
            "classificacao": lead.classificacao,
            "regiao": lead.regiao,
            "capital_disponivel": lead.capital_disponivel,
            "prazo": lead.prazo,
            "chatwoot_conversation_id": lead.chatwoot_conversation_id,
        }
        for lead in repo.listar(status)
    ])


@app.get("/saude")
def saude():
    return jsonify({
        "gemini": bool(config.GEMINI_API_KEY),
        "meta_template": bool(config.META_TOKEN and config.META_PHONE_NUMBER_ID and config.META_TEMPLATE_NAME),
        "chatwoot": chatwoot.ativo(),
        "webhook_assinado": bool(config.CHATWOOT_WEBHOOK_SECRET),
        "handoff_configurado": bool(config.CHATWOOT_TEAM_ID or config.CHATWOOT_ASSIGNEE_ID),
        "planilha": google_sheets.ativo(),
        "disparo_automatico": config.DISPARO_AUTOMATICO,
        "disparo_intervalo_min": config.DISPARO_INTERVALO_MIN,
    })


if __name__ == "__main__":
    print(f"\nAstroBot rodando em http://localhost:{config.PORT}")
    print("Webhook do Agent Bot: /webhook/chatwoot")
    if not config.CHATWOOT_WEBHOOK_SECRET:
        print("AVISO: CHATWOOT_WEBHOOK_SECRET vazio; validação HMAC desativada")
    app.run(host="0.0.0.0", port=config.PORT, debug=config.DEBUG)
