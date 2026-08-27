import unittest
from datetime import datetime
from unittest.mock import patch

from core import sincronizacao


class JanelaDeHorarioTests(unittest.TestCase):
    """Padrão: seg-sex, 9h às 18h."""

    def setUp(self):
        self.patches = [
            patch.object(sincronizacao.config, "DISPARO_DIAS", "0,1,2,3,4"),
            patch.object(sincronizacao.config, "DISPARO_HORA_INICIO", 9),
            patch.object(sincronizacao.config, "DISPARO_HORA_FIM", 18),
        ]
        for p in self.patches:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in self.patches])

    def test_quarta_as_10h_pode(self):
        pode, _ = sincronizacao.dentro_da_janela(datetime(2026, 8, 26, 10, 0))
        self.assertTrue(pode)

    def test_quarta_as_8h_ainda_nao(self):
        pode, motivo = sincronizacao.dentro_da_janela(datetime(2026, 8, 26, 8, 59))
        self.assertFalse(pode)
        self.assertIn("abre", motivo)

    def test_quarta_as_18h_ja_fechou(self):
        """18h é o limite: às 18h em ponto já não dispara."""
        pode, motivo = sincronizacao.dentro_da_janela(datetime(2026, 8, 26, 18, 0))
        self.assertFalse(pode)
        self.assertIn("fechou", motivo)

    def test_ultimo_minuto_util_ainda_dispara(self):
        pode, _ = sincronizacao.dentro_da_janela(datetime(2026, 8, 26, 17, 59))
        self.assertTrue(pode)

    def test_sabado_nao(self):
        pode, motivo = sincronizacao.dentro_da_janela(datetime(2026, 8, 29, 10, 0))
        self.assertFalse(pode)
        self.assertIn("sábado", motivo)

    def test_domingo_nao(self):
        pode, _ = sincronizacao.dentro_da_janela(datetime(2026, 8, 30, 10, 0))
        self.assertFalse(pode)

    def test_madrugada_de_sabado_nao_escapa(self):
        pode, _ = sincronizacao.dentro_da_janela(datetime(2026, 8, 29, 3, 0))
        self.assertFalse(pode)


class ProximaAberturaTests(unittest.TestCase):
    def setUp(self):
        self.patches = [
            patch.object(sincronizacao.config, "DISPARO_DIAS", "0,1,2,3,4"),
            patch.object(sincronizacao.config, "DISPARO_HORA_INICIO", 9),
            patch.object(sincronizacao.config, "DISPARO_HORA_FIM", 18),
        ]
        for p in self.patches:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in self.patches])

    def test_sexta_a_noite_espera_ate_segunda(self):
        proxima = sincronizacao.proxima_abertura(datetime(2026, 8, 28, 20, 0))
        self.assertEqual(proxima, datetime(2026, 8, 31, 9, 0))
        self.assertEqual(proxima.weekday(), 0)

    def test_quarta_a_noite_espera_ate_quinta(self):
        proxima = sincronizacao.proxima_abertura(datetime(2026, 8, 26, 22, 0))
        self.assertEqual(proxima, datetime(2026, 8, 27, 9, 0))


