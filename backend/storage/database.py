"""Short PostgreSQL transactions; use the provider's transaction-pooler URL."""

import os
import re
from contextlib import contextmanager
from dataclasses import dataclass, field
from threading import BoundedSemaphore
from urllib.parse import parse_qs, urlsplit

import psycopg
from psycopg.rows import dict_row

# Connection resource cap only. All investigation state/quotas live in PostgreSQL.
_CONNECTION_SLOTS = BoundedSemaphore(4)


class StorageError(RuntimeError):
    pass


class StorageConfigurationError(StorageError):
    pass


class StorageUnavailable(StorageError):
    pass


class NotFound(StorageError):
    pass


class Conflict(StorageError):
    pass


class LimitReached(StorageError):
    pass


class ExecutionDisabled(StorageError):
    pass


class SessionDenied(StorageError):
    pass


@dataclass(frozen=True)
class Settings:
    database_url: str = field(repr=False)
    app_origin: str = "https://supportbridge-agentathon.vercel.app"
    session_ttl: int = 28800
    session_daily_limit: int = 2
    global_active_limit: int = 4
    global_daily_limit: int = 20
    experiment_limit: int = 8
    model_limit: int = 10
    lease_seconds: int = 60
    ai_enabled: bool = False

    @classmethod
    def from_env(cls):
        try:
            url = os.getenv("DATABASE_URL", "")
            parsed = urlsplit(url)
            if (
                parsed.scheme not in ("postgres", "postgresql")
                or not parsed.hostname
                or not parsed.path.strip("/")
            ):
                raise ValueError
            if parsed.hostname not in ("localhost", "127.0.0.1", "::1"):
                ssl_modes = parse_qs(parsed.query).get("sslmode", [])
                if ssl_modes not in (["require"], ["verify-ca"], ["verify-full"]):
                    raise ValueError
            origin = os.getenv(
                "PUBLIC_APP_ORIGIN", "https://supportbridge-agentathon.vercel.app"
            )
            if not re.fullmatch(
                "https://[a-zA-Z0-9.-]+(?::[0-9]{1,5})?|http://(?:localh"
                "ost|127\\.0\\.0\\.1)(?::[0-9]{1,5})?",
                origin,
            ):
                raise ValueError
            values = {}
            for attr, name, default, low, high in (
                ("session_ttl", "SESSION_TTL_SECONDS", 28800, 300, 604800),
                (
                    "session_daily_limit",
                    "SESSION_NEW_INVESTIGATIONS_PER_DAY",
                    2,
                    1,
                    100,
                ),
                ("global_active_limit", "MAX_GLOBAL_ACTIVE_RUNS", 4, 1, 100),
                ("global_daily_limit", "MAX_GLOBAL_NEW_RUNS_PER_DAY", 20, 1, 10000),
                ("experiment_limit", "MAX_EXPERIMENTS_PER_RUN", 8, 1, 8),
                ("model_limit", "MAX_MODEL_CALLS_PER_RUN", 10, 1, 20),
                ("lease_seconds", "STAGE_LEASE_SECONDS", 60, 20, 120),
            ):
                value = os.getenv(name, str(default))
                if (
                    not value.isascii()
                    or not value.isdigit()
                    or not low <= int(value) <= high
                ):
                    raise ValueError
                values[attr] = int(value)
            enabled = os.getenv("AI_RUNS_ENABLED", "false")
            if enabled not in ("true", "false"):
                raise ValueError
            return cls(url, app_origin=origin, ai_enabled=enabled == "true", **values)
        except ValueError:
            raise StorageConfigurationError(
                "Configure a valid backend DATABASE_URL and investigation settings"
            ) from None


class Database:
    def __init__(self, settings: Settings, *, schema: str = "public"):
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", schema):
            raise ValueError("Invalid storage schema")
        self.settings, self.schema = settings, schema

    @contextmanager
    def transaction(self, *, migration=False):
        if not _CONNECTION_SLOTS.acquire(timeout=3):
            raise StorageUnavailable("Investigation storage connections are busy")
        try:
            with psycopg.connect(
                self.settings.database_url,
                connect_timeout=3,
                prepare_threshold=None,
                row_factory=dict_row,
                application_name="supportbridge",
            ) as connection:
                connection.execute(
                    "SELECT set_config('search_path', %s, true)", (self.schema,)
                )
                connection.execute(
                    "SELECT set_config('statement_timeout', %s, true)",
                    ("30000" if migration else "5000",),
                )
                connection.execute("SELECT set_config('lock_timeout', '2000', true)")
                yield connection
        except psycopg.Error:
            raise StorageUnavailable(
                "Investigation storage is unavailable; check backend database setup"
            ) from None
        finally:
            _CONNECTION_SLOTS.release()
