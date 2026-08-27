"""
Varredura automática da planilha.

Fica rodando, e a cada DISPARO_INTERVALO_MIN minutos confere se apareceu
contato novo — disparando o template para quem ainda não tem status.

    python3 sincronizar.py              roda para sempre
    python3 sincronizar.py --uma-vez    faz uma varredura e sai
    python3 sincronizar.py --agora      ignora a janela de horário (teste)

Em produção quem roda isso é o serviço 'astrobot-sync' do docker-compose.

Nada é enviado enquanto DISPARO_AUTOMATICO=false no .env.
"""

import argparse
import sys

import config
from core import sincronizacao


def registrar(mensagem):
    print(mensagem, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uma-vez", action="store_true",
                        help="faz uma varredura e encerra")
    parser.add_argument("--agora", action="store_true",
                        help="ignora a janela de horário")
    args = parser.parse_args()

    if not args.uma_vez:
        sincronizacao.loop(registrar)
        return

    momento = sincronizacao.agora().strftime("%d/%m %H:%M")
    resumo = sincronizacao.rodada(registrar, ignorar_janela=args.agora)

    if "pulou" in resumo:
        extra = f"  (próxima janela: {resumo['proxima']})" if resumo.get("proxima") else ""
        registrar(f"[{momento}] {resumo['pulou']}{extra}")
        if resumo["pulou"] == "DISPARO_AUTOMATICO=false":
            registrar("\nPara ligar, no .env: DISPARO_AUTOMATICO=true")
        return

    registrar(f"[{momento}] lidos: {resumo['lidos']} | fila: {resumo['na_fila']} | "
              f"disparados: {resumo['disparados']} | erros: {len(resumo['erros'])}")
    for falha in resumo["erros"]:
        registrar(f"   ✗ {falha['telefone']}: {falha['erro']}")
    if resumo["erros"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
