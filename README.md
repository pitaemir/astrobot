# AstroBot — qualificação de leads no WhatsApp + Chatwoot

O AstroBot dispara um template aprovado para uma lista de leads, conduz a
qualificação com Gemini e transfere os interessados para atendentes humanos na
mesma conversa do Chatwoot.

## Arquitetura

```text
Lista de leads
    └─ POST /disparar
         └─ template aprovado pela Meta

Lead responde no WhatsApp
    └─ Meta → Chatwoot → Agent Bot webhook
                         └─ Gemini
                              └─ resposta pela API do Chatwoot

Interessado/pediu humano
    └─ nota privada + labels + atributos
         └─ status open + equipe/agente humano
```

O webhook da Meta deve continuar apontando **somente para o Chatwoot**. O
AstroBot recebe os eventos por `POST /webhook/chatwoot`, configurado como URL do
Agent Bot. Depois que o lead responde, todas as mensagens saem pelo Chatwoot;
isso evita respostas duplicadas e mantém o histórico em um único lugar.

## Setup local

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp ENV_TEMPLATE.txt .env
```

Preencha no `.env`:

- `GEMINI_API_KEY`
- `META_TOKEN`, `META_PHONE_NUMBER_ID`, `META_TEMPLATE_NAME`
- `CHATWOOT_URL`, `CHATWOOT_ACCOUNT_ID`, `CHATWOOT_INBOX_ID`
- `CHATWOOT_API_TOKEN`, obtido no perfil de um administrador do Chatwoot
- `CHATWOOT_WEBHOOK_SECRET`, exibido ao criar/editar o Agent Bot
- `CHATWOOT_TEAM_ID` ou `CHATWOOT_ASSIGNEE_ID` para o handoff

Nunca reutilize ou publique tokens que apareceram em capturas de tela.

## Configuração no Chatwoot

1. Crie as labels `ia-atendendo`, `interessado`, `atendimento-humano` e
   `sem-interesse`.
2. Crie os atributos de conversa opcionais `nome_lead`, `regiao`,
   `capital_disponivel`, `prazo`, `classificacao` e `score`.
3. Em **Configurações → Bots**, crie `AstroBot` com a URL pública:
   `https://seu-dominio/webhook/chatwoot`.
4. Copie o segredo do webhook para `CHATWOOT_WEBHOOK_SECRET`.
5. Na caixa do WhatsApp, selecione o AstroBot em **Configuração do bot**.

Conversas em `pending` são atendidas pela IA. No handoff, o AstroBot muda a
conversa para `open`; a partir daí ele ignora novas mensagens e o humano assume.

## Disparo inicial

O endpoint aceita apenas o template configurado, nunca texto livre fora da
janela de 24 horas:

```bash
curl -X POST http://localhost:5000/disparar \
  -H 'Content-Type: application/json' \
  -d '{"telefones":["5511999999999"]}'
```

Para templates com variáveis:

```json
{
  "telefones": ["5511999999999"],
  "parametros": {"5511999999999": ["Bruno"]}
}
```

Use somente contatos que tenham autorizado mensagens da empresa.
Por segurança, leads que já estejam em conversa, transferidos ou marcados como
sem interesse são ignorados. O campo `"forcar": true` existe para testes e
reprocessamentos deliberados; não o use em campanhas comuns.

## Execução

Desenvolvimento:

```bash
python3 main.py
```

Produção:

```bash
gunicorn --workers 2 --threads 4 --bind 127.0.0.1:5000 main:app
```

Saúde: `GET /saude`  
Leads: `GET /leads` ou `GET /leads?status=transferido`

## Estrutura relevante

- `main.py`: webhook do Agent Bot, disparo e endpoints de consulta
- `core/conversation.py`: motor da qualificação
- `prompts/qualificacao.py`: roteiro e prompt do Gemini
- `integrations/chatwoot.py`: mensagens, labels, atributos e handoff
- `integrations/whatsapp_meta.py`: somente o template inicial
- `storage/leads.py`: persistência atual em JSON
- `storage/events.py`: deduplicação de webhooks

Para volume maior, substitua os dois arquivos JSON por PostgreSQL e use uma fila
durável para os jobs do Gemini.

---

# Contatos vindos de uma planilha do Google

A lista de leads mora numa planilha do Google. O bot lê os contatos de lá,
dispara o template inicial e escreve o status de volta na própria planilha —
que vira o painel de acompanhamento da equipe.

