"""Checagens de qualidade de dados.

Cada regra mede `falhas / total`. Se passar do limite:
  - severidade 'error'  -> o pipeline FALHA e nada é exportado;
  - severidade 'warn'   -> vira alerta no relatório, o pipeline segue.
Resultados ficam em dq_resultado (histórico por execução).
"""
import sqlite3
from datetime import datetime, timezone

CORTE = "(SELECT valor FROM pipeline_meta WHERE chave = 'data_corte')"

CHECKS = [
    dict(nome="chave_duplicada_staging", severidade="error", limite_pct=0.0,
         descricao="Mais de uma linha por (tribunal, numero_processo) em stg_processo.",
         falhas="SELECT COUNT(*) FROM (SELECT 1 FROM stg_processo GROUP BY tribunal, numero_processo HAVING COUNT(*) > 1)",
         total="SELECT COUNT(*) FROM stg_processo"),
    dict(nome="data_ajuizamento_invalida", severidade="error", limite_pct=0.02,
         descricao="dataAjuizamento ausente ou em formato/valor inválido (vai para quarentena).",
         falhas="SELECT COUNT(*) FROM stg_processo WHERE dt_ajuizamento IS NULL",
         total="SELECT COUNT(*) FROM stg_processo"),
    dict(nome="classe_ausente", severidade="error", limite_pct=0.05,
         descricao="Processo sem classe processual (vai para quarentena).",
         falhas="SELECT COUNT(*) FROM stg_processo WHERE classe_codigo IS NULL",
         total="SELECT COUNT(*) FROM stg_processo"),
    dict(nome="ajuizamento_no_futuro", severidade="error", limite_pct=0.0,
         descricao="Data de ajuizamento posterior à data de corte.",
         falhas=f"SELECT COUNT(*) FROM stg_processo WHERE date(dt_ajuizamento) > {CORTE}",
         total="SELECT COUNT(*) FROM stg_processo"),
    dict(nome="quarentena_excessiva", severidade="error", limite_pct=0.10,
         descricao="Proporção de processos em quarentena acima do tolerável: a fonte provavelmente mudou.",
         falhas="SELECT COUNT(*) FROM dq_quarentena",
         total="SELECT COUNT(*) FROM stg_processo"),
    dict(nome="integridade_referencial_movimentacao", severidade="error", limite_pct=0.0,
         descricao="Movimentação sem processo correspondente em fato_processo.",
         falhas="SELECT COUNT(*) FROM fato_movimentacao m LEFT JOIN fato_processo p ON p.processo_key = m.processo_key WHERE p.processo_key IS NULL",
         total="SELECT COUNT(*) FROM fato_movimentacao"),
    dict(nome="movimentacao_antes_do_ajuizamento", severidade="warn", limite_pct=0.005,
         descricao="Processos com movimentação datada antes do ajuizamento (mantidas, mas excluídas dos tempos).",
         falhas="SELECT COUNT(DISTINCT processo_key) FROM fato_movimentacao WHERE anterior_ao_ajuizamento = 1",
         total="SELECT COUNT(*) FROM fato_processo"),
    dict(nome="processo_sem_movimentacao", severidade="warn", limite_pct=0.01,
         descricao="Processos sem nenhuma movimentação válida.",
         falhas="SELECT COUNT(*) FROM fato_processo WHERE qtd_movimentacoes = 0",
         total="SELECT COUNT(*) FROM fato_processo"),
    dict(nome="movimentacao_com_data_invalida", severidade="warn", limite_pct=0.01,
         descricao="Movimentações cuja data não pôde ser interpretada.",
         falhas="SELECT COUNT(*) FROM stg_movimento WHERE dt_movimento IS NULL",
         total="SELECT COUNT(*) FROM stg_movimento"),
]


class DataQualityError(RuntimeError):
    pass


def executar_checks(conn: sqlite3.Connection) -> list[dict]:
    conn.execute("""CREATE TABLE IF NOT EXISTS dq_resultado (
        executado_em TEXT, nome TEXT, severidade TEXT, descricao TEXT,
        falhas INTEGER, total INTEGER, pct REAL, limite_pct REAL, status TEXT)""")
    agora = datetime.now(timezone.utc).isoformat(timespec="seconds")
    resultados = []
    for c in CHECKS:
        falhas = conn.execute(c["falhas"]).fetchone()[0]
        total = conn.execute(c["total"]).fetchone()[0]
        pct = (falhas / total) if total else 0.0
        if pct > c["limite_pct"]:
            status = "falha" if c["severidade"] == "error" else "alerta"
        else:
            status = "ok"
        r = dict(executado_em=agora, nome=c["nome"], severidade=c["severidade"],
                 descricao=c["descricao"], falhas=falhas, total=total,
                 pct=round(pct, 6), limite_pct=c["limite_pct"], status=status)
        resultados.append(r)
        conn.execute("INSERT INTO dq_resultado VALUES (:executado_em,:nome,:severidade,:descricao,:falhas,:total,:pct,:limite_pct,:status)", r)
    conn.commit()
    return resultados


def exigir(resultados: list[dict]) -> None:
    falhas = [r for r in resultados if r["status"] == "falha"]
    if falhas:
        det = "; ".join(f'{r["nome"]}: {r["falhas"]}/{r["total"]} ({r["pct"]:.2%} > {r["limite_pct"]:.2%})' for r in falhas)
        raise DataQualityError(f"Qualidade de dados reprovada. {det}")
