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
# TODO: preencher quando o colega finalizar o cadastro do número na Meta
META_TOKEN = os.getenv("META_TOKEN", "")
META_PHONE_NUMBER_ID = os.getenv("META_PHONE_NUMBER_ID", "")
META_VERIFY_TOKEN = os.getenv("META_VERIFY_TOKEN", "astrobox_verify")
META_API_VERSION = os.getenv("META_API_VERSION", "v21.0")


# ------------------------------------------------------------------ Chatwoot
# TODO: preencher com os dados da VM do colega
CHATWOOT_URL = os.getenv("CHATWOOT_URL", "")
CHATWOOT_ACCOUNT_ID = os.getenv("CHATWOOT_ACCOUNT_ID", "")
CHATWOOT_INBOX_ID = os.getenv("CHATWOOT_INBOX_ID", "")
CHATWOOT_API_TOKEN = os.getenv("CHATWOOT_API_TOKEN", "")


# -------------------------------------------------------- Atendente humano
# Número que recebe o aviso quando um lead termina a qualificação.
# Formato internacional sem "+": 5511999999999
ATENDENTE_WHATSAPP = os.getenv("ATENDENTE_WHATSAPP", "")


# ------------------------------------------------------------------ Servidor
PORT = int(os.getenv("PORT", "5000"))
DEBUG = os.getenv("DEBUG", "true").lower() == "true"


def checar_config(obrigatorios):
    """Valida que as variáveis necessárias estão preenchidas.

    Ex: checar_config(["GEMINI_API_KEY", "META_TOKEN"])
    """
    faltando = [nome for nome in obrigatorios if not globals().get(nome)]
    if faltando:
        raise RuntimeError(
            "Faltam variáveis no .env: " + ", ".join(faltando)
        )