```
Planilha do Google
        │  importar_planilha.py
        ▼
   leads.json  ──►  template da Meta  ──►  Lead
                                             │ responde
                                             ▼
                                          Chatwoot
                                             │
                                     webhook /webhook/chatwoot
                                             │
                                      conversa + qualificação
                                             │
                    ┌────────────────────────┴──────────┐
                    ▼                                   ▼
          handoff no Chatwoot              status de volta na planilha
                                        (respondeu / qualificado / sem interesse)
```

## Configurar o acesso (Service Account)

1. [console.cloud.google.com](https://console.cloud.google.com) → criar um projeto
2. **APIs e serviços → Biblioteca** → ativar **Google Sheets API**
3. **APIs e serviços → Credenciais** → Criar credenciais → **Conta de serviço**
4. Na conta criada: aba **Chaves** → Adicionar chave → **JSON** → baixar
5. Salvar o arquivo como `credenciais.json` na raiz do projeto
6. Abrir o JSON, copiar o valor de `client_email`
   (algo como `astrobot@projeto.iam.gserviceaccount.com`)
7. Na planilha: **Compartilhar** → colar esse e-mail → permissão **Editor**

No `.env`:

```
GOOGLE_CREDENCIAIS_JSON=credenciais.json
PLANILHA_ID=1AbC...          # o trecho entre /d/ e /edit na URL da planilha
PLANILHA_ABA=                # vazio = primeira aba
PLANILHA_ESCRITA=true
```

O `credenciais.json` está no `.gitignore` — ele é uma credencial, nunca vai
para o repositório.

## Preparar a planilha

Em vez de adivinhar o formato, deixe o bot escrever a estrutura:

```bash
python3 importar_planilha.py preparar
```

Ele grava o cabeçalho `nome | telefone | origem | status_bot | atualizado_em`
na primeira aba, em negrito e com a linha congelada. Depois é só colar os
contatos a partir da linha 2.

Se a aba já tiver conteúdo, ele **para e avisa** em vez de sobrescrever.
Nesse caso:

```bash
python3 importar_planilha.py preparar --aba Leads    # cria uma aba nova
python3 importar_planilha.py preparar --forcar       # troca só a linha 1
```

Criando aba nova, lembre de pôr `PLANILHA_ABA=Leads` no `.env` — o próprio
comando avisa.

Nada disso é obrigatório: se a planilha já existe com outro cabeçalho, o bot
detecta as colunas sozinho (ver abaixo). O `preparar` serve para começar do
zero sem erro.

## Usar

```bash
python3 importar_planilha.py preparar            # cria as colunas do bot
python3 importar_planilha.py inspecionar         # mostra a planilha crua
python3 importar_planilha.py ler                 # só mostra, não grava nada
python3 importar_planilha.py importar            # grava no leads.json
python3 importar_planilha.py disparar --limite 3 # envia o template
```

Opções: `--limite N` (só os N primeiros), `--todos` (inclui quem já tem
status), `--forcar` (reaborda quem já está em conversa).

Comece sempre pelo `ler`. Ele mostra quais colunas foram detectadas, quais
contatos entraram e quais linhas foram ignoradas e por quê — sem tocar em
nada.

## Colunas da planilha

Detectadas sozinhas pelo cabeçalho:

| Papel | Nomes aceitos |
|---|---|
| telefone | telefone, celular, whatsapp, fone, numero, contato, phone, tel |
| nome | nome, name, lead, cliente, responsavel |
| status | status_bot, status, situacao |

Funciona também com variações (`WhatsApp do contato`, `Telefone do lead`).
Se o cabeçalho for muito diferente, force pelo `.env`:
`PLANILHA_COLUNA_TELEFONE=`, `PLANILHA_COLUNA_NOME=`, `PLANILHA_COLUNA_STATUS=`.

O cabeçalho não precisa estar na linha 1 — o bot procura nas 10 primeiras
linhas, pulando título e linhas em branco, e continua reportando o número
real da linha na planilha.

A coluna de status não precisa existir — o bot cria `status_bot` e
`atualizado_em` no fim da planilha na primeira vez que escreve.

Telefones são normalizados para o formato internacional (`5519999990001`).
Aceita `(19) 99999-0001`, `+55 19 99999-0001`, `19999990001`. Duplicados,
linhas sem DDD e células sem número são separados e listados na tela, nunca
descartados em silêncio.

## Disparo automático

O Google Sheets não avisa quando alguém adiciona uma linha — não existe
webhook de "contato novo". Então o bot vai lá conferir de tempos em tempos.

Em produção quem faz isso é o serviço `astrobot-sync` do `docker-compose`
(container separado de propósito: o `astrobot` roda com 2 workers do
gunicorn, e um agendador dentro do app dispararia em dobro).

```bash
docker compose up -d              # sobe o bot e a varredura
docker compose logs -f astrobot-sync
```

Para testar na mão:

```bash
python3 sincronizar.py --uma-vez           # uma varredura e sai
python3 sincronizar.py --uma-vez --agora   # ignora a janela de horário
```

### Como o disparo sai

A varredura **não grava no `leads.json`** — ela chama a rota `/disparar`
do próprio bot:

```
astrobot-sync                         astrobot
  lê a planilha
  monta a fila      ── POST /disparar ──►  grava no leads.json
                                           envia o template pela Meta
  marca o status    ◄── resultado ──────
  de volta na planilha
```

O motivo é chato mas importante: o `leads.json` é protegido por um lock de
thread, que só vale **dentro de um processo**. São dois containers. Se os
dois gravassem no mesmo arquivo, um sobrescreveria o escrito pelo outro —
lead perdido, ou JSON corrompido. Passando pela rota, só o processo do
servidor escreve.

Por isso o `astrobot-sync` no compose **não monta `./data`**. É de
propósito.

Com `ASTROBOT_URL` vazio ele chama a função no mesmo processo — modo local,
para rodar o comando na mão com o servidor desligado.

O corpo aceito pela rota:

```json
{
  "telefones": ["5519998652758"],
  "nomes":     {"5519998652758": "Bruno"},
  "linhas":    {"5519998652758": 3},
  "parametros":{"5519998652758": ["Bruno"]},
  "pausa": 3
}
```

`linhas` é a linha de origem na planilha — é ela que permite ao bot
escrever o status de volta quando o lead responder no Chatwoot.

### Travas

| Variável | Padrão | O que faz |
|---|---|---|
| `DISPARO_AUTOMATICO` | `false` | interruptor geral — nada sai enquanto for false |
| `DISPARO_INTERVALO_MIN` | `120` | de quanto em quanto tempo varre a planilha |
| `DISPARO_MAX_POR_RODADA` | `20` | teto de mensagens por varredura |
| `DISPARO_PAUSA_SEGUNDOS` | `3` | respiro entre uma mensagem e outra |
| `DISPARO_DIAS` | `0,1,2,3,4` | 0=segunda … 6=domingo |
| `DISPARO_HORA_INICIO` / `_FIM` | `9` / `18` | janela em que pode abordar |
| `DISPARO_TIMEZONE` | `America/Sao_Paulo` | fuso da janela e dos carimbos na planilha |

Contato colado fora da janela não é perdido: fica na fila e sai na próxima
abertura. O log diz quando será.

Fora da janela o bot **nem chega a ler a planilha** — economiza chamada e
deixa claro no log por que não disparou.

### Por que não duplica

Duas camadas independentes:

1. a coluna `status_bot` na planilha tira da fila quem já foi abordado
2. o `leads.json` recusa quem não está em `novo` / `sem_resposta`

Se a escrita na planilha falhar (rede caiu no meio), a segunda camada
segura. Rodar a varredura duas vezes seguidas não manda nada duas vezes.

## Status escritos de volta

| Status | Quando |
|---|---|
| `disparado` | o template saiu para o lead |
| `respondeu` | o lead respondeu a primeira vez |
| `qualificado` | terminou a qualificação e foi para um humano |
| `sem interesse` | disse que não quer mais |
| `erro` | falhou o envio (o motivo aparece no terminal) |

Quem já tem um desses status não é abordado de novo — é isso que impede
disparo duplicado quando alguém roda o comando duas vezes.

Para desligar a escrita: `PLANILHA_ESCRITA=false`.

## Testes

```bash
python3 -m unittest discover -s tests
```

A leitura da planilha é testada sem internet — `interpretar_planilha()`
recebe as linhas cruas, então dá para testar cabeçalho torto, duplicado,
telefone inválido e linha em branco sem tocar no Google.
