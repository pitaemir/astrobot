"""Deduplicação simples dos webhooks recebidos do Chatwoot."""

import json
import os
import threading


ARQUIVO = os.getenv("ARQUIVO_EVENTOS", "processed_events.json")
LIMITE = int(os.getenv("LIMITE_EVENTOS", "5000"))
_trava = threading.Lock()
_em_processamento = set()


def _ler():
    if not os.path.exists(ARQUIVO):
        return []
    try:
        with open(ARQUIVO, "r", encoding="utf-8") as arquivo:
            valor = json.load(arquivo)
            return valor if isinstance(valor, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def reservar(event_id):
    chave = str(event_id)
    with _trava:
        if chave in _em_processamento or chave in set(_ler()):
            return False
        _em_processamento.add(chave)
        return True


def concluir(event_id):
    chave = str(event_id)
    with _trava:
        eventos = _ler()
        if chave not in eventos:
            eventos.append(chave)
        with open(ARQUIVO, "w", encoding="utf-8") as arquivo:
            json.dump(eventos[-LIMITE:], arquivo)
        _em_processamento.discard(chave)


def liberar(event_id):
    with _trava:
        _em_processamento.discard(str(event_id))