class TravasDaRodadaTests(unittest.TestCase):
    def test_desligado_nao_dispara_nada(self):
        with patch.object(sincronizacao.config, "DISPARO_AUTOMATICO", False):
            resumo = sincronizacao.rodada(registrar=lambda m: None)
        self.assertEqual(resumo["pulou"], "DISPARO_AUTOMATICO=false")

    def test_sem_template_aprovado_nao_dispara(self):
        with patch.object(sincronizacao.config, "DISPARO_AUTOMATICO", True), \
             patch.object(sincronizacao.config, "META_TEMPLATE_NAME", ""):
            resumo = sincronizacao.rodada(registrar=lambda m: None)
        self.assertIn("META_TEMPLATE_NAME", resumo["pulou"])

    def test_fora_da_janela_nao_le_a_planilha(self):
        """Se está fora do horário, nem chega a chamar o Google."""
        with patch.object(sincronizacao.config, "DISPARO_AUTOMATICO", True), \
             patch.object(sincronizacao.config, "META_TEMPLATE_NAME", "abertura"), \
             patch.object(sincronizacao.planilha, "ativo", return_value=True), \
             patch.object(sincronizacao.planilha, "ler_contatos") as leitura, \
             patch.object(sincronizacao, "dentro_da_janela",
                          return_value=(False, "fora do horário")):
            resumo = sincronizacao.rodada(registrar=lambda m: None)
        leitura.assert_not_called()
        self.assertEqual(resumo["pulou"], "fora do horário")

    def test_respeita_o_teto_por_rodada(self):
        contatos = [
            {"linha": i, "telefone": f"5519999{i:06d}", "nome": f"L{i}",
             "status": "", "bruto": "", "aviso": None}
            for i in range(2, 32)
        ]
        with patch.object(sincronizacao.config, "DISPARO_AUTOMATICO", True), \
             patch.object(sincronizacao.config, "META_TEMPLATE_NAME", "abertura"), \
             patch.object(sincronizacao.config, "DISPARO_MAX_POR_RODADA", 5), \
             patch.object(sincronizacao.planilha, "ativo", return_value=True), \
             patch.object(sincronizacao.planilha, "ler_contatos",
                          return_value=(contatos, [], {"status": None})), \
             patch.object(sincronizacao, "dentro_da_janela",
                          return_value=(True, "ok")), \
             patch.object(sincronizacao, "disparar_da_planilha") as envio:
            envio.return_value = {"disparados": [], "ignorados": [], "erros": []}
            resumo = sincronizacao.rodada(registrar=lambda m: None)

        enviados = envio.call_args[0][0]
        self.assertEqual(len(enviados), 5)
        self.assertEqual(resumo["na_fila"], 30)


class ComoODisparoSaiTests(unittest.TestCase):
    """O leads.json só pode ser escrito por um processo (o servidor).

    Com ASTROBOT_URL definido, a varredura precisa passar pela rota HTTP
    em vez de gravar no arquivo direto — senão dois containers escrevem
    no mesmo JSON e um atropela o outro.
    """

    CONTATOS = [
        {"linha": 2, "telefone": "5519999990001", "nome": "Ana",
         "status": "", "bruto": "", "aviso": None},
    ]

    def test_com_url_definida_vai_por_http(self):
        with patch.object(sincronizacao.config, "ASTROBOT_URL", "http://astrobot:5000"), \
             patch.object(sincronizacao.config, "PLANILHA_ESCRITA", False), \
             patch.object(sincronizacao.requests, "post") as post:
            post.return_value.status_code = 200
            post.return_value.json.return_value = {
                "disparados": ["5519999990001"], "ignorados": [], "erros": []}
            sincronizacao.disparar_da_planilha(self.CONTATOS, {})

        url, corpo = post.call_args[0][0], post.call_args[1]["json"]
        self.assertEqual(url, "http://astrobot:5000/disparar")
        self.assertEqual(corpo["telefones"], ["5519999990001"])
        self.assertEqual(corpo["linhas"], {"5519999990001": 2})
        self.assertEqual(corpo["nomes"], {"5519999990001": "Ana"})

    def test_sem_url_chama_no_mesmo_processo(self):
        with patch.object(sincronizacao.config, "ASTROBOT_URL", ""), \
             patch.object(sincronizacao.config, "PLANILHA_ESCRITA", False), \
             patch("core.disparo.disparar_lote") as lote, \
             patch.object(sincronizacao.requests, "post") as post:
            lote.return_value = {"disparados": [], "ignorados": [], "erros": []}
            sincronizacao.disparar_da_planilha(self.CONTATOS, {})

        post.assert_not_called()
        lote.assert_called_once()

    def test_erro_http_vira_excecao_clara(self):
        with patch.object(sincronizacao.config, "ASTROBOT_URL", "http://astrobot:5000"), \
             patch.object(sincronizacao.requests, "post") as post:
            post.return_value.status_code = 503
            post.return_value.text = "META_TEMPLATE_NAME não configurado"
            with self.assertRaises(RuntimeError) as ctx:
                sincronizacao.disparar_da_planilha(self.CONTATOS, {})
        self.assertIn("503", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
