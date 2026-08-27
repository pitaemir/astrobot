"""
=============================================================================
 PLANILHA DO GOOGLE — origem dos contatos
=============================================================================

 Lê a lista de leads de uma planilha do Google e escreve de volta o status
 de cada contato, para a planilha virar o painel de acompanhamento.

 Autenticação: Service Account.
   1. console.cloud.google.com → criar projeto
   2. Ativar "Google Sheets API"
   3. Criar uma Service Account → Chaves → Adicionar chave → JSON
   4. Salvar o JSON como credenciais.json na raiz do projeto
   5. Compartilhar a planilha (botão Compartilhar) com o e-mail
      client_email que está dentro do JSON, como Editor

 A leitura é tolerante: detecta sozinha as colunas de telefone, nome e
 status pelo cabeçalho. Se os nomes forem exóticos, dá para forçar pelo
 .env (PLANILHA_COLUNA_TELEFONE etc).
=============================================================================
"""

import re
from datetime import datetime

import config


# Status que o bot escreve de volta na planilha
PENDENTE = ""
DISPARADO = "disparado"
RESPONDEU = "respondeu"
QUALIFICADO = "qualificado"
SEM_INTERESSE = "sem interesse"
ERRO = "erro"

# Um contato com um destes status não é abordado de novo
JA_TRABALHADOS = {DISPARADO, RESPONDEU, QUALIFICADO, SEM_INTERESSE}


# --------------------------------------------------------------------------
# Detecção de colunas
# --------------------------------------------------------------------------
NOMES_TELEFONE = [
    "telefone", "celular", "whatsapp", "whats", "fone", "numero",
    "número", "contato", "phone", "tel",
]
NOMES_NOME = ["nome", "name", "lead", "cliente", "responsavel", "responsável"]
NOMES_STATUS = ["status_bot", "status bot", "status", "situacao", "situação"]


def achar_linha_cabecalho(linhas, limite=10):
    """Índice (0-based) da primeira linha que parece um cabeçalho.

    Planilha real costuma ter linha em branco ou um título antes da
    tabela. Cabeçalho = primeira linha com pelo menos duas células
    preenchidas, olhando só as primeiras `limite` linhas.
    """
    for indice, linha in enumerate(linhas[:limite]):
        preenchidas = [c for c in linha if str(c).strip()]
        if len(preenchidas) >= 2:
            return indice
    for indice, linha in enumerate(linhas[:limite]):
        if any(str(c).strip() for c in linha):
            return indice
    return 0


def _agora_local():
    """Horário no fuso configurado — o mesmo que os logs usam.

    Sem isso a planilha grava no fuso do container (UTC), e a equipe lê
    'atualizado_em' três horas adiantado.
    """
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo(config.DISPARO_TIMEZONE))
    except Exception:
        return datetime.now()


def _limpar(texto):
    return re.sub(r"\s+", " ", str(texto or "")).strip().lower()


def _achar_coluna(cabecalho, candidatos, forcado=None, obrigatoria=True):
    """Devolve o índice (0-based) da coluna, ou None.

    obrigatoria=False: um nome forçado que não existe devolve None em vez
    de dar erro. É o caso da coluna de status, cujo nome no .env também
    serve para criá-la quando ela ainda não está na planilha.
    """
    normalizado = [_limpar(c) for c in cabecalho]

    if forcado:
        alvo = _limpar(forcado)
        if alvo in normalizado:
            return normalizado.index(alvo)
        if not obrigatoria:
            return None
        raise ValueError(
            f"A coluna '{forcado}' não existe na planilha. "
            f"Colunas encontradas: {', '.join(c for c in cabecalho if c)}"
        )

    # 1ª passada: nome exato
    for candidato in candidatos:
        if candidato in normalizado:
            return normalizado.index(candidato)

    # 2ª passada: nome contém o candidato (ex: "telefone do lead")
    for candidato in candidatos:
        for indice, coluna in enumerate(normalizado):
            if coluna and candidato in coluna:
                return indice

    return None


# --------------------------------------------------------------------------
# Normalização de telefone (Brasil)
# --------------------------------------------------------------------------
def normalizar_telefone(bruto):
    """Devolve (telefone, aviso).

    telefone no formato internacional só com dígitos: 5519999990000
    aviso é None quando está tudo certo.
    """
    digitos = re.sub(r"\D", "", str(bruto or ""))

    if not digitos:
        return None, "vazio" if not str(bruto or "").strip() else "sem dígitos"

    # Já veio com o 55 na frente
    if digitos.startswith("55") and len(digitos) in (12, 13):
        return digitos, None

    # DDD + número, sem o código do país
    if len(digitos) == 11:                      # celular com o 9
        return "55" + digitos, None
    if len(digitos) == 10:                      # fixo, ou celular antigo
        return "55" + digitos, "10 dígitos: pode ser fixo ou celular sem o 9"

    if len(digitos) in (8, 9):
        return None, "sem DDD"

    return None, f"{len(digitos)} dígitos — formato não reconhecido"


