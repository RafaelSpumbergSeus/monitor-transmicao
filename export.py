import csv
import sqlite3
from pathlib import Path

TABELAS = ["dim_tribunal", "dim_classe", "dim_orgao_julgador", "dim_assunto",
           "dim_categoria_movimento", "dim_calendario", "fato_processo", "fato_movimentacao",
           "mart_tempo_primeiro_julgamento", "mart_gargalo_fase", "mart_carga_mensal",
           "mart_acervo_pendente", "dq_quarentena", "dq_resultado"]


def exportar_csv(conn: sqlite3.Connection, pasta: Path) -> dict[str, int]:
    pasta.mkdir(parents=True, exist_ok=True)
    contagem = {}
    for t in TABELAS:
        cur = conn.execute(f"SELECT * FROM {t}")
        cols = [d[0] for d in cur.description]
        with (pasta / f"{t}.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(cols)
            n = 0
            for linha in cur:
                w.writerow(linha)
                n += 1
        contagem[t] = n
    return contagem
