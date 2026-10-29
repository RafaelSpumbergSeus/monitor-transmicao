"""Testes do pipeline. Rodar: python -m unittest discover -s tests -t . -v

Os testes com fixtures pequenas verificam REGRAS (mediana, dedup, quarentena,
censura); o teste com dados sintéticos verifica o pipeline inteiro e que as
checagens de qualidade enxergam os defeitos injetados.
"""
import unittest

from src.ingestao import synthetic
from src.pipeline import db, quality
from src.pipeline.run import executar

CORTE = "2025-12-31"
CLASSE = {"codigo": 7, "nome": "Procedimento Comum Cível"}


def doc(numero, ajuiz="2024-01-10T00:00:00.000Z", movs=(), classe=CLASSE, atualiz=None):
    movimentos = [{"codigo": 1, "nome": n, "dataHora": d} for n, d in movs]
    ultima = atualiz or (movs[-1][1] if movs else ajuiz)
    return ("tjrs", {"numeroProcesso": numero, "classe": classe, "dataAjuizamento": ajuiz,
                     "dataHoraUltimaAtualizacao": ultima, "grau": "G1",
                     "orgaoJulgador": {"codigo": 1, "nome": "Vara"},
                     "assuntos": [{"codigo": 10, "nome": "Assunto"}], "movimentos": movimentos})


def com_julgamento_apos(numero, dias, base="2024-01-10"):
    from datetime import date, timedelta
    y, m, d = map(int, base.split("-"))
    alvo = (date(y, m, d) + timedelta(days=dias)).isoformat()
    return doc(numero, ajuiz=f"{base}T00:00:00.000Z",
               movs=[("Distribuição", f"{base}T08:00:00.000Z"), ("Julgamento", f"{alvo}T10:00:00.000Z")])


class Base(unittest.TestCase):
    def setUp(self):
        self.conn = db.conectar(":memory:")

    def tearDown(self):
        self.conn.close()

    def q(self, sql, *args):
        return self.conn.execute(sql, args).fetchall()


class TestNormTs(unittest.TestCase):
    def test_formatos_validos(self):
        self.assertEqual(db.norm_ts("20240315121500"), "2024-03-15 12:15:00")
        self.assertEqual(db.norm_ts("2024-03-15T12:15:00.000Z"), "2024-03-15 12:15:00")
        self.assertEqual(db.norm_ts("2024-03-15"), "2024-03-15 00:00:00")

    def test_invalidos_viram_none(self):
        for v in (None, "", "31/02/2024", "2024-02-31T00:00:00.000Z", "20241340000000", "abc"):
            self.assertIsNone(db.norm_ts(v), v)


class TestRegrasDeNegocio(Base):
    def test_mediana_e_p90_impar(self):
        docs = [com_julgamento_apos(f"P{i}", d) for i, d in enumerate([10, 20, 30, 40, 100])]
        executar(self.conn, docs, "teste", data_corte=CORTE)
        mediana, p90, n = self.q("SELECT mediana_dias, p90_dias, n_julgados FROM mart_tempo_primeiro_julgamento")[0]
        self.assertEqual((mediana, p90, n), (30, 100, 5))

    def test_mediana_par_e_p90(self):
        docs = [com_julgamento_apos(f"P{i}", d) for i, d in enumerate([10, 20, 30, 40])]
        executar(self.conn, docs, "teste", data_corte=CORTE)
        mediana, p90 = self.q("SELECT mediana_dias, p90_dias FROM mart_tempo_primeiro_julgamento")[0]
        self.assertEqual((mediana, p90), (25, 40))

    def test_censura_nao_entra_na_mediana_mas_entra_no_denominador(self):
        docs = [com_julgamento_apos(f"P{i}", d) for i, d in enumerate([10, 20, 30])]
        docs.append(doc("SEM_JULG", movs=[("Distribuição", "2024-01-10T08:00:00.000Z")]))
        executar(self.conn, docs, "teste", data_corte=CORTE)
        n, nj, pct, mediana = self.q(
            "SELECT n_processos, n_julgados, pct_julgados, mediana_dias FROM mart_tempo_primeiro_julgamento")[0]
        self.assertEqual((n, nj, pct, mediana), (4, 3, 0.75, 20))
        self.assertEqual(self.q("SELECT flag_sem_julgamento FROM fato_processo WHERE numero_processo='SEM_JULG'")[0][0], 1)

    def test_dedup_mantem_versao_mais_recente_independente_da_ordem(self):
        nova = doc("DUP", classe={"codigo": 1116, "nome": "Execução Fiscal"},
                   movs=[("Distribuição", "2024-01-10T08:00:00.000Z")], atualiz="2024-06-01T00:00:00.000Z")
        velha = doc("DUP", classe=CLASSE, movs=[("Distribuição", "2024-01-10T08:00:00.000Z")],
                    atualiz="2024-02-01T00:00:00.000Z")
        executar(self.conn, [nova, velha], "teste", data_corte=CORTE)  # velha chega DEPOIS
        self.assertEqual(self.q("SELECT classe_codigo FROM stg_processo WHERE numero_processo='DUP'"), [(1116,)])

    def test_gargalo_mede_tempo_parado_apos_cada_fase(self):
        d = doc("G1", movs=[("Distribuição", "2024-01-10T08:00:00.000Z"),
                            ("Conclusão", "2024-01-15T08:00:00.000Z"),
                            ("Despacho", "2024-01-22T08:00:00.000Z")])
        executar(self.conn, [d], "teste", data_corte=CORTE)
        got = dict(self.q("SELECT categoria_origem, mediana_dias_ate_proximo FROM mart_gargalo_fase"))
        self.assertEqual(got, {"distribuicao": 5, "conclusao": 7})

    def test_movimentacao_anterior_ao_ajuizamento_nao_distorce_tempos(self):
        d = doc("ANT", movs=[("Julgamento", "2023-12-01T08:00:00.000Z"),   # antes do ajuizamento (2024-01-10)
                             ("Distribuição", "2024-01-10T08:00:00.000Z")])
        executar(self.conn, [d], "teste", data_corte=CORTE, strict=False)
        self.assertEqual(self.q("SELECT flag_sem_julgamento, dias_ate_primeiro_julgamento FROM fato_processo"), [(1, None)])
        self.assertEqual(self.q("SELECT COUNT(*) FROM fato_movimentacao WHERE anterior_ao_ajuizamento=1")[0][0], 1)


