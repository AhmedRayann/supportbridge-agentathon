"""Read only approved historical checkout sources through the GitHub REST API."""

import asyncio
import base64
import binascii
import difflib
import hashlib
import json
from datetime import UTC, datetime
from typing import Annotated

from pydantic import Field, ValidationError, validate_call

from . import _http
from ._config import GithubSettings, approved_path, github_settings
from .investigation_models import (
    GithubSource,
    HistoryEntry,
    HistoryResult,
    ReleaseId,
    ReleaseList,
    SourceComparison,
    SourceLine,
    SourceResult,
    ToolError,
)

__all__ = [
    "list_checkout_releases",
    "get_checkout_source",
    "get_checkout_history",
    "compare_checkout_sources",
]
SourcePath = Annotated[str, Field(min_length=1, max_length=200)]
HistoryLimit = Annotated[int, Field(ge=1, le=5)]
MAX_SOURCE_BYTES = 32_768


def _headers(settings: GithubSettings) -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "SupportBridge",
    }
    if settings.token:
        headers["Authorization"] = f"Bearer {settings.token.get_secret_value()}"
    return headers


@validate_call(config={"strict": True})
def list_checkout_releases() -> ReleaseList:
    """List packaged identities without claiming live GitHub verification."""
    settings = github_settings()
    return ReleaseList(
        observed_at=datetime.now(UTC),
        releases=tuple(
            settings.identity(release) for release in settings.manifest.releases
        ),
    )


@validate_call(config={"strict": True})
async def get_checkout_source(release: ReleaseId, path: SourcePath) -> SourceResult:
    """Fetch an allowlisted file at its exact approved historical commit."""
    settings = github_settings()
    approved_path(settings, release, path)
    identity = settings.identity(release)
    observed_at = datetime.now(UTC)
    url = (
        f"https://api.github.com/repos/{settings.repository}/contents/{path}"
        f"?ref={identity.commit_sha}"
    )
    raw = await _http.request("GET", url, headers=_headers(settings))
    error = raw.error
    source = None
    if error and raw.status == 404:
        error = ToolError(
            code="source_unavailable",
            detail="Approved historical source is unavailable",
        )
    if error is None:
        try:
            data = json.loads(raw.body)
            if (
                not isinstance(data, dict)
                or data.get("type") != "file"
                or data.get("path") != path
                or data.get("encoding") != "base64"
                or type(data.get("size")) is not int
                or not 0 <= data["size"] <= MAX_SOURCE_BYTES
                or not isinstance(data.get("content"), str)
            ):
                raise ValueError
            content = base64.b64decode("".join(data["content"].split()), validate=True)
            if len(content) != data["size"] or len(content) > MAX_SOURCE_BYTES:
                raise ValueError
            text = content.decode("utf-8")
            digest = hashlib.sha256(content).hexdigest()
            is_calculation = path == identity.source_path
            if is_calculation and digest != identity.source_sha256:
                error = ToolError(
                    code="source_hash_mismatch",
                    detail="Source did not match approved SHA-256",
                )
            else:
                permalink = (
                    f"https://github.com/{settings.repository}/blob/"
                    f"{identity.commit_sha}/{path}"
                )
                source = GithubSource(
                    release=release,
                    repository=settings.repository,
                    commit_sha=identity.commit_sha,
                    path=path,
                    permalink=permalink,
                    retrieved_at=datetime.now(UTC),
                    content=text,
                    source_sha256=digest,
                    manifest_hash_verified=True if is_calculation else None,
                    lines=tuple(
                        SourceLine(number=n, text=line, permalink=f"{permalink}#L{n}")
                        for n, line in enumerate(text.splitlines(), 1)
                    ),
                )
        except (
            ValueError,
            KeyError,
            TypeError,
            UnicodeError,
            binascii.Error,
            RecursionError,
        ):
            error = ToolError(
                code="invalid_response", detail="GitHub source response was invalid"
            )
    return SourceResult(
        status="error" if error else "success",
        release=release,
        path=path,
        observed_at=observed_at,
        http_status=raw.status,
        source=source,
        error=error,
    )


@validate_call(config={"strict": True})
async def get_checkout_history(
    release: ReleaseId,
    path: SourcePath,
    limit: HistoryLimit = 5,
) -> HistoryResult:
    """Read scoped history; expose only approved release commit identities."""
    settings = github_settings()
    approved_path(settings, release, path)
    identity = settings.identity(release)
    observed_at = datetime.now(UTC)
    url = (
        f"https://api.github.com/repos/{settings.repository}/commits"
        f"?sha={identity.commit_sha}&path={path}&per_page={limit}"
    )
    raw = await _http.request("GET", url, headers=_headers(settings))
    error = raw.error
    entries = []
    if error is None:
        try:
            data = json.loads(raw.body)
            if not isinstance(data, list) or len(data) > limit:
                raise ValueError
            approved = {m.commit_sha: r for r, m in settings.manifest.releases.items()}
            seen = set()
            for item in data:
                if not isinstance(item, dict) or not isinstance(item.get("sha"), str):
                    raise ValueError
                sha = item["sha"]
                if sha not in approved or path not in settings.allowed_paths(
                    approved[sha]
                ):
                    continue
                if sha in seen:
                    raise ValueError
                seen.add(sha)
                # Omit messages, authors, file lists, patches and provider URLs.
                entries.append(
                    HistoryEntry.model_validate_json(
                        json.dumps(
                            {
                                "commit_sha": sha,
                                "committed_at": item["commit"]["committer"]["date"],
                                "source_path": path,
                                "source_url": f"https://github.com/{settings.repository}/blob/{sha}/{path}",
                            }
                        )
                    )
                )
        except (ValueError, KeyError, TypeError, ValidationError, RecursionError):
            entries = []
            error = ToolError(
                code="invalid_response", detail="GitHub history response was invalid"
            )
    return HistoryResult(
        status="error" if error else "success",
        release=release,
        repository=settings.repository,
        path=path,
        pinned_commit_sha=identity.commit_sha,
        limit=limit,
        observed_at=observed_at,
        http_status=raw.status,
        entries=tuple(entries),
        error=error,
    )


@validate_call(config={"strict": True})
async def compare_checkout_sources(
    from_release: ReleaseId,
    to_release: ReleaseId,
) -> SourceComparison:
    """Compare two GitHub source snapshots locally; not a historical Git patch."""
    settings = github_settings()
    observed_at = datetime.now(UTC)
    results = await asyncio.gather(
        *(
            get_checkout_source(
                release, settings.manifest.releases[release].source_path
            )
            for release in (from_release, to_release)
        )
    )
    error = next((result.error for result in results if result.error), None)
    sources = tuple(result.source for result in results if result.source is not None)
    difference = None
    if error is None:
        left, right = sources
        difference = "".join(
            difflib.unified_diff(
                left.content.splitlines(keepends=True),
                right.content.splitlines(keepends=True),
                fromfile=f"{left.path}@{left.commit_sha}",
                tofile=f"{right.path}@{right.commit_sha}",
            )
        )
    return SourceComparison(
        status="error" if error else "success",
        from_release=from_release,
        to_release=to_release,
        observed_at=observed_at,
        sources=sources,
        unified_diff=difference,
        error=error,
    )
