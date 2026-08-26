"""
Cliente do Gemini.

Único ponto do projeto que fala com a API do Google. Se um dia trocar de
modelo (OpenAI, Claude, Llama local), só este arquivo muda.
"""

import json
import google.generativeai as genai

import config
from prompts.qualificacao import montar_prompt


_modelo = None


def get_modelo():
    """Cria (uma vez só) o modelo já com o prompt de sistema carregado."""
    global _modelo
    if _modelo is None:
        config.checar_config(["GEMINI_API_KEY"])
        genai.configure(api_key=config.GEMINI_API_KEY)
        _modelo = genai.GenerativeModel(
            model_name=config.GEMINI_MODEL,
            system_instruction=montar_prompt(),
            generation_config={
                "temperature": 0.6,
                "response_mime_type": "application/json",
            },
        )
    return _modelo


def _historico_para_gemini(historico):
    """Converte o histórico do Lead para o formato de conteúdo do Gemini."""
    convertido = []
    for msg in historico:
        papel = "user" if msg["autor"] == "lead" else "model"
        convertido.append({"role": papel, "parts": [msg["texto"]]})
    return convertido


def gerar_resposta(historico, mensagem_lead):
    """Envia a conversa ao Gemini e devolve o dicionário parseado.

    Retorna sempre um dict com as chaves:
        resposta (str), dados (dict), finalizado (bool), pedir_humano (bool)
    """
    chat = get_modelo().start_chat(history=_historico_para_gemini(historico))
    resposta = chat.send_message(mensagem_lead)
    return _parsear(resposta.text)


def _parsear(texto):
    """Lê o JSON devolvido pelo modelo, tolerando cercas de markdown."""
    limpo = (texto or "").strip()
    if limpo.startswith("```"):
        limpo = limpo.split("```")[1]
        if limpo.lstrip().startswith("json"):
            limpo = limpo.lstrip()[4:]
        limpo = limpo.strip()

    try:
        dados = json.loads(limpo)
    except json.JSONDecodeError:
        # Se o modelo escorregar e mandar texto puro, ainda entregamos algo.
        return {
            "resposta": texto,
            "dados": {},
            "finalizado": False,
            "pedir_humano": False,
        }

    return {
        "resposta": dados.get("resposta", ""),
        "dados": dados.get("dados") or {},
        "finalizado": bool(dados.get("finalizado")),
        "pedir_humano": bool(dados.get("pedir_humano")),
    }
