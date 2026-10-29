"""Conexão SQLite + utilitários.

`norm_ts` normaliza os formatos de data/hora vistos no DataJud para
'YYYY-MM-DD HH:MM:SS'. Devolve NULL (e não explode) quando o valor é
inválido; quem decide o que fazer com NULL é a camada de qualidade.
Em PostgreSQL isto vira uma função SQL (ver README, seção "Portar para PostgreSQL").
"""
import re
import sqlite3
from datetime import datetime
from pathlib import Path

_RE_14 = re.compile(r"^\d{14}$")
_RE_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")
_RE_DATA = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def norm_ts(valor):
    if valor is None:
        return None
    s = str(valor).strip()
    try:
        if _RE_14.match(s):
            dt = datetime.strptime(s, "%Y%m%d%H%M%S")
        elif _RE_ISO.match(s):
            # O sufixo 'Z'/milissegundos é descartado: tratamos como horário civil.
            dt = datetime.strptime(s[:19], "%Y-%m-%dT%H:%M:%S")
        elif _RE_DATA.match(s):
            dt = datetime.strptime(s, "%Y-%m-%d")
        else:
            return None
    except ValueError:  # ex.: 2024-02-31
        return None
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def conectar(caminho) -> sqlite3.Connection:
    if str(caminho) != ":memory:":
        Path(caminho).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(caminho))
    conn.create_function("norm_ts", 1, norm_ts, deterministic=True)
    return conn


def executar_arquivo_sql(conn: sqlite3.Connection, caminho: Path) -> None:
    conn.executescript(Path(caminho).read_text(encoding="utf-8"))
    conn.commit()
