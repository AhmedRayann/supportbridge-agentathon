"""Explicit, transactional, versioned migration command; never runs on startup."""

import hashlib
from pathlib import Path

from .database import Database, Settings, StorageError


def migrate(database: Database) -> None:
    with database.transaction(migration=True) as connection:
        connection.execute("""SELECT pg_advisory_xact_lock(78249506)""")
        connection.execute(
            """CREATE TABLE IF NOT EXISTS sb_schema_migrations (version text PRIMARY
            KEY, checksum text NOT NULL, applied_at timestamptz NOT NULL DEFAULT
            clock_timestamp())"""
        )
        for path in sorted((Path(__file__).parent / "migrations").glob("*.sql")):
            source = path.read_bytes().replace(b"\r\n", b"\n")
            checksum = hashlib.sha256(source).hexdigest()
            existing = connection.execute(
                """SELECT checksum FROM sb_schema_migrations WHERE version=%s""",
                (path.stem,),
            ).fetchone()
            if existing:
                if existing["checksum"] != checksum:
                    raise StorageError("Applied migration checksum changed")
                continue
            connection.execute(source.decode(), prepare=False)
            connection.execute(
                """INSERT INTO sb_schema_migrations(version, checksum) VALUES (%s,
                %s)""",
                (path.stem, checksum),
            )


if __name__ == "__main__":
    try:
        migrate(Database(Settings.from_env()))
    except StorageError as error:
        raise SystemExit(str(error)) from None
    print("Investigation migrations applied")
