"""Typed observations for read-only technical investigation tools."""

from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

if __package__ == "tools":
    from sandbox.models import QuoteRequest, QuoteResponse, ReleaseId
else:
    from ..sandbox.models import QuoteRequest, QuoteResponse, ReleaseId


class FrozenModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)


class ToolError(FrozenModel):
    code: Literal[
        "timeout",
        "environment_unavailable",
        "http_error",
        "rate_limited",
        "redirect_denied",
        "response_too_large",
        "invalid_response",
        "source_hash_mismatch",
        "source_unavailable",
        "budget_exhausted",
        "budget_unavailable",
    ]
    detail: str


class ReleaseIdentity(FrozenModel):
    release: ReleaseId
    repository: str
    commit_sha: str
    tag: str
    source_path: str
    source_url: str
    source_sha256: str


class ReleaseList(FrozenModel):
    provenance: Literal["packaged_release_manifest"] = "packaged_release_manifest"
    observed_at: AwareDatetime
    releases: tuple[ReleaseIdentity, ...]


class SourceLine(FrozenModel):
    number: Annotated[int, Field(ge=1)]
    text: str
    permalink: str


class GithubSource(FrozenModel):
    origin: Literal["github_rest"] = "github_rest"
    content_trust: Literal["untrusted_data"] = "untrusted_data"
    release: ReleaseId
    repository: str
    commit_sha: str
    path: str
    permalink: str
    retrieved_at: AwareDatetime
    content: str
    lines: tuple[SourceLine, ...]
    source_sha256: str
    manifest_hash_verified: bool | None


class SourceResult(FrozenModel):
    status: Literal["success", "error"]
    release: ReleaseId
    path: str
    observed_at: AwareDatetime
    http_status: int | None = None
    source: GithubSource | None = None
    error: ToolError | None = None


class HistoryEntry(FrozenModel):
    commit_sha: str
    committed_at: AwareDatetime
    source_path: str
    source_url: str


class HistoryResult(FrozenModel):
    content_trust: Literal["untrusted_data"] = "untrusted_data"
    coverage: Literal["single_page_approved_release_commits_only"] = (
        "single_page_approved_release_commits_only"
    )
    status: Literal["success", "error"]
    release: ReleaseId
    repository: str
    path: str
    pinned_commit_sha: str
    limit: int
    observed_at: AwareDatetime
    http_status: int | None = None
    entries: tuple[HistoryEntry, ...] = ()
    error: ToolError | None = None


class SourceComparison(FrozenModel):
    comparison_kind: Literal["local_unified_diff_of_github_sources"] = (
        "local_unified_diff_of_github_sources"
    )
    content_trust: Literal["untrusted_data"] = "untrusted_data"
    status: Literal["success", "error"]
    from_release: ReleaseId
    to_release: ReleaseId
    observed_at: AwareDatetime
    sources: tuple[GithubSource, ...] = ()
    unified_diff: str | None = None
    error: ToolError | None = None


class CheckoutObservation(FrozenModel):
    status: Literal[
        "success",
        "http_error",
        "environment_unavailable",
        "invalid_response",
        "blocked",
    ]
    request: QuoteRequest
    method: Literal["POST"] = "POST"
    path: Literal["/svc/api/sandbox/quote"] = "/svc/api/sandbox/quote"
    url: str
    executed_at: AwareDatetime
    elapsed_ms: Annotated[float, Field(ge=0)]
    http_status: int | None = None
    response: QuoteResponse | None = None
    error: ToolError | None = None
