"""Orquestração: landing -> raw -> staging -> marts -> qualidade -> export.

Uso:
  python -m src.pipeline.run --fonte sintetico --n 3000
  DATAJUD_API_KEY=... python -m src.pipeline.run --fonte datajud \
      --tribunais tjrs trt4 --classes 7 1116 985 --de 2023-01-01 --ate 2025-09-30
"""
import argparse
import logging
import sqlite3
from datetime import datetime, timezone
from typing import Iterable

from src.config import DB_PATH, DOCS_DIR, EXPORT_DIR, RAW_DIR, SQL_DIR
from src.ingestao import datajud_client, landing, synthetic
from src.pipeline import db, export, quality, report
from src.pipeline.load_raw import carregar_raw, carregar_seed_categorias

log = logging.getLogger("pipeline")


def executar(conn: sqlite3.Connection, docs: Iterable[tuple[str, dict]], fonte: str,
             data_corte: str | None = None, strict: bool = True, batch_id: str | None = None) -> list[dict]:
    batch_id = batch_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    db.executar_arquivo_sql(conn, SQL_DIR / "01_raw.sql")
    carregar_seed_categorias(conn)
    novos, repetidos = carregar_raw(conn, docs, batch_id)
    log.info("raw: %s novos, %s já existentes", novos, repetidos)

    db.executar_arquivo_sql(conn, SQL_DIR / "02_staging.sql")
    corte = data_corte or conn.execute("SELECT MAX(date(dt_movimento)) FROM stg_movimento").fetchone()[0]
    if corte is None:
        raise RuntimeError("Sem movimentações válidas: não há como definir a data de corte.")
    for k, v in (("fonte", fonte), ("data_corte", corte),
                 ("executado_em", datetime.now(timezone.utc).isoformat(timespec="seconds"))):
        conn.execute("INSERT OR REPLACE INTO pipeline_meta VALUES (?,?)", (k, v))
    conn.commit()

    db.executar_arquivo_sql(conn, SQL_DIR / "03_marts.sql")
    resultados = quality.executar_checks(conn)
    if strict:
        quality.exigir(resultados)
    return resultados


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fonte", choices=["sintetico", "datajud"], default="sintetico")
    ap.add_argument("--n", type=int, default=3000, help="(sintetico) nº de processos")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--sem-defeitos", action="store_true", help="(sintetico) não injeta defeitos")
    ap.add_argument("--tribunais", nargs="+", default=["tjrs", "trt4"])
    ap.add_argument("--classes", nargs="+", type=int, default=[7, 1116, 985])
    ap.add_argument("--de", default="2023-01-01")
    ap.add_argument("--ate", default="2025-09-30")
    ap.add_argument("--max-docs", type=int, default=None, help="(datajud) limite por tribunal, para testes")
    ap.add_argument("--db", default=str(DB_PATH))
    ap.add_argument("--reset", action="store_true", help="apaga o banco antes de rodar")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if args.reset and DB_PATH.exists():
        DB_PATH.unlink()

    if args.fonte == "sintetico":
        docs = synthetic.gerar(n=args.n, seed=args.seed, defeitos=not args.sem_defeitos)
    else:
        def _api():
            for alias in args.tribunais:
                for d in datajud_client.buscar(alias, args.classes, args.de, args.ate, max_docs=args.max_docs):
                    yield alias, d
        docs = _api()
    contagem = landing.escrever_jsonl(docs, RAW_DIR)
    log.info("landing: %s", contagem)

    conn = db.conectar(args.db)
    try:
        resultados = executar(conn, landing.ler_jsonl(RAW_DIR), fonte=args.fonte)
        for r in resultados:
            log.info("DQ %-40s %-6s %s/%s", r["nome"], r["status"], r["falhas"], r["total"])
        n = export.exportar_csv(conn, EXPORT_DIR)
        report.escrever_relatorio_qualidade(conn, DOCS_DIR / "relatorio_qualidade.md")
        report.gerar_figura(conn, DOCS_DIR / "img" / "tempo_por_coorte.png")
        log.info("exportado: %s", n)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
