"""
Configuração central do bot Astrobox.

Todas as credenciais vêm do arquivo .env (nunca commitar o .env!).
Use o ENV_TEMPLATE.txt como base.
"""

import os
from dotenv import load_dotenv

# Carrega .env.gemini primeiro (só a chave do Gemini) e depois .env (o resto)
load_dotenv(".env.gemini")
load_dotenv(".env")


# ---------------------------------------------------------------- Gemini (IA)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")


# ------------------------------------------------- WhatsApp / Meta Cloud API
META_TOKEN = os.getenv("META_TOKEN", "")
META_PHONE_NUMBER_ID = os.getenv("META_PHONE_NUMBER_ID", "")
META_API_VERSION = os.getenv("META_API_VERSION", "v21.0")
META_TEMPLATE_NAME = os.getenv("META_TEMPLATE_NAME", "")
META_TEMPLATE_LANGUAGE = os.getenv("META_TEMPLATE_LANGUAGE", "pt_BR")


# ------------------------------------------------------------------ Chatwoot
CHATWOOT_URL = os.getenv("CHATWOOT_URL", "")
CHATWOOT_ACCOUNT_ID = os.getenv("CHATWOOT_ACCOUNT_ID", "")
CHATWOOT_INBOX_ID = os.getenv("CHATWOOT_INBOX_ID", "")
CHATWOOT_API_TOKEN = os.getenv("CHATWOOT_API_TOKEN", "")
CHATWOOT_WEBHOOK_SECRET = os.getenv("CHATWOOT_WEBHOOK_SECRET", "")
CHATWOOT_TEAM_ID = os.getenv("CHATWOOT_TEAM_ID", "")
CHATWOOT_ASSIGNEE_ID = os.getenv("CHATWOOT_ASSIGNEE_ID", "")
CHATWOOT_BOT_ONLY_PENDING = os.getenv(
    "CHATWOOT_BOT_ONLY_PENDING", "true"
).lower() == "true"


# ------------------------------------------------------ Planilha do Google
GOOGLE_CREDENCIAIS_JSON = os.getenv("GOOGLE_CREDENCIAIS_JSON", "credenciais.json")
PLANILHA_ID = os.getenv("PLANILHA_ID", "")
PLANILHA_ABA = os.getenv("PLANILHA_ABA", "")
PLANILHA_COLUNA_TELEFONE = os.getenv("PLANILHA_COLUNA_TELEFONE", "")
PLANILHA_COLUNA_NOME = os.getenv("PLANILHA_COLUNA_NOME", "")
PLANILHA_COLUNA_STATUS = os.getenv("PLANILHA_COLUNA_STATUS", "status_bot")
PLANILHA_ESCRITA = os.getenv("PLANILHA_ESCRITA", "true").lower() == "true"


# --------------------------------------------------- Disparo automático
# Varredura periódica da planilha. Desligado por padrão: ligue só quando
# estiver confortável, porque isso manda mensagem real para gente real.
# URL do próprio bot. A varredura dispara por aqui em vez de gravar no
# leads.json direto — só um processo pode escrever nesse arquivo.
# Vazio = chama a função no mesmo processo (uso local, sem servidor rodando).
ASTROBOT_URL = os.getenv("ASTROBOT_URL", "")

DISPARO_AUTOMATICO = os.getenv("DISPARO_AUTOMATICO", "false").lower() == "true"
DISPARO_INTERVALO_MIN = int(os.getenv("DISPARO_INTERVALO_MIN", "120"))
DISPARO_MAX_POR_RODADA = int(os.getenv("DISPARO_MAX_POR_RODADA", "20"))
DISPARO_PAUSA_SEGUNDOS = float(os.getenv("DISPARO_PAUSA_SEGUNDOS", "3"))

# Janela em que o bot pode abordar. 0=segunda ... 6=domingo
DISPARO_TIMEZONE = os.getenv("DISPARO_TIMEZONE", "America/Sao_Paulo")
DISPARO_DIAS = os.getenv("DISPARO_DIAS", "0,1,2,3,4")
DISPARO_HORA_INICIO = int(os.getenv("DISPARO_HORA_INICIO", "9"))
DISPARO_HORA_FIM = int(os.getenv("DISPARO_HORA_FIM", "18"))


# ------------------------------------------------------------------ Servidor
PORT = int(os.getenv("PORT", "5000"))
DEBUG = os.getenv("DEBUG", "false").lower() == "true"


def checar_config(obrigatorios):
    """Valida que as variáveis necessárias estão preenchidas.

    Ex: checar_config(["GEMINI_API_KEY", "META_TOKEN"])
    """
    faltando = [nome for nome in obrigatorios if not globals().get(nome)]
    if faltando:
        raise RuntimeError(
            "Faltam variáveis no .env: " + ", ".join(faltando)
        )
