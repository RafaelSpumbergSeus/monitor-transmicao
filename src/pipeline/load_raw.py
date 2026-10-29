import csv
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from typing import Iterable

from src.config import SEEDS_DIR


def carregar_seed_categorias(conn: sqlite3.Connection) -> int:
    with (SEEDS_DIR / "categoria_movimento.csv").open(encoding="utf-8") as f:
        linhas = [(r["padrao"], r["categoria"], int(r["prioridade"]), int(r["ordem_fase"]))
                  for r in csv.DictReader(f)]
    conn.execute("DELETE FROM ref_categoria_movimento")
    conn.executemany("INSERT INTO ref_categoria_movimento VALUES (?,?,?,?)", linhas)
    conn.commit()
    return len(linhas)


def carregar_raw(conn: sqlite3.Connection, docs: Iterable[tuple[str, dict]], batch_id: str) -> tuple[int, int]:
    """Insere documentos na camada raw de forma idempotente. Devolve (novos, ja_existentes)."""
    agora = datetime.now(timezone.utc).isoformat(timespec="seconds")
    antes = conn.execute("SELECT COUNT(*) FROM raw_processo").fetchone()[0]
    total = 0
    lote = []
    for alias, doc in docs:
        payload = json.dumps(doc, sort_keys=True, ensure_ascii=False)
        h = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        lote.append((alias, str(doc.get("numeroProcesso")), h, payload, batch_id, agora))
        total += 1
        if len(lote) >= 5000:
            conn.executemany("INSERT OR IGNORE INTO raw_processo VALUES (?,?,?,?,?,?)", lote)
            lote = []
    if lote:
        conn.executemany("INSERT OR IGNORE INTO raw_processo VALUES (?,?,?,?,?,?)", lote)
    conn.commit()
    depois = conn.execute("SELECT COUNT(*) FROM raw_processo").fetchone()[0]
    return depois - antes, total - (depois - antes)
