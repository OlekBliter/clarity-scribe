import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from .exceptions import DatabaseError, RepositoryError


_REQUIRED_TABLES = frozenset(
    {
        "patients",
        "sessions",
        "transcript_segments",
        "biomarkers",
        "medical_cards",
        "soap_notes",
    }
)


class Database:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path).resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        return conn

    def init_schema(self) -> None:
        conn = self.connect()
        try:
            existing_tables = {
                row["name"]
                for row in conn.execute(
                    """
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'table' AND name IN (?, ?, ?, ?, ?, ?)
                    """,
                    tuple(_REQUIRED_TABLES),
                ).fetchall()
            }
            missing_tables = _REQUIRED_TABLES - existing_tables

            if not existing_tables:
                try:
                    schema_file = Path(__file__).resolve().with_name("schema.sql")
                    sql_content = schema_file.read_text(encoding="utf-8")
                    conn.executescript(sql_content)
                    conn.execute("PRAGMA user_version = 1;")
                    conn.commit()
                except OSError as error:
                    raise DatabaseError("Failed to read the database schema.") from error
                except sqlite3.Error as error:
                    raise DatabaseError("Failed to initialize the database schema.") from error
            elif missing_tables:
                missing = ", ".join(sorted(missing_tables))
                raise DatabaseError(f"Database schema is incomplete. Missing tables: {missing}.")
        finally:
            conn.close()

    @contextmanager
    def read(self) -> Generator[sqlite3.Connection, None, None]:
        conn = self.connect()
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        conn = self.connect()
        committed = False
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
            committed = True
        except sqlite3.Error as e:
            raise RepositoryError(str(e)) from e
        finally:
            if not committed:
                try:
                    conn.rollback()
                except sqlite3.Error:
                    pass
            conn.close()