# --------------------------------------------------------------------------
# Interpretação (pura — testável sem internet)
# --------------------------------------------------------------------------
def interpretar_planilha(linhas, coluna_telefone=None, coluna_nome=None,
                         coluna_status=None):
    """Transforma as linhas cruas da planilha em contatos.

    linhas: lista de listas, a primeira sendo o cabeçalho.

    Devolve (contatos, problemas, mapa).
        contatos: [{"linha", "telefone", "nome", "status", "bruto"}]
        problemas: [{"linha", "bruto", "motivo"}]
        mapa: {"telefone": i, "nome": i, "status": i, "cabecalho": [...]}
    """
    if not linhas or not any(any(str(c).strip() for c in l) for l in linhas):
        raise ValueError(
            "A planilha (ou a aba escolhida) está vazia. "
            "Rode: python3 importar_planilha.py inspecionar"
        )

    inicio = achar_linha_cabecalho(linhas)
    cabecalho = linhas[inicio]
    indice_tel = _achar_coluna(cabecalho, NOMES_TELEFONE, coluna_telefone)
    if indice_tel is None:
        vistas = ", ".join(str(c) for c in cabecalho if str(c).strip())
        raise ValueError(
            "Não encontrei a coluna de telefone.\n"
            f"  Cabeçalho lido (linha {inicio + 1}): "
            + (vistas or "(linha vazia)")
            + "\n  Rode 'python3 importar_planilha.py inspecionar' para ver "
              "a planilha crua, ou defina PLANILHA_COLUNA_TELEFONE no .env."
        )

    indice_nome = _achar_coluna(cabecalho, NOMES_NOME, coluna_nome)
    indice_status = _achar_coluna(
        cabecalho, NOMES_STATUS, coluna_status, obrigatoria=False
    )

    mapa = {
        "telefone": indice_tel,
        "nome": indice_nome,
        "status": indice_status,
        "cabecalho": cabecalho,
        "linha_cabecalho": inicio + 1,
    }

    def celula(linha, indice):
        if indice is None or indice >= len(linha):
            return ""
        return str(linha[indice]).strip()

    contatos, problemas, vistos = [], [], set()

    for numero_linha, linha in enumerate(linhas[inicio + 1:], start=inicio + 2):
        bruto = celula(linha, indice_tel)
        if not bruto and not any(str(c).strip() for c in linha):
            continue  # linha totalmente vazia

        telefone, aviso = normalizar_telefone(bruto)

        if telefone is None:
            problemas.append({
                "linha": numero_linha, "bruto": bruto, "motivo": aviso,
            })
            continue

        if telefone in vistos:
            problemas.append({
                "linha": numero_linha, "bruto": bruto, "motivo": "duplicado",
            })
            continue
        vistos.add(telefone)

        contatos.append({
            "linha": numero_linha,
            "telefone": telefone,
            "nome": celula(linha, indice_nome) or None,
            "status": _limpar(celula(linha, indice_status)),
            "bruto": bruto,
            "aviso": aviso,
        })

    return contatos, problemas, mapa


def pendentes(contatos):
    """Só os contatos que ainda não foram trabalhados."""
    return [c for c in contatos if c["status"] not in JA_TRABALHADOS]


# --------------------------------------------------------------------------
# Acesso à planilha
# --------------------------------------------------------------------------
_aba = None


def ativo():
    return bool(config.PLANILHA_ID and config.GOOGLE_CREDENCIAIS_JSON)


def _abrir_aba():
    """Conecta na planilha (uma vez só) e devolve a worksheet."""
    global _aba
    if _aba is not None:
        return _aba

    import os
    import gspread

    if not config.PLANILHA_ID:
        raise RuntimeError("PLANILHA_ID não configurado no .env")
    if not os.path.exists(config.GOOGLE_CREDENCIAIS_JSON):
        raise RuntimeError(
            f"Arquivo de credenciais não encontrado: "
            f"{config.GOOGLE_CREDENCIAIS_JSON}\n"
            "Baixe o JSON da Service Account e salve com esse nome."
        )

    cliente = gspread.service_account(filename=config.GOOGLE_CREDENCIAIS_JSON)

    try:
        planilha = cliente.open_by_key(config.PLANILHA_ID)
    except Exception as erro:
        raise RuntimeError(
            f"Não consegui abrir a planilha {config.PLANILHA_ID}: {erro}\n"
            "Confira se você compartilhou a planilha com o client_email "
            "que está dentro do credenciais.json."
        ) from erro

    _aba = (planilha.worksheet(config.PLANILHA_ABA)
            if config.PLANILHA_ABA else planilha.sheet1)
    return _aba


def ler_contatos():
    """Lê a planilha e devolve (contatos, problemas, mapa)."""
    linhas = _abrir_aba().get_all_values()
    return interpretar_planilha(
        linhas,
        config.PLANILHA_COLUNA_TELEFONE or None,
        config.PLANILHA_COLUNA_NOME or None,
        config.PLANILHA_COLUNA_STATUS or None,
    )