class TestQualidade(Base):
    def test_processo_invalido_vai_para_quarentena_e_sai_dos_indicadores(self):
        bons = [com_julgamento_apos(f"P{i}", 10 + i) for i in range(60)]
        ruim = doc("RUIM", ajuiz="31/02/2024", movs=[("Distribuição", "2024-01-10T08:00:00.000Z")])
        sem_classe = doc("SEMCLASSE", classe={}, movs=[("Distribuição", "2024-01-10T08:00:00.000Z")])
        executar(self.conn, bons + [ruim, sem_classe], "teste", data_corte=CORTE)
        self.assertEqual(dict(self.q("SELECT numero_processo, motivo_quarentena FROM dq_quarentena")),
                         {"RUIM": "dt_ajuizamento_invalida", "SEMCLASSE": "classe_nula"})
        self.assertEqual(self.q("SELECT COUNT(*) FROM fato_processo")[0][0], 60)

    def test_pipeline_falha_quando_qualidade_estoura_limite(self):
        docs = [com_julgamento_apos(f"P{i}", 10) for i in range(5)]
        docs += [doc(f"R{i}", ajuiz="lixo", movs=[("Distribuição", "2024-01-10T08:00:00.000Z")]) for i in range(5)]
        with self.assertRaises(quality.DataQualityError) as ctx:
            executar(self.conn, docs, "teste", data_corte=CORTE)
        self.assertIn("data_ajuizamento_invalida", str(ctx.exception))

    def test_idempotencia_rodar_duas_vezes_nao_duplica(self):
        docs = synthetic.gerar(n=300, seed=7, corte=__import__("datetime").date(2025, 12, 31))
        executar(self.conn, docs, "sintetico", data_corte=CORTE)
        antes = {t: self.q(f"SELECT COUNT(*) FROM {t}")[0][0]
                 for t in ("raw_processo", "stg_processo", "fato_processo", "fato_movimentacao")}
        executar(self.conn, docs, "sintetico", data_corte=CORTE)
        depois = {t: self.q(f"SELECT COUNT(*) FROM {t}")[0][0] for t in antes}
        self.assertEqual(antes, depois)


class TestSinteticoFimAFim(Base):
    def test_conservacao_de_linhas_e_defeitos_detectados(self):
        docs = synthetic.gerar(n=1500, seed=42)
        res = executar(self.conn, docs, "sintetico")  # strict: defeitos injetados ficam dentro dos limites
        unicos = self.q("SELECT COUNT(DISTINCT tribunal_alias || numero_processo) FROM raw_processo")[0][0]
        stg = self.q("SELECT COUNT(*) FROM stg_processo")[0][0]
        fato = self.q("SELECT COUNT(*) FROM fato_processo")[0][0]
        quar = self.q("SELECT COUNT(*) FROM dq_quarentena")[0][0]
        self.assertEqual(unicos, stg)
        self.assertEqual(stg, fato + quar)
        self.assertGreater(quar, 0)
        por_nome = {r["nome"]: r for r in res}
        self.assertGreater(por_nome["data_ajuizamento_invalida"]["falhas"], 0)
        self.assertGreater(por_nome["classe_ausente"]["falhas"], 0)
        self.assertGreater(por_nome["movimentacao_antes_do_ajuizamento"]["falhas"], 0)
        self.assertEqual(por_nome["integridade_referencial_movimentacao"]["falhas"], 0)

    def test_sem_defeitos_nao_gera_quarentena(self):
        executar(self.conn, synthetic.gerar(n=500, seed=3, defeitos=False), "sintetico")
        self.assertEqual(self.q("SELECT COUNT(*) FROM dq_quarentena")[0][0], 0)

    def test_gerador_e_deterministico(self):
        self.assertEqual(synthetic.gerar(n=50, seed=1), synthetic.gerar(n=50, seed=1))


if __name__ == "__main__":
    unittest.main()
