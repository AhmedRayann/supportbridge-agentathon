import hashlib
import json
import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import get_args

import pytest

from backend.main import app
from backend.sandbox import router
from backend.sandbox.models import ReleaseId
from backend.sandbox.releases import v1_0, v1_1

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "backend/sandbox/release_manifest.json"
APPROVED_RELEASES = {
    "v1.0": (
        "a4eeea911604494f693e027cdaca5f2da2f78a7e",
        "backend/sandbox/releases/v1_0.py",
    ),
    "v1.1": (
        "c8473e4fcdb3f71630301c13c37fbf742c2a14ef",
        "backend/sandbox/releases/v1_1.py",
    ),
}


@pytest.fixture
def manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_manifest_has_only_neutral_identity_fields(manifest: dict) -> None:
    # A closed schema prevents adding narrative, scenarios or expected outcomes.
    assert set(manifest) == {"schema_version", "repository", "releases"}
    assert manifest["schema_version"] == 1
    assert manifest["repository"] == {
        "owner": "AhmedRayann",
        "name": "supportbridge-agentathon",
    }
    assert set(manifest["releases"]) == set(APPROVED_RELEASES)
    for metadata in manifest["releases"].values():
        assert set(metadata) == {
            "commit_sha",
            "tag",
            "source_path",
            "source_url",
            "source_sha256",
        }


@pytest.mark.parametrize("release", APPROVED_RELEASES)
def test_manifest_pins_approved_source_and_url(manifest: dict, release: str) -> None:
    metadata = manifest["releases"][release]
    approved_sha, approved_path = APPROVED_RELEASES[release]
    assert re.fullmatch(r"[0-9a-f]{40}", metadata["commit_sha"])
    assert metadata["commit_sha"] == approved_sha
    assert metadata["tag"] == f"checkout-{release}"

    source_path = metadata["source_path"]
    path = PurePosixPath(source_path)
    assert not path.is_absolute()
    assert path.as_posix() == source_path
    assert ".." not in path.parts and "\\" not in source_path
    assert source_path == approved_path
    assert path.parts[:3] == ("backend", "sandbox", "releases")
    assert (ROOT / source_path).resolve().is_relative_to(ROOT / "backend/sandbox")
    assert metadata["source_url"] == (
        "https://github.com/AhmedRayann/supportbridge-agentathon/blob/"
        f"{approved_sha}/{approved_path}"
    )
    assert re.fullmatch(r"[0-9a-f]{64}", metadata["source_sha256"])
    source = (ROOT / source_path).read_bytes().replace(b"\r\n", b"\n")
    assert hashlib.sha256(source).hexdigest() == metadata["source_sha256"]


def test_manifest_releases_match_existing_static_dispatch(manifest: dict) -> None:
    assert set(manifest["releases"]) == set(get_args(ReleaseId))
    assert router._QUOTE_CALCULATORS == {
        "v1.0": v1_0.calculate_quote,
        "v1.1": v1_1.calculate_quote,
    }
    for release, calculator in router._QUOTE_CALCULATORS.items():
        source = Path(calculator.__code__.co_filename).resolve()
        assert source == ROOT / manifest["releases"][release]["source_path"]
    assert set(app.openapi()["paths"]) == {
        "/health",
        "/svc/api/health",
        "/svc/api/sandbox/quote",
    }


@pytest.mark.parametrize("release", APPROVED_RELEASES)
def test_manifest_matches_historical_source(
    manifest: dict, release: str, release_git_history: Callable[..., bytes]
) -> None:
    metadata = manifest["releases"][release]
    sha = metadata["commit_sha"]
    assert release_git_history("rev-parse", f"{sha}^{{commit}}").decode().strip() == sha
    source = release_git_history("show", f"{sha}:{metadata['source_path']}")
    assert hashlib.sha256(source).hexdigest() == metadata["source_sha256"]
    assert source == (ROOT / metadata["source_path"]).read_bytes().replace(
        b"\r\n", b"\n"
    )


def test_release_commits_have_real_ancestry(
    release_git_history: Callable[..., bytes],
) -> None:
    first = APPROVED_RELEASES["v1.0"][0]
    second = APPROVED_RELEASES["v1.1"][0]
    assert release_git_history("merge-base", "--is-ancestor", first, second) == b""
