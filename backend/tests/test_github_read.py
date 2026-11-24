"""Deterministic mocked GitHub tests; these do not establish live connectivity."""

import base64
import hashlib
import json
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from backend.tools import _config, _http
from backend.tools import github_read as tools

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = json.loads((ROOT / "backend/sandbox/release_manifest.json").read_bytes())
RELEASES = MANIFEST["releases"]
pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True)
def configuration(monkeypatch):
    for key in (
        "DEMO_GITHUB_OWNER",
        "DEMO_GITHUB_REPO",
        "DEMO_SOURCE_PREFIX",
        "DEMO_RELEASE_V1_0_REF",
        "DEMO_RELEASE_V1_1_REF",
        "GITHUB_TOKEN",
    ):
        monkeypatch.delenv(key, raising=False)


@pytest.fixture
def mock_github(monkeypatch):
    requests = []

    def install(handler):
        def respond(request):
            requests.append(request)
            return handler(request)

        monkeypatch.setattr(
            _http,
            "_client",
            lambda: httpx.AsyncClient(
                transport=httpx.MockTransport(respond),
                follow_redirects=False,
                trust_env=False,
                timeout=5,
            ),
        )
        return requests

    return install


def source_response(release, path=None, content=None):
    # Packaged files are explicit mock fixtures, never live tool evidence.
    path = path or RELEASES[release]["source_path"]
    content = (
        content
        if content is not None
        else (ROOT / path).read_bytes().replace(b"\r\n", b"\n")
    )
    return {
        "type": "file",
        "path": path,
        "size": len(content),
        "encoding": "base64",
        "content": base64.b64encode(content).decode(),
        "download_url": "https://excluded.invalid/private",
        "internal": "DO_NOT_EXPOSE",
    }


async def test_manifest_identities_do_not_claim_live_verification(mock_github):
    requests = mock_github(lambda r: pytest.fail("Unexpected network call"))
    result = tools.list_checkout_releases()
    assert result.provenance == "packaged_release_manifest"
    assert len(result.releases) == 2 and requests == []
    for identity in result.releases:
        assert (
            identity.model_dump(exclude={"release", "repository"})
            == RELEASES[identity.release]
        )


@pytest.mark.parametrize("release", RELEASES)
async def test_source_is_pinned_hashed_exact_and_line_citable(release, mock_github):
    metadata = RELEASES[release]
    requests = mock_github(lambda r: httpx.Response(200, json=source_response(release)))
    result = await tools.get_checkout_source(release, metadata["source_path"])
    assert result.status == "success" and result.http_status == 200
    source = result.source
    assert source.manifest_hash_verified is True
    assert source.source_sha256 == metadata["source_sha256"]
    assert hashlib.sha256(source.content.encode()).hexdigest() == source.source_sha256
    assert source.content_trust == "untrusted_data" and source.origin == "github_rest"
    assert source.commit_sha == metadata["commit_sha"]
    assert source.permalink == metadata["source_url"]
    assert [line.text for line in source.lines] == source.content.splitlines()
    assert source.lines[0].number == 1
    assert source.lines[-1].permalink.endswith(f"#L{len(source.lines)}")
    assert source.retrieved_at.tzinfo is not None
    assert "DO_NOT_EXPOSE" not in result.model_dump_json()
    assert len(requests) == 1
    request = requests[0]
    assert request.method == "GET" and request.url.host == "api.github.com"
    assert request.url.params["ref"] == metadata["commit_sha"]
    assert request.url.path.endswith("/contents/" + metadata["source_path"])


@pytest.mark.parametrize("release", RELEASES)
@pytest.mark.parametrize(
    "path", ["backend/sandbox/models.py", "backend/sandbox/router.py"]
)
async def test_shared_files_are_allowed_at_both_pins(release, path, mock_github):
    requests = mock_github(
        lambda r: httpx.Response(200, json=source_response(release, path))
    )
    result = await tools.get_checkout_source(release, path)
    assert result.status == "success" and result.source.manifest_hash_verified is None
    assert requests[0].url.params["ref"] == RELEASES[release]["commit_sha"]


