from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SQL_DIR = ROOT / "sql"
SEEDS_DIR = ROOT / "seeds"
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
EXPORT_DIR = DATA_DIR / "exports"
DOCS_DIR = ROOT / "docs"
DB_PATH = DATA_DIR / "warehouse.db"
