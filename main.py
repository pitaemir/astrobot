"""
Servidor do bot Astrobox.

Endpoints:
    GET  /webhook   → verificação do webhook pela Meta
    POST /webhook   → mensagens recebidas do WhatsApp
    POST /disparar  → inicia a conversa com uma lista de leads
    GET  /leads     → lista os leads e o status de cada um
    GET  /saude     → checagem rápida de configuração

Rodar:
    python3 main.py
"""

from flask import Flask, request, jsonify

import config
from core import conversation
from integrations import whatsapp_meta, chatwoot
from storage import leads as repo

app = Flask(__name__)


# ----------------------------------------------------------- Webhook da Meta
@app.get("/webhook")
def verificar_webhook():
    """A Meta chama isto uma vez ao cadastrar a URL do webhook."""
    modo = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    desafio = request.args.get("hub.challenge")

    if modo == "subscribe" and token == config.META_VERIFY_TOKEN:
        return desafio, 200
    return "token inválido", 403


@app.post("/webhook")
def receber_mensagem():
    telefone, texto = whatsapp_meta.extrair_mensagem(request.get_json(silent=True))

    # Sempre responder 200 rápido: a Meta reenvia o evento se demorarmos.
    if not telefone or not texto:
        return jsonify({"ok": True}), 200

    try:
        lead, resposta = conversation.processar(telefone, texto)
        if resposta:
            whatsapp_meta.enviar_texto(telefone, resposta)
    except Exception as erro:  # não derruba o webhook por causa de um lead
        app.logger.exception("erro processando %s: %s", telefone, erro)

    return jsonify({"ok": True}), 200


# -------------------------------------------------- Disparo para leads novos
@app.post("/disparar")
def disparar():
    """Inicia a conversa com uma lista de números.

    Body: {"telefones": ["5511999999999", "5521888888888"]}

    ⚠️ Em produção, a primeira mensagem para quem nunca falou com o número
    precisa ser um TEMPLATE aprovado (janela de 24h da Meta).
    Ver whatsapp_meta.enviar_template().
    """
    corpo = request.get_json(silent=True) or {}
    telefones = corpo.get("telefones") or []
    repo.importar(telefones)

    enviados = []
    for telefone in telefones:
        limpo = "".join(c for c in str(telefone) if c.isdigit())
        lead, mensagem = conversation.iniciar(limpo)
        whatsapp_meta.enviar_texto(limpo, mensagem)
        enviados.append(limpo)

    return jsonify({"disparados": enviados}), 200


# ------------------------------------------------------------------ Consulta
@app.get("/leads")
def listar_leads():
    status = request.args.get("status")
    return jsonify([
        {
            "telefone": l.telefone,
            "nome": l.nome,
            "status": l.status,
            "score": l.score,
            "classificacao": l.classificacao,
            "regiao": l.regiao,
            "capital_disponivel": l.capital_disponivel,
            "prazo": l.prazo,
        }
        for l in repo.listar(status)
    ])


@app.get("/saude")
def saude():
    return jsonify({
        "gemini": bool(config.GEMINI_API_KEY),
        "whatsapp": not whatsapp_meta.modo_simulacao(),
        "chatwoot": chatwoot.ativo(),
        "atendente": bool(config.ATENDENTE_WHATSAPP),
    })


if __name__ == "__main__":
    print(f"\n🚀 Bot Astrobox rodando em http://localhost:{config.PORT}")
    if whatsapp_meta.modo_simulacao():
        print("⚠️  WhatsApp em MODO SIMULAÇÃO (META_TOKEN vazio no .env)")
    if not chatwoot.ativo():
        print("⚠️  Chatwoot desligado (CHATWOOT_URL vazio no .env)")
    print()
    app.run(host="0.0.0.0", port=config.PORT, debug=config.DEBUG)