@pytest.mark.parametrize(
    "path",
    [
        "AGENTS.md",
        "README.md",
        "docs/IMPLEMENTATION_BLUEPRINT.md",
        "docs/MILESTONE_2A_RESULTS.md",
        "backend/oracle/shipping_contract.py",
        "backend/tests/test_checkout.py",
        "eval/cases.json",
        "backend/main.py",
        "backend/sandbox/__init__.py",
        "../backend/sandbox/models.py",
        "/backend/sandbox/models.py",
        "backend\\sandbox\\models.py",
        "backend/sandbox/../oracle/shipping_contract.py",
        "backend/sandbox/%2e%2e/oracle/shipping_contract.py",
        "backend%2fsandbox%2fmodels.py",
        "https://github.com/a/b",
        "backend/sandbox/models.py?ref=main",
        "backend/sandbox/models.py\n",
        "backend/sandbox/releases/v1_1.py",
    ],
)
async def test_denied_paths_never_make_requests(path, mock_github):
    requests = mock_github(lambda r: pytest.fail("Denied path reached HTTP"))
    with pytest.raises(ValueError):
        await tools.get_checkout_source("v1.0", path)
    with pytest.raises(ValueError):
        await tools.get_checkout_history("v1.0", path)
    assert requests == []


@pytest.mark.parametrize("release", ["main", "checkout-v1.0", "v2.0", "../", None, 1])
async def test_unsupported_refs_are_rejected(release, mock_github):
    requests = mock_github(lambda r: pytest.fail("Invalid ref reached HTTP"))
    with pytest.raises(ValidationError):
        await tools.get_checkout_source(release, "backend/sandbox/models.py")
    with pytest.raises(ValidationError):
        await tools.compare_checkout_sources("v1.0", release)
    assert requests == []


@pytest.mark.parametrize(
    "kwargs",
    [
        {"sha": "main"},
        {"repository": "other/private"},
        {"url": "https://elsewhere.invalid"},
        {"headers": {}},
        {"method": "PUT"},
    ],
)
async def test_no_extra_target_or_mutation_arguments(kwargs):
    with pytest.raises(ValidationError):
        await tools.get_checkout_source("v1.0", "backend/sandbox/models.py", **kwargs)


@pytest.mark.parametrize(
    "key,value",
    [
        ("DEMO_GITHUB_OWNER", "different"),
        ("DEMO_GITHUB_REPO", "elsewhere"),
        ("DEMO_SOURCE_PREFIX", "backend/"),
        ("DEMO_RELEASE_V1_0_REF", "main"),
        ("DEMO_RELEASE_V1_1_REF", "checkout-v1.1"),
        ("GITHUB_TOKEN", "bad\ntoken"),
    ],
)
async def test_configuration_must_match_manifest(key, value, monkeypatch, mock_github):
    requests = mock_github(lambda r: pytest.fail("Bad config reached network"))
    monkeypatch.setenv(key, value)
    with pytest.raises(_config.ConfigurationError) as error:
        tools.list_checkout_releases()
    assert value not in str(error.value) and requests == []


async def test_valid_explicit_configuration_and_private_token(monkeypatch, mock_github):
    for name, value in {
        "DEMO_GITHUB_OWNER": MANIFEST["repository"]["owner"],
        "DEMO_GITHUB_REPO": MANIFEST["repository"]["name"],
        "DEMO_SOURCE_PREFIX": "backend/sandbox/",
        "DEMO_RELEASE_V1_0_REF": RELEASES["v1.0"]["commit_sha"],
        "DEMO_RELEASE_V1_1_REF": RELEASES["v1.1"]["commit_sha"],
        "GITHUB_TOKEN": "secret-token-sentinel",
    }.items():
        monkeypatch.setenv(name, value)
    requests = mock_github(
        lambda r: httpx.Response(500, text="secret-token-sentinel DO_NOT_EXPOSE")
    )
    result = await tools.get_checkout_source("v1.0", RELEASES["v1.0"]["source_path"])
    assert requests[0].headers["Authorization"] == "Bearer secret-token-sentinel"
    assert "sentinel" not in result.model_dump_json()
    assert "sentinel" not in repr(_config.github_settings())


