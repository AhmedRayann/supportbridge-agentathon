"""Backend-only configuration validated against packaged release provenance."""

import os
import re
from pathlib import Path, PurePosixPath
from typing import Annotated, Literal, get_args

from pydantic import Field, SecretStr, ValidationError

from .investigation_models import FrozenModel, ReleaseId, ReleaseIdentity

_MANIFEST_PATH = Path(__file__).resolve().parents[1] / "sandbox/release_manifest.json"
_CALCULATION_SUFFIXES = {"v1.0": "releases/v1_0.py", "v1.1": "releases/v1_1.py"}
_SHARED_SUFFIXES = ("models.py", "router.py")
PRODUCTION_SANDBOX_ORIGIN = "https://supportbridge-agentathon.vercel.app"


class ConfigurationError(ValueError):
    """Operator configuration must be corrected; never substitute an environment."""


class Repository(FrozenModel):
    owner: Annotated[str, Field(pattern=r"^[A-Za-z0-9-]{1,39}$")]
    name: Annotated[str, Field(pattern=r"^[A-Za-z0-9_.-]{1,100}$")]


class ReleaseMetadata(FrozenModel):
    commit_sha: Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]
    tag: str
    source_path: str
    source_url: str
    source_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class Manifest(FrozenModel):
    schema_version: Literal[1]
    repository: Repository
    releases: dict[ReleaseId, ReleaseMetadata]


class GithubSettings(FrozenModel):
    manifest: Manifest
    source_prefix: str
    token: SecretStr | None = Field(default=None, repr=False)

    @property
    def repository(self) -> str:
        repo = self.manifest.repository
        return f"{repo.owner}/{repo.name}"

    def allowed_paths(self, release: ReleaseId) -> tuple[str, ...]:
        return (
            self.manifest.releases[release].source_path,
            *(self.source_prefix + suffix for suffix in _SHARED_SUFFIXES),
        )

    def identity(self, release: ReleaseId) -> ReleaseIdentity:
        return ReleaseIdentity(
            release=release,
            repository=self.repository,
            **self.manifest.releases[release].model_dump(),
        )


def github_settings() -> GithubSettings:
    try:
        manifest = Manifest.model_validate_json(_MANIFEST_PATH.read_bytes())
        if set(manifest.releases) != set(get_args(ReleaseId)):
            raise ValueError
        prefix = (
            str(PurePosixPath(manifest.releases["v1.0"].source_path).parents[1]) + "/"
        )
        if not re.fullmatch(r"(?:[A-Za-z0-9_-]+/)+", prefix):
            raise ValueError
        repo = manifest.repository
        repository = f"{repo.owner}/{repo.name}"
        for release, metadata in manifest.releases.items():
            if (
                metadata.source_path != prefix + _CALCULATION_SUFFIXES[release]
                or metadata.tag != f"checkout-{release}"
                or metadata.source_url
                != (
                    f"https://github.com/{repository}/blob/"
                    f"{metadata.commit_sha}/{metadata.source_path}"
                )
            ):
                raise ValueError
            reference = os.getenv(
                f"DEMO_RELEASE_{release.upper().replace('.', '_')}_REF"
            )
            if reference and reference != metadata.commit_sha:
                raise ValueError
        for name, expected in (
            ("DEMO_GITHUB_OWNER", repo.owner),
            ("DEMO_GITHUB_REPO", repo.name),
            ("DEMO_SOURCE_PREFIX", prefix),
        ):
            configured = os.getenv(name)
            if configured and configured != expected:
                raise ValueError
        token = os.getenv("GITHUB_TOKEN")
        if token and (
            not token.isascii() or any(c.isspace() or ord(c) < 32 for c in token)
        ):
            raise ValueError
        return GithubSettings(
            manifest=manifest,
            source_prefix=prefix,
            token=SecretStr(token) if token else None,
        )
    except (OSError, ValueError, IndexError, ValidationError):
        raise ConfigurationError(
            "Invalid approved GitHub release configuration"
        ) from None


def approved_path(settings: GithubSettings, release: ReleaseId, path: str) -> str:
    # Exact membership also rejects normalization tricks, encoded paths and URLs.
    if path not in settings.allowed_paths(release):
        raise ValueError("Source path is not approved for this release")
    return path


def sandbox_origin() -> str:
    value = os.getenv("SANDBOX_API_BASE_URL", "")
    if value.rstrip("/") == PRODUCTION_SANDBOX_ORIGIN and value in (
        PRODUCTION_SANDBOX_ORIGIN,
        PRODUCTION_SANDBOX_ORIGIN + "/",
    ):
        return PRODUCTION_SANDBOX_ORIGIN
    match = re.fullmatch(r"http://(localhost|127\.0\.0\.1)(?::([0-9]{1,5}))?/?", value)
    if match and (match[2] is None or 1 <= int(match[2]) <= 65535):
        return value.removesuffix("/")
    raise ConfigurationError("Set SANDBOX_API_BASE_URL to an approved sandbox origin")
