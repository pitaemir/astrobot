"""
Lê os contatos da planilha do Google.

Três modos, do mais seguro para o mais definitivo:

    python3 importar_planilha.py ler
        Só lê e mostra na tela. Não grava nada, em lugar nenhum.
        É por aqui que você começa.

    python3 importar_planilha.py importar
        Grava os contatos no leads.json do bot. Ainda não manda mensagem.

    python3 importar_planilha.py disparar
        Importa e envia o template aprovado da Meta para cada contato,
        marcando "disparado" de volta na planilha.

Opções úteis:
    --limite 5      trabalha só com os 5 primeiros (ótimo pro primeiro teste)
    --todos         inclui quem já tem status na planilha
    --forcar        reaborda quem já está em conversa
"""

import argparse
import sys

import config
from integrations import google_sheets as planilha


VERDE, AMARELO, VERMELHO, CINZA, RESET = (
    "\033[92m", "\033[93m", "\033[91m", "\033[90m", "\033[0m"
)


def _cabecalho(titulo):
    print(f"\n{'=' * 66}\n{titulo}\n{'=' * 66}")


def _carregar(args):
    """Lê a planilha e aplica os filtros da linha de comando."""
    if not planilha.ativo():
        print(f"{VERMELHO}✗ Planilha não configurada.{RESET}")
        print("\nPreencha no .env:")
        print("    PLANILHA_ID=...              (o id que aparece na URL)")
        print("    GOOGLE_CREDENCIAIS_JSON=credenciais.json")
        sys.exit(1)

    try:
        contatos, problemas, mapa = planilha.ler_contatos()
    except Exception as erro:
        print(f"\n{VERMELHO}✗ {erro}{RESET}\n")
        sys.exit(1)

    selecionados = contatos if args.todos else planilha.pendentes(contatos)
    if args.limite:
        selecionados = selecionados[:args.limite]

    return contatos, selecionados, problemas, mapa


def _mostrar(contatos, selecionados, problemas, mapa):
    cabecalho = [c for c in mapa["cabecalho"] if c]
    print(f"\n{CINZA}Colunas da planilha: {', '.join(cabecalho)}{RESET}")

    def nome_col(chave):
        indice = mapa.get(chave)
        if indice is None:
            return f"{AMARELO}não encontrada{RESET}"
        return f"{VERDE}{mapa['cabecalho'][indice]}{RESET}"

    print(f"\nColuna de telefone : {nome_col('telefone')}")
    print(f"Coluna de nome     : {nome_col('nome')}")
    print(f"Coluna de status   : {nome_col('status')}")

    _cabecalho(f"CONTATOS LIDOS — {len(selecionados)} selecionados "
               f"de {len(contatos)} válidos")

    if not selecionados:
        print(f"\n{AMARELO}Nenhum contato pendente.{RESET}")
        print("Use --todos para incluir quem já tem status preenchido.\n")
    else:
        print(f"\n{'linha':>6}  {'telefone':<16} {'nome':<24} status")
        print(f"{'-' * 66}")
        for contato in selecionados:
            aviso = f"  {AMARELO}⚠ {contato['aviso']}{RESET}" if contato["aviso"] else ""
            print(
                f"{contato['linha']:>6}  "
                f"{contato['telefone']:<16} "
                f"{(contato['nome'] or '—')[:24]:<24} "
                f"{contato['status'] or '—'}{aviso}"
            )

    if problemas:
        _cabecalho(f"LINHAS IGNORADAS — {len(problemas)}")
        print()
        for problema in problemas:
            print(f"{VERMELHO}  linha {problema['linha']:>4}{RESET}  "
                  f"{problema['bruto'] or '(vazio)':<22} → {problema['motivo']}")

    print()