def garantir_coluna_status(mapa):
    """Cria a coluna de status na planilha se ela ainda não existir.

    Devolve o índice (0-based) da coluna.
    """
    if mapa.get("status") is not None:
        return mapa["status"]

    aba = _abrir_aba()
    indice = len(mapa["cabecalho"])
    aba.update_cell(1, indice + 1, config.PLANILHA_COLUNA_STATUS or "status_bot")
    aba.update_cell(1, indice + 2, "atualizado_em")
    mapa["status"] = indice
    return indice


def marcar(linha, status, mapa):
    """Escreve o status de um contato de volta na planilha.

    linha: número da linha na planilha (1-based, como aparece no Sheets)
    """
    if not config.PLANILHA_ESCRITA:
        return None

    indice = garantir_coluna_status(mapa)
    aba = _abrir_aba()
    agora = _agora_local().strftime("%d/%m/%Y %H:%M")

    aba.batch_update([
        {"range": _celula_a1(linha, indice), "values": [[status]]},
        {"range": _celula_a1(linha, indice + 1), "values": [[agora]]},
    ])
    return status


def _celula_a1(linha, coluna_zero_based):
    """(2, 7) → 'H2'"""
    numero = coluna_zero_based + 1
    letras = ""
    while numero > 0:
        numero, resto = divmod(numero - 1, 26)
        letras = chr(65 + resto) + letras
    return f"{letras}{linha}"


# Estrutura que o bot espera. "origem" é livre — serve para a equipe
# saber de onde veio o lead; o bot não usa, mas também não atrapalha.
COLUNAS_PADRAO = ["nome", "telefone", "origem", "status_bot", "atualizado_em"]


def preparar_planilha(nome_aba=None, forcar=False):
    """Escreve na planilha o cabeçalho que o bot espera.

    Nunca sobrescreve dados: se a aba de destino já tiver conteúdo, para
    e explica, a não ser que forcar=True (que substitui só a linha 1).

    Devolve {"aba", "criada", "colunas"}.
    """
    import gspread

    cliente = gspread.service_account(filename=config.GOOGLE_CREDENCIAIS_JSON)
    planilha = cliente.open_by_key(config.PLANILHA_ID)

    alvo = nome_aba or config.PLANILHA_ABA or None
    existentes = {aba.title: aba for aba in planilha.worksheets()}
    criada = False

    if alvo and alvo in existentes:
        aba = existentes[alvo]
    elif alvo:
        aba = planilha.add_worksheet(title=alvo, rows=500,
                                     cols=len(COLUNAS_PADRAO) + 2)
        criada = True
    else:
        aba = planilha.sheet1

    if not criada and not forcar:
        conteudo = aba.get_all_values()
        if any(any(str(c).strip() for c in linha) for linha in conteudo):
            raise ValueError(
                f"A aba '{aba.title}' já tem conteúdo — não vou sobrescrever.\n"
                "  Para criar uma aba nova:  --aba Leads\n"
                "  Para substituir só o cabeçalho desta aba:  --forcar"
            )

    fim = _celula_a1(1, len(COLUNAS_PADRAO) - 1)
    aba.batch_update([{"range": f"A1:{fim}", "values": [COLUNAS_PADRAO]}])

    try:
        aba.format(f"A1:{fim}", {"textFormat": {"bold": True}})
        aba.freeze(rows=1)
    except Exception:
        pass  # formatação é cosmética; não vale derrubar o comando

    return {"aba": aba.title, "criada": criada, "colunas": COLUNAS_PADRAO}


def inspecionar():
    """Devolve a estrutura crua da planilha, para diagnóstico."""
    import gspread

    cliente = gspread.service_account(filename=config.GOOGLE_CREDENCIAIS_JSON)
    planilha = cliente.open_by_key(config.PLANILHA_ID)
    return {
        "titulo": planilha.title,
        "abas": [
            {"nome": aba.title, "linhas": aba.row_count,
             "colunas": aba.col_count, "amostra": aba.get_all_values()[:8]}
            for aba in planilha.worksheets()
        ],
    }


_mapa_cache = None


def _mapa_atual():
    """Mapa de colunas, lido uma vez por processo."""
    global _mapa_cache
    if _mapa_cache is None:
        _, _, _mapa_cache = ler_contatos()
    return _mapa_cache


def marcar_lead(lead, status):
    """Atualiza o status de um lead na planilha, se ele veio de lá.

    Silencioso quando a planilha não está configurada ou quando o lead
    não tem linha de origem — o bot nunca quebra por causa disso.
    """
    if not ativo() or not config.PLANILHA_ESCRITA:
        return None
    if not getattr(lead, "planilha_linha", None):
        return None
    try:
        return marcar(lead.planilha_linha, status, _mapa_atual())
    except Exception:
        return None
