"""
Simulador de conversa — testa o bot no terminal, sem WhatsApp.

Você faz o papel do lead. O bot responde de verdade (via Gemini), grava
o lead no leads.json e, ao final, mostra o resumo que iria para o
atendente humano.

Rodar:
    python3 simulate.py
"""

import core.models as models
from core import conversation
from storage import leads as repo

TELEFONE_TESTE = "5511999990000"


def main():
    print("\n" + "=" * 62)
    print("🚀 SIMULADOR — Bot de qualificação Astrobox")
    print("=" * 62)
    print("\nVocê é o LEAD. Digite 'sair' para encerrar.")
    print("Digite 'reset' para começar um lead do zero.\n")

    lead, abertura = conversation.iniciar(TELEFONE_TESTE)
    print(f"🤖 Bot: {abertura}")

    while True:
        try:
            entrada = input("\n👤 Lead: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\n👋 Até logo!\n")
            return

        if entrada.lower() == "sair":
            print("\n👋 Até logo!\n")
            return

        if entrada.lower() == "reset":
            repo.salvar(models.Lead(telefone=TELEFONE_TESTE))
            lead, abertura = conversation.iniciar(TELEFONE_TESTE)
            print(f"\n♻️  Lead zerado.\n\n🤖 Bot: {abertura}")
            continue

        if not entrada:
            continue

        try:
            lead, resposta = conversation.processar(TELEFONE_TESTE, entrada)
        except Exception as erro:
            print(f"\n❌ Erro: {erro}")
            return

        if resposta:
            print(f"\n🤖 Bot: {resposta}")

        if lead.status in (models.TRANSFERIDO, models.SEM_INTERESSE):
            print("\n" + "=" * 62)
            print(f"✅ Conversa encerrada — status: {lead.status}")
            print("=" * 62)
            print("\nResumo que vai para o atendente:\n")
            print(lead.resumo_para_atendente())
            print("\n(digite 'reset' para testar outro lead)\n")


if __name__ == "__main__":
    main()
