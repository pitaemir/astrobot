import unittest

from integrations import google_sheets as planilha


class NormalizarTelefoneTests(unittest.TestCase):
    def test_formatos_validos_viram_o_mesmo_numero(self):
        for bruto in [
            "5519999990000",
            "+55 19 99999-0000",
            "(19) 99999-0000",
            "19999990000",
            "19 9 9999 0000",
        ]:
            telefone, _ = planilha.normalizar_telefone(bruto)
            self.assertEqual(telefone, "5519999990000", f"falhou em {bruto!r}")

    def test_fixo_com_dez_digitos_passa_com_aviso(self):
        telefone, aviso = planilha.normalizar_telefone("(19) 3333-4444")
        self.assertEqual(telefone, "551933334444")
        self.assertIsNotNone(aviso)

    def test_sem_ddd_e_recusado(self):
        telefone, aviso = planilha.normalizar_telefone("99999-0000")
        self.assertIsNone(telefone)
        self.assertEqual(aviso, "sem DDD")

    def test_vazio_e_lixo_sao_recusados(self):
        self.assertEqual(planilha.normalizar_telefone(""), (None, "vazio"))
        self.assertEqual(
            planilha.normalizar_telefone("a combinar"), (None, "sem dígitos")
        )
        self.assertIsNone(planilha.normalizar_telefone("a definir")[0])
        self.assertIsNone(planilha.normalizar_telefone("123")[0])


class InterpretarPlanilhaTests(unittest.TestCase):
    def linhas(self):
        return [
            ["Nome", "Telefone", "Origem", "status_bot"],
            ["Ana Souza", "(19) 99999-0001", "instagram", ""],
            ["Bruno Lima", "5511988880002", "site", "disparado"],
            ["", "", "", ""],
            ["Carla", "sem numero", "feira", ""],
            ["Ana de novo", "19 99999-0001", "indicação", ""],
            ["Diego", "+55 21 97777-0003", "site", ""],
        ]

    def test_detecta_colunas_sozinha(self):
        _, _, mapa = planilha.interpretar_planilha(self.linhas())
        self.assertEqual(mapa["telefone"], 1)
        self.assertEqual(mapa["nome"], 0)
        self.assertEqual(mapa["status"], 3)

    def test_le_contatos_validos_com_a_linha_certa(self):
        contatos, _, _ = planilha.interpretar_planilha(self.linhas())
        self.assertEqual(
            [(c["linha"], c["telefone"], c["nome"]) for c in contatos],
            [
                (2, "5519999990001", "Ana Souza"),
                (3, "5511988880002", "Bruno Lima"),
                (7, "5521977770003", "Diego"),
            ],
        )

    def test_separa_duplicado_e_invalido(self):
        _, problemas, _ = planilha.interpretar_planilha(self.linhas())
        motivos = {p["linha"]: p["motivo"] for p in problemas}
        self.assertEqual(motivos[5], "sem dígitos")
        self.assertEqual(motivos[6], "duplicado")
        self.assertNotIn(4, motivos)  # linha em branco é só ignorada

    def test_pendentes_pula_quem_ja_foi_trabalhado(self):
        contatos, _, _ = planilha.interpretar_planilha(self.linhas())
        pendentes = planilha.pendentes(contatos)
        self.assertEqual([c["nome"] for c in pendentes], ["Ana Souza", "Diego"])

    def test_cabecalho_diferente_ainda_e_reconhecido(self):
        linhas = [
            ["Lead", "WhatsApp do contato", "Situação"],
            ["Elis", "11 96666-0004", ""],
        ]
        contatos, _, mapa = planilha.interpretar_planilha(linhas)
        self.assertEqual(mapa["telefone"], 1)
        self.assertEqual(contatos[0]["telefone"], "5511966660004")

    def test_sem_coluna_de_telefone_explica_o_erro(self):
        with self.assertRaises(ValueError) as contexto:
            planilha.interpretar_planilha([["Nome", "Cidade"], ["Ana", "SP"]])
        self.assertIn("PLANILHA_COLUNA_TELEFONE", str(contexto.exception))

    def test_coluna_de_status_ainda_inexistente_nao_e_erro(self):
        """O nome no .env também serve para criar a coluna depois."""
        contatos, _, mapa = planilha.interpretar_planilha(
            [["Nome", "Telefone"], ["Ana", "19999990001"]],
            coluna_status="status_bot",
        )
        self.assertIsNone(mapa["status"])
        self.assertEqual(len(contatos), 1)

    def test_coluna_forcada_inexistente_lista_as_reais(self):
        with self.assertRaises(ValueError) as contexto:
            planilha.interpretar_planilha(
                [["Nome", "Fone"], ["Ana", "19999990000"]],
                coluna_telefone="celular_do_lead",
            )
        self.assertIn("Fone", str(contexto.exception))


class CelulaA1Tests(unittest.TestCase):
    def test_converte_indice_para_notacao_a1(self):
        self.assertEqual(planilha._celula_a1(2, 0), "A2")
        self.assertEqual(planilha._celula_a1(10, 7), "H10")
        self.assertEqual(planilha._celula_a1(1, 25), "Z1")
        self.assertEqual(planilha._celula_a1(3, 26), "AA3")


if __name__ == "__main__":
    unittest.main()
