"""
=============================================================================
 PONTUAÇÃO E CLASSIFICAÇÃO DE LEADS
=============================================================================

"""

QUENTE = "QUENTE"
MORNO = "MORNO"
FRIO = "FRIO"
A_DEFINIR = "A DEFINIR"

# Faixas de corte — ajustar quando a régua de pontos for definida.
CORTE_QUENTE = 70
CORTE_MORNO = 40


def calcular_score(lead):
    """Devolve (score, detalhe) a partir das respostas do lead.

    TODO: implementar quando a Astrobox enviar os critérios.

    Estrutura esperada quando for implementar:

        detalhe = {
            "respondeu":          0,   # teve resposta do lead
            "regiao":             0,
            "capital_ou_interior":0,
            "habitantes":         0,
            "capital_disponivel": 0,
            "prazo":              0,
        }
        return sum(detalhe.values()), detalhe
    """
    return None, {}


def classificar(score):
    """Converte o score numérico em QUENTE / MORNO / FRIO."""
    if score is None:
        return A_DEFINIR
    if score >= CORTE_QUENTE:
        return QUENTE
    if score >= CORTE_MORNO:
        return MORNO
    return FRIO


def qualificar(lead):
    """Calcula e grava score + classificação no lead. Devolve o lead."""
    score, detalhe = calcular_score(lead)
    lead.score = score
    lead.detalhe_score = detalhe
    lead.classificacao = classificar(score)
    return lead
