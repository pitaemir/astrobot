"""
=============================================================================
 VARREDURA AUTOMÁTICA DA PLANILHA
=============================================================================

 O Google Sheets não avisa quando alguém adiciona uma linha — não existe
 webhook de "contato novo". Então o bot vai lá conferir de tempos em tempos.

 O que impede disparo duplicado é a coluna status_bot: quem já foi
 abordado tem status preenchido e sai da fila. Rodar duas vezes seguidas
 não manda nada duas vezes.

 Travas de segurança, todas no .env:
   DISPARO_AUTOMATICO=false   interruptor geral (padrão: desligado)
   DISPARO_MAX_POR_RODADA     teto de mensagens por varredura
   DISPARO_PAUSA_SEGUNDOS     respiro entre uma mensagem e outra
   DISPARO_DIAS / HORA_*      janela em que pode abordar
=============================================================================
"""

import time
from datetime import datetime, timedelta

import requests

import config
from integrations import google_sheets as planilha


DIAS_PT = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]


def _fuso():
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(config.DISPARO_TIMEZONE)
    except Exception:
        return None


def agora():
    fuso = _fuso()
    return datetime.now(fuso) if fuso else datetime.now()


def _dias_permitidos():
    dias = set()
    for parte in str(config.DISPARO_DIAS).split(","):
        parte = parte.strip()
        if parte.isdigit() and 0 <= int(parte) <= 6:
            dias.add(int(parte))
    return dias or {0, 1, 2, 3, 4}


def dentro_da_janela(momento=None):
    """Devolve (pode_disparar, motivo)."""
    momento = momento or agora()
    dias = _dias_permitidos()

    if momento.weekday() not in dias:
        return False, f"hoje é {DIAS_PT[momento.weekday()]}, fora dos dias permitidos"

    if momento.hour < config.DISPARO_HORA_INICIO:
        return False, (f"são {momento.hour:02d}h, a janela abre às "
                       f"{config.DISPARO_HORA_INICIO:02d}h")

    if momento.hour >= config.DISPARO_HORA_FIM:
        return False, (f"são {momento.hour:02d}h, a janela fechou às "
                       f"{config.DISPARO_HORA_FIM:02d}h")

    return True, "dentro da janela"


def proxima_abertura(momento=None):
    """Quando a janela abre de novo. Usado só para informar nos logs."""
    momento = momento or agora()
    dias = _dias_permitidos()

    candidato = momento.replace(
        hour=config.DISPARO_HORA_INICIO, minute=0, second=0, microsecond=0
    )
    if candidato <= momento:
        candidato += timedelta(days=1)

    for _ in range(8):
        if candidato.weekday() in dias:
            return candidato
        candidato += timedelta(days=1)
    return candidato


# --------------------------------------------------------------------------
def _pedir_disparo(payload):
    """Manda o disparo para o bot via HTTP.

    Por que HTTP e não chamar a função direto: o leads.json é protegido
    por um lock de thread, que só vale dentro de um processo. A varredura
    roda num container separado do servidor — se os dois gravassem no
    mesmo arquivo, um sobrescreveria o outro. Passando pela rota, só o
    processo do servidor escreve.

    Com ASTROBOT_URL vazio, cai no modo local: chama a função no mesmo
    processo. Serve para rodar o comando na mão sem servidor no ar.
    """
    if not config.ASTROBOT_URL:
        from core import disparo
        return disparo.disparar_lote(
            payload["telefones"],
            payload.get("parametros"),
            forcar=payload.get("forcar", False),
            nomes_por_telefone=payload.get("nomes"),
            linhas_por_telefone=payload.get("linhas"),
            pausa_segundos=payload.get("pausa", 0),
        )

    resposta = requests.post(
        f"{config.ASTROBOT_URL.rstrip('/')}/disparar",
        json=payload,
        timeout=300,
    )
    if resposta.status_code not in (200, 207):
        raise RuntimeError(
            f"o bot respondeu {resposta.status_code}: {resposta.text[:200]}"
        )
    return resposta.json()