@pytest.mark.parametrize(
    "damage", ["hash", "path", "size", "encoding", "type", "base64", "json"]
)
async def test_invalid_or_mismatched_sources_are_not_exposed(damage, mock_github):
    data = source_response("v1.0")
    if damage == "hash":
        data = source_response("v1.0", content=b"modified source\n")
    elif damage == "path":
        data["path"] = "AGENTS.md"
    elif damage == "size":
        data["size"] += 1
    elif damage == "encoding":
        data["encoding"] = "none"
    elif damage == "type":
        data["type"] = "symlink"
    elif damage == "base64":
        data["content"] = "!!invalid!!"
    requests = mock_github(
        lambda r: httpx.Response(
            200, content=b"{" if damage == "json" else json.dumps(data).encode()
        )
    )
    result = await tools.get_checkout_source("v1.0", RELEASES["v1.0"]["source_path"])
    assert result.status == "error" and result.source is None
    assert result.error.code == (
        "source_hash_mismatch" if damage == "hash" else "invalid_response"
    )
    assert len(requests) == 1


@pytest.mark.parametrize(
    "status,headers,code",
    [
        (404, {}, "source_unavailable"),
        (500, {}, "http_error"),
        (403, {}, "http_error"),
        (403, {"x-ratelimit-remaining": "0"}, "rate_limited"),
        (429, {}, "rate_limited"),
        (302, {"location": "https://excluded.invalid"}, "redirect_denied"),
    ],
)
async def test_http_errors_never_fall_back(status, headers, code, mock_github):
    requests = mock_github(
        lambda r: httpx.Response(status, headers=headers, text="PRIVATE")
    )
    result = await tools.get_checkout_source("v1.0", RELEASES["v1.0"]["source_path"])
    assert result.http_status == status and result.error.code == code
    assert result.source is None and len(requests) == 1
    assert "PRIVATE" not in result.model_dump_json()


@pytest.mark.parametrize(
    "exception,code",
    [(httpx.ReadTimeout, "timeout"), (httpx.ConnectError, "environment_unavailable")],
)
async def test_network_failures_are_explicit(exception, code, mock_github):
    def handler(request):
        raise exception("PRIVATE", request=request)

    requests = mock_github(handler)
    result = await tools.get_checkout_source("v1.1", RELEASES["v1.1"]["source_path"])
    assert result.error.code == code and result.http_status is None
    assert result.source is None and len(requests) == 1


async def test_response_size_limit(mock_github):
    mock_github(
        lambda r: httpx.Response(200, content=b"x" * (_http.MAX_RESPONSE_BYTES + 1))
    )
    result = await tools.get_checkout_source("v1.0", RELEASES["v1.0"]["source_path"])
    assert result.error.code == "response_too_large" and result.http_status == 200


async def test_history_is_path_scoped_and_excluded_metadata_is_not_returned(
    mock_github,
):
    sha = RELEASES["v1.1"]["commit_sha"]
    data = [
        {
            "sha": sha,
            "commit": {
                "committer": {"date": "2026-11-21T10:00:00Z"},
                "message": "PRIVATE_DIAGNOSIS",
            },
            "files": [
                {"filename": "AGENTS.md", "patch": "PRIVATE_DIAGNOSIS"},
                {
                    "filename": "backend/oracle/shipping_contract.py",
                    "patch": "PRIVATE_DIAGNOSIS",
                },
            ],
            "html_url": "https://excluded.invalid/PRIVATE_DIAGNOSIS",
        },
        {"sha": "0" * 40, "commit": {"message": "PRIVATE_DIAGNOSIS"}},
    ]
    requests = mock_github(lambda r: httpx.Response(200, json=data))
    path = RELEASES["v1.1"]["source_path"]
    result = await tools.get_checkout_history("v1.1", path, limit=2)
    assert result.status == "success" and len(result.entries) == 1
    assert result.entries[0].commit_sha == sha
    assert result.entries[0].source_url.endswith(f"/{sha}/{path}")
    assert "PRIVATE_DIAGNOSIS" not in result.model_dump_json()
    assert "AGENTS.md" not in result.model_dump_json()
    assert requests[0].url.params == httpx.QueryParams(sha=sha, path=path, per_page=2)


