import hashlib
import hmac
import json
import time
import unittest
from unittest.mock import Mock, patch

import main


class AgentBotWebhookTests(unittest.TestCase):
    def payload(self, message_type="incoming", status="pending"):
        return {
            "event": "message_created",
            "id": 987,
            "content": "Tenho interesse",
            "message_type": message_type,
            "private": False,
            "sender": {"phone_number": "+55 (19) 99999-0000"},
            "conversation": {"id": 42, "inbox_id": 7, "status": status},
        }

    def test_extrai_apenas_mensagem_incoming_pendente(self):
        with patch.object(main.config, "CHATWOOT_INBOX_ID", "7"):
            evento = main._extrair_evento_chatwoot(self.payload())
        self.assertEqual(evento["telefone"], "5519999990000")
        self.assertEqual(evento["conversation_id"], 42)
        self.assertEqual(evento["event_id"], "987")

    def test_ignora_mensagem_do_proprio_bot(self):
        self.assertIsNone(main._extrair_evento_chatwoot(self.payload("outgoing")))

    def test_ignora_conversa_que_ja_foi_entregue_ao_humano(self):
        with patch.object(main.config, "CHATWOOT_BOT_ONLY_PENDING", True):
            self.assertIsNone(main._extrair_evento_chatwoot(self.payload(status="open")))

    def test_valida_assinatura_hmac(self):
        corpo = json.dumps(self.payload()).encode()
        timestamp = str(int(time.time()))
        segredo = "segredo-de-teste"
        assinatura = "sha256=" + hmac.new(
            segredo.encode(), timestamp.encode() + b"." + corpo, hashlib.sha256
        ).hexdigest()
        with patch.object(main.config, "CHATWOOT_WEBHOOK_SECRET", segredo):
            self.assertTrue(main._assinatura_valida(corpo, {
                "X-Chatwoot-Signature": assinatura,
                "X-Chatwoot-Timestamp": timestamp,
            }))

    @patch.object(main.whatsapp_meta, "enviar_template")
    @patch.object(main.conversation, "iniciar")
    @patch.object(main.repo, "buscar_ou_criar")
    @patch.object(main.repo, "importar")
    def test_disparo_usa_template_e_nao_texto_livre(
        self, importar, buscar, iniciar, enviar
    ):
        buscar.return_value = Mock(status=main.models.NOVO)
        iniciar.return_value = (Mock(), "texto que não deve ser enviado diretamente")
        with (
            patch.object(main.config, "META_TEMPLATE_NAME", "confirmar_interesse"),
            patch.object(main.config, "META_TEMPLATE_LANGUAGE", "pt_BR"),
        ):
            resposta = main.app.test_client().post(
                "/disparar", json={"telefones": ["+55 (19) 99999-0000"]}
            )
        self.assertEqual(resposta.status_code, 200)
        enviar.assert_called_once_with(
            "5519999990000", "confirmar_interesse", "pt_BR", None
        )

    @patch.object(main.whatsapp_meta, "enviar_template")
    @patch.object(main.repo, "buscar_ou_criar")
    @patch.object(main.repo, "importar")
    def test_nao_reaborda_lead_sem_interesse(self, importar, buscar, enviar):
        buscar.return_value = Mock(status=main.models.SEM_INTERESSE)
        with patch.object(main.config, "META_TEMPLATE_NAME", "confirmar_interesse"):
            resposta = main.app.test_client().post(
                "/disparar", json={"telefones": ["5519999990000"]}
            )
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.get_json()["ignorados"][0]["status"], "sem_interesse")
        enviar.assert_not_called()


if __name__ == "__main__":
    unittest.main()