def _gravar_origem(selecionados):
    """Guarda no lead o nome e a linha de onde ele veio na planilha.

    A linha é o que permite o bot escrever o status de volta depois,
    quando o lead responder lá no Chatwoot.
    """
    from storage import leads as repo

    for contato in selecionados:
        lead = repo.buscar_ou_criar(contato["telefone"])
        mudou = False
        if contato["nome"] and not lead.nome:
            lead.nome = contato["nome"]
            mudou = True
        if lead.planilha_linha != contato["linha"]:
            lead.planilha_linha = contato["linha"]
            mudou = True
        if mudou:
            repo.salvar(lead)


# --------------------------------------------------------------------------
def comando_ler(args):
    contatos, selecionados, problemas, mapa = _carregar(args)
    _mostrar(contatos, selecionados, problemas, mapa)
    print(f"{CINZA}Nada foi gravado. Para salvar no bot: "
          f"python3 importar_planilha.py importar{RESET}\n")


def comando_importar(args):
    from storage import leads as repo

    contatos, selecionados, problemas, mapa = _carregar(args)
    _mostrar(contatos, selecionados, problemas, mapa)

    if not selecionados:
        return

    criados = repo.importar([c["telefone"] for c in selecionados])
    _gravar_origem(selecionados)

    print(f"{VERDE}✓ {criados} leads novos gravados no bot"
          f" ({len(selecionados) - criados} já existiam).{RESET}\n")


def comando_disparar(args):
    from core import disparo

    contatos, selecionados, problemas, mapa = _carregar(args)
    _mostrar(contatos, selecionados, problemas, mapa)

    if not selecionados:
        return

    if not config.META_TEMPLATE_NAME:
        print(f"{VERMELHO}✗ META_TEMPLATE_NAME não configurado no .env.{RESET}")
        print("  A primeira mensagem para quem nunca falou com o número "
              "precisa ser um template aprovado pela Meta.\n")
        sys.exit(1)

    print(f"{AMARELO}Vai disparar para {len(selecionados)} contatos "
          f"usando o template '{config.META_TEMPLATE_NAME}'.{RESET}")
    if input("Confirma? (digite SIM) ").strip().upper() != "SIM":
        print("Cancelado.\n")
        return

    _gravar_origem(selecionados)
    nomes = {c["telefone"]: c["nome"] for c in selecionados if c["nome"]}
    resultado = disparo.disparar_lote(
        [c["telefone"] for c in selecionados],
        forcar=args.forcar,
        nomes_por_telefone=nomes,
    )

    # Marca o resultado de volta na planilha
    por_telefone = {c["telefone"]: c for c in selecionados}
    if config.PLANILHA_ESCRITA:
        for telefone in resultado["disparados"]:
            planilha.marcar(por_telefone[telefone]["linha"],
                            planilha.DISPARADO, mapa)
        for falha in resultado["erros"]:
            planilha.marcar(por_telefone[falha["telefone"]]["linha"],
                            planilha.ERRO, mapa)

    _cabecalho("RESULTADO")
    print(f"\n{VERDE}  disparados : {len(resultado['disparados'])}{RESET}")
    print(f"{CINZA}  ignorados  : {len(resultado['ignorados'])}{RESET}")
    print(f"{VERMELHO}  erros      : {len(resultado['erros'])}{RESET}")
    for falha in resultado["erros"]:
        print(f"    {falha['telefone']}: {falha['erro']}")
    print()


# --------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Lê os contatos dos leads de uma planilha do Google.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="comando", required=True)

    for nome, funcao, ajuda in [
        ("ler", comando_ler, "só mostra na tela, não grava nada"),
        ("importar", comando_importar, "grava os contatos no bot"),
        ("disparar", comando_disparar, "importa e envia o template"),
    ]:
        p = sub.add_parser(nome, help=ajuda)
        p.add_argument("--limite", type=int, help="trabalha só com os N primeiros")
        p.add_argument("--todos", action="store_true",
                       help="inclui quem já tem status na planilha")
        p.add_argument("--forcar", action="store_true",
                       help="reaborda quem já está em conversa")
        p.set_defaults(funcao=funcao)

    args = parser.parse_args()
    args.funcao(args)


if __name__ == "__main__":
    main()