def disparar_da_planilha(contatos, mapa, forcar=False, pausa=None,
                         registrar=print):
    """Dispara para uma lista de contatos e marca o resultado na planilha.

    Compartilhado pelo comando manual e pela varredura automática, para
    os dois se comportarem exatamente igual.
    """
    if not contatos:
        return {"disparados": [], "ignorados": [], "erros": []}

    resultado = _pedir_disparo({
        "telefones": [c["telefone"] for c in contatos],
        "nomes": {c["telefone"]: c["nome"] for c in contatos if c["nome"]},
        "linhas": {c["telefone"]: c["linha"] for c in contatos},
        "forcar": forcar,
        "pausa": config.DISPARO_PAUSA_SEGUNDOS if pausa is None else pausa,
    })

    if config.PLANILHA_ESCRITA:
        por_telefone = {c["telefone"]: c for c in contatos}
        for telefone in resultado["disparados"]:
            try:
                planilha.marcar(por_telefone[telefone]["linha"],
                                planilha.DISPARADO, mapa)
            except Exception as erro:
                registrar(f"  aviso: não marquei a linha "
                          f"{por_telefone[telefone]['linha']}: {erro}")
        for falha in resultado["erros"]:
            contato = por_telefone.get(falha["telefone"])
            if contato:
                try:
                    planilha.marcar(contato["linha"], planilha.ERRO, mapa)
                except Exception:
                    pass

    return resultado


def rodada(registrar=print, ignorar_janela=False):
    """Uma varredura completa. Devolve um resumo do que aconteceu."""
    if not config.DISPARO_AUTOMATICO:
        return {"pulou": "DISPARO_AUTOMATICO=false"}

    if not config.META_TEMPLATE_NAME:
        return {"pulou": "META_TEMPLATE_NAME não configurado"}

    if not planilha.ativo():
        return {"pulou": "planilha não configurada"}

    if not ignorar_janela:
        pode, motivo = dentro_da_janela()
        if not pode:
            abertura = proxima_abertura()
            return {"pulou": motivo,
                    "proxima": abertura.strftime("%d/%m %H:%M")}

    contatos, problemas, mapa = planilha.ler_contatos()
    fila = planilha.pendentes(contatos)

    if not fila:
        return {"pulou": "nenhum contato novo", "lidos": len(contatos)}

    total = len(fila)
    fila = fila[:config.DISPARO_MAX_POR_RODADA]
    if total > len(fila):
        registrar(f"  {total} na fila; disparando {len(fila)} nesta rodada "
                  f"(teto DISPARO_MAX_POR_RODADA)")

    registrar(f"  disparando para {len(fila)} contato(s)...")
    resultado = disparar_da_planilha(fila, mapa, registrar=registrar)

    return {
        "lidos": len(contatos),
        "na_fila": total,
        "disparados": len(resultado["disparados"]),
        "ignorados": len(resultado["ignorados"]),
        "erros": resultado["erros"],
        "problemas": len(problemas),
    }


# --------------------------------------------------------------------------
def loop(registrar=print):
    """Fica rodando para sempre, uma varredura a cada DISPARO_INTERVALO_MIN."""
    intervalo = max(1, config.DISPARO_INTERVALO_MIN) * 60

    registrar(f"varredura da planilha a cada {config.DISPARO_INTERVALO_MIN} min")
    registrar(f"janela: {config.DISPARO_HORA_INICIO:02d}h-"
              f"{config.DISPARO_HORA_FIM:02d}h, dias "
              f"{config.DISPARO_DIAS} ({config.DISPARO_TIMEZONE})")
    if not config.DISPARO_AUTOMATICO:
        registrar("DISPARO_AUTOMATICO=false — nada será enviado")

    while True:
        marca = agora().strftime("%d/%m %H:%M")
        try:
            resumo = rodada(registrar=registrar)
            if "pulou" in resumo:
                extra = f" (próxima janela: {resumo['proxima']})" if resumo.get("proxima") else ""
                registrar(f"[{marca}] {resumo['pulou']}{extra}")
            else:
                registrar(f"[{marca}] disparados: {resumo['disparados']} | "
                          f"fila: {resumo['na_fila']} | erros: {len(resumo['erros'])}")
                for falha in resumo["erros"]:
                    registrar(f"    ✗ {falha['telefone']}: {falha['erro']}")
        except Exception as erro:
            registrar(f"[{marca}] erro na varredura: {erro}")

        time.sleep(intervalo)
