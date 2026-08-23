"""Database layer. Nothing here knows about agents or tools."""
import sqlite3
from pathlib import Path

ROOT = Path(__file__).parent
SCHEMA_DIR = ROOT / "schema"
DB_PATH = ROOT / "jenkov.db"

SCHEMA_FILES = ["jenkov_schema.sql", "strength_schema.sql"]
SEED_FILES = ["strength_seed.sql"]


def connect(path=None):
    con = sqlite3.connect(path or DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def connect_ro(path=None):
    """Read-only handle. This is what run_query gets. It cannot write, period."""
    p = path or DB_PATH
    con = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def init(path=None, seed=True):
    """Create schema and optionally load the seed catalog. Idempotent-ish:
    raises if tables already exist, so callers decide."""
    con = connect(path)
    for f in SCHEMA_FILES:
        con.executescript((SCHEMA_DIR / f).read_text())
    if seed:
        for f in SEED_FILES:
            con.executescript((SCHEMA_DIR / f).read_text())
    con.commit()
    return con


def schema_text():
    """The DDL, for putting in a system prompt so the model can write SQL."""
    return "\n\n".join((SCHEMA_DIR / f).read_text() for f in SCHEMA_FILES)


if __name__ == "__main__":
    if DB_PATH.exists():
        print(f"{DB_PATH} already exists — delete it first to re-init")
    else:
        con = init()
        n = con.execute("SELECT COUNT(*) FROM exercises").fetchone()[0]
        a = con.execute("SELECT COUNT(*) FROM exercise_aliases").fetchone()[0]
        print(f"initialized {DB_PATH}: {n} exercises, {a} aliases")
