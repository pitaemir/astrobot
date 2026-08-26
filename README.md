# Bot de Qualificação de Leads — Astrobox

Bot de WhatsApp que conversa com leads interessados em abrir uma franquia
Astrobox, confirma o interesse, coleta as informações de qualificação e
entrega o lead pronto para um atendente humano.

---

## Como funciona

```
Lista de leads
      │
      ▼
POST /disparar ──► WhatsApp (Meta API) ──► Lead
                                             │
                                             ▼ responde
                            POST /webhook ◄──┘
                                  │
                                  ▼
                         core/conversation.py
                                  │
                    ┌─────────────┼─────────────┐
                    ▼             ▼             ▼
              Gemini (IA)     Chatwoot      leads.json
              conduz as       espelha a     guarda tudo
              perguntas       conversa
                    │
                    ▼ terminou de responder
              core/scoring.py  (pontuação — a definir)
                    │
                    ▼
        WhatsApp do atendente humano
        (nome + número + resumo das respostas)
```

---

## Setup

```bash
cd astrobox

python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt

cp ENV_TEMPLATE.txt .env      # depois edite o .env
```

### Testar sem WhatsApp

```bash
python3 simulate.py
```

Você faz o papel do lead no terminal. O bot responde de verdade (Gemini),
e no final imprime o resumo que iria para o atendente.

### Rodar o servidor

```bash
python3 main.py
```

Checar o que está ligado: `curl localhost:5000/saude`

---

## O que já está pronto e o que falta

| Peça | Status |
|---|---|
| Conversa com IA (Gemini) | ✅ funcionando |
| Extração das respostas do lead | ✅ funcionando |
| Armazenamento dos leads | ✅ funcionando (JSON) |
| Aviso ao atendente humano | ✅ funcionando |
| Envio/recebimento WhatsApp | ✅ código pronto, ⏳ falta credencial |
| Chatwoot | ✅ código pronto, ⏳ falta URL/token da VM |
| Pontuação e classificação | ⏳ **proposital** — aguardando critérios da Astrobox |
| Perguntas oficiais do setor | ⏳ aguardando a empresa |

Sem as credenciais o bot **não quebra**: WhatsApp entra em modo simulação
(imprime no terminal) e o Chatwoot fica desligado.

---

## Onde mexer depois

**Perguntas do roteiro** → `prompts/qualificacao.py`
É o único arquivo a editar quando a Astrobox mandar as perguntas oficiais.
Se surgirem campos novos, adicione também em `core/models.py` (classe `Lead`)
e na lista `CAMPOS_OBRIGATORIOS`.

**Pontuação** → `core/scoring.py`
As funções `calcular_score()` e `classificar()` estão com a estrutura
pronta e um `TODO`. Preencher não exige mudar mais nada no projeto.

**Credenciais Meta** → `.env` (`META_TOKEN`, `META_PHONE_NUMBER_ID`)
e cadastrar a URL `https://seu-dominio/webhook` no painel da Meta usando o
mesmo `META_VERIFY_TOKEN` do `.env`.

**Credenciais Chatwoot** → `.env` (`CHATWOOT_URL`, `CHATWOOT_ACCOUNT_ID`,
`CHATWOOT_INBOX_ID`, `CHATWOOT_API_TOKEN`).

---

## Estrutura

```
astrobox/
├── main.py                    servidor Flask (webhook + disparo)
├── simulate.py                testa a conversa no terminal
├── config.py                  lê o .env
│
├── prompts/
│   └── qualificacao.py        👈 o roteiro de perguntas
│
├── core/
│   ├── models.py              o que é um Lead
│   ├── conversation.py        motor da conversa
│   └── scoring.py             👈 pontuação (a definir)
│
├── integrations/
│   ├── gemini_client.py       IA
│   ├── whatsapp_meta.py       Meta Cloud API
│   ├── chatwoot.py            painel do time
│   └── notificacao.py         aviso ao atendente
│
└── storage/
    └── leads.py               persistência (JSON)
```

---

## Detalhe importante da Meta

Para iniciar conversa com quem nunca falou com o número, a Meta exige um
**template aprovado** (regra da janela de 24h). O `enviar_texto()` só
funciona dentro dessa janela.

Antes de disparar para a lista real, cadastre um template de abordagem no
Gerenciador da Meta e use `whatsapp_meta.enviar_template()` no `/disparar`.
# astrobot