@pytest.mark.parametrize("limit", [0, 6, True, "2", 1.5])
async def test_history_limits(limit):
    with pytest.raises(ValidationError):
        await tools.get_checkout_history("v1.0", "backend/sandbox/models.py", limit)


@pytest.mark.parametrize(
    "data", [{}, [{"sha": RELEASES["v1.0"]["commit_sha"]}], "invalid"]
)
async def test_malformed_history_is_an_error(data, mock_github):
    mock_github(lambda r: httpx.Response(200, json=data))
    result = await tools.get_checkout_history("v1.0", "backend/sandbox/models.py")
    assert result.error.code == "invalid_response" and result.entries == ()


async def test_comparison_uses_two_github_snapshots_and_truthful_diff(mock_github):
    def handler(request):
        release = next(
            r
            for r, m in RELEASES.items()
            if m["commit_sha"] == request.url.params["ref"]
        )
        return httpx.Response(200, json=source_response(release))

    requests = mock_github(handler)
    result = await tools.compare_checkout_sources("v1.0", "v1.1")
    assert result.status == "success" and len(requests) == 2
    assert result.comparison_kind == "local_unified_diff_of_github_sources"
    assert all(s.manifest_hash_verified for s in result.sources)
    assert "@@" in result.unified_diff
    assert "releases/v1_0.py@" in result.unified_diff
    assert "releases/v1_1.py@" in result.unified_diff
    assert "AGENTS.md" not in result.model_dump_json()
    assert all("/contents/" in r.url.path for r in requests)


async def test_failed_comparison_does_not_fabricate_diff(mock_github):
    mock_github(lambda r: httpx.Response(404))
    result = await tools.compare_checkout_sources("v1.0", "v1.1")
    assert result.status == "error" and result.unified_diff is None
    assert result.sources == ()


@pytest.mark.parametrize("damage", ["missing", "schema", "prefix", "short_path", "url"])
async def test_manifest_configuration_fails_closed(damage, monkeypatch, tmp_path):
    manifest = json.loads(json.dumps(MANIFEST))
    if damage == "schema":
        manifest["schema_version"] = 2
    elif damage == "prefix":
        manifest["releases"]["v1.0"]["source_path"] = "../releases/v1_0.py"
    elif damage == "short_path":
        manifest["releases"]["v1.0"]["source_path"] = "v1_0.py"
    elif damage == "url":
        manifest["releases"]["v1.0"]["source_url"] = "https://excluded.invalid"
    target = tmp_path / "manifest.json"
    if damage != "missing":
        target.write_text(json.dumps(manifest))
    monkeypatch.setattr(_config, "_MANIFEST_PATH", target)
    with pytest.raises(_config.ConfigurationError):
        tools.list_checkout_releases()


async def test_sha_resolution_reads_manifest_not_tool_constants(
    monkeypatch,
    tmp_path,
    mock_github,
):
    manifest = json.loads(json.dumps(MANIFEST))
    metadata = manifest["releases"]["v1.0"]
    metadata["commit_sha"] = "a" * 40
    metadata["source_url"] = (
        f"https://github.com/{MANIFEST['repository']['owner']}/"
        f"{MANIFEST['repository']['name']}/blob/{'a' * 40}/{metadata['source_path']}"
    )
    target = tmp_path / "manifest.json"
    target.write_text(json.dumps(manifest))
    monkeypatch.setattr(_config, "_MANIFEST_PATH", target)
    requests = mock_github(lambda r: httpx.Response(200, json=source_response("v1.0")))
    result = await tools.get_checkout_source("v1.0", metadata["source_path"])
    assert result.source.commit_sha == "a" * 40
    assert requests[0].url.params["ref"] == "a" * 40


async def test_deeply_nested_json_is_a_structured_source_error(mock_github):
    mock_github(lambda r: httpx.Response(200, content=b"[" * 1100 + b"]" * 1100))
    result = await tools.get_checkout_source("v1.0", RELEASES["v1.0"]["source_path"])
    assert result.error.code == "invalid_response" and result.source is None
