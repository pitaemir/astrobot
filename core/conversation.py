"""
Motor da conversa.

"""

import core.models as models
from core import scoring
from integrations import gemini_client
from prompts.qualificacao import CAMPOS_OBRIGATORIOS, MENSAGEM_ABERTURA
from storage import leads as repo


def iniciar(telefone):
    """Prepara o lead e devolve a mensagem de abertura.

    Não envia nada — quem envia é a camada de WhatsApp.
    """
    lead = repo.buscar_ou_criar(telefone)
    lead.status = models.EM_CONVERSA

    lead.registrar("bot", MENSAGEM_ABERTURA)
    repo.salvar(lead)

    return lead, MENSAGEM_ABERTURA


def processar(telefone, mensagem):
    """Processa uma mensagem recebida do lead.

    Devolve (lead, resposta_do_bot). resposta_do_bot pode ser None se o
    lead já tinha sido transferido para um humano.
    """
    lead = repo.buscar_ou_criar(telefone)

    # Lead já entregue ao atendente: o bot cala a boca e só espelha.
    if lead.status in (models.TRANSFERIDO, models.SEM_INTERESSE):
        lead.registrar("lead", mensagem)
        repo.salvar(lead)
        return lead, None

    if lead.status == models.NOVO:
        lead.status = models.EM_CONVERSA

    resultado = gemini_client.gerar_resposta(lead.historico, mensagem)

    lead.registrar("lead", mensagem)
    lead.aplicar_dados(resultado["dados"])
    lead.pedir_humano = lead.pedir_humano or resultado["pedir_humano"]

    resposta = resultado["resposta"]
    if resposta:
        lead.registrar("bot", resposta)

    if _deve_encerrar(lead, resultado):
        _encerrar(lead)

    repo.salvar(lead)
    return lead, resposta


# --------------------------------------------------------------------------
def _deve_encerrar(lead, resultado):
    if lead.pedir_humano:
        return True
    if lead.interesse_ativo is False:
        return True
    if resultado["finalizado"]:
        return True
    return not lead.campos_faltando(CAMPOS_OBRIGATORIOS)


def _encerrar(lead):
    """Fecha a qualificação: pontua, classifica e avisa o atendente."""
    if lead.interesse_ativo is False and not lead.pedir_humano:
        lead.status = models.SEM_INTERESSE
        return

    scoring.qualificar(lead)
    lead.status = models.QUALIFICADO
    repo.salvar(lead)

    lead.status = models.TRANSFERIDO
