"""Canonical hashing and bounded public-observation serialization."""

import hashlib
import json
import os
import re

FORBIDDEN_KEYS = {
    "authorization",
    "cookie",
    "set_cookie",
    "session_token",
    "session_credential",
    "api_key",
    "database_url",
    "github_token",
    "secret",
    "password",
    "chain_of_thought",
    "private_reasoning",
    "reasoning",
    "analysis",
}


def canonical_json(value: object, *, maximum: int = 1_048_576) -> str:
    def inspect(item, depth=0):
        if depth > 30:
            raise ValueError("Observation nesting exceeds its limit")
        if isinstance(item, dict):
            for key, child in item.items():
                if not isinstance(key, str):
                    raise ValueError("Observation keys must be strings")
                normalized = re.sub(r"[^a-z0-9]+", "_", key.casefold()).strip("_")
                if normalized in FORBIDDEN_KEYS or normalized.endswith("_api_key"):
                    raise ValueError("Private data is not permitted in observations")
                inspect(child, depth + 1)
        elif isinstance(item, (list, tuple)):
            for child in item:
                inspect(child, depth + 1)
        elif isinstance(item, str):
            if re.search(r"(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{43}(?![A-Za-z0-9_-])", item):
                raise ValueError(
                    "Session credentials are not permitted in observations"
                )
            if re.search(
                "postgres(?:ql)?://|://[^/\\s]+:[^/\\s]+@|Bearer\\s+\\S+|gh["
                "pousr]_[A-Za-z0-9]{16,}|AIza[A-Za-z0-9_-]{25,}",
                item,
                re.I,
            ):
                raise ValueError("Credentials are not permitted in observations")
        elif item is not None and type(item) not in (bool, int, float):
            raise ValueError("Observations must contain only JSON values")

    inspect(value)
    try:
        content = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (ValueError, TypeError, RecursionError):
        raise ValueError("Observation is not valid canonical JSON") from None
    for name, secret in os.environ.items():
        if (
            (name.endswith(("_KEY", "_TOKEN")) or name == "DATABASE_URL")
            and len(secret) >= 8
            and secret in content
        ):
            raise ValueError("Credentials are not permitted in observations")
    if len(content.encode("utf-8")) > maximum:
        raise ValueError("Observation exceeds its byte limit")
    return content


def content_hash(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()
