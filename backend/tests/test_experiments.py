"""Mocked HTTP observations, plus a local ASGI adapter integration check."""

import asyncio
import json

import httpx
import pytest
from pydantic import ValidationError

from backend.main import app
from backend.tools import _config, _http
from backend.tools import experiments as tools

pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True)
def sandbox_environment(monkeypatch):
    monkeypatch.setenv("SANDBOX_API_BASE_URL", "http://127.0.0.1:8000")


@pytest.fixture
def mock_checkout(monkeypatch):
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
            ),
        )
        return requests

    return install


def quote_body(release="v1.0", subtotal=11000, percent=15):
    # Explicit mocked HTTP body; the adapter must preserve it without policy assertions.
    return {
        "release": release,
        "subtotal_cents": subtotal,
        "discount_percent": percent,
        "discount_cents": 1650,
        "discounted_subtotal_cents": 9350,
        "shipping_cents": 0,
        "total_cents": 9350,
    }


@pytest.mark.parametrize("release", ["v1.0", "v1.1"])
async def test_request_and_returned_observation_are_exact(release, mock_checkout):
    body = quote_body(release)
    requests = mock_checkout(lambda r: httpx.Response(200, json=body))
    result = await tools.run_checkout_quote(release, 11000, 15)
    assert result.status == "success" and result.response.model_dump() == body
    assert result.http_status == 200 and result.elapsed_ms >= 0
    assert result.executed_at.tzinfo is not None
    assert result.method == "POST" and result.path == tools.QUOTE_PATH
    assert len(requests) == 1 and requests[0].method == "POST"
    assert requests[0].url == "http://127.0.0.1:8000/svc/api/sandbox/quote"
    assert json.loads(requests[0].content) == result.request.model_dump()
    assert "authorization" not in requests[0].headers
    for forbidden in ("verdict", "expected_total", "root_cause", "policy", "oracle"):
        assert forbidden not in result.model_dump_json()


@pytest.mark.parametrize("release", ["v1.0", "v1.1"])
@pytest.mark.parametrize(
    "subtotal,percent,total",
    [
        (12500, 20, 10000),
        (11000, 5, 10450),
        (8000, 15, 7550),
        (10000, 0, 10000),
        (0, 100, 750),
        (100_000_000, 0, 100_000_000),
    ],
)
async def test_multiple_selected_inputs_against_actual_asgi_app(
    release,
    subtotal,
    percent,
    total,
    monkeypatch,
):
    monkeypatch.setattr(
        _http,
        "_client",
        lambda: httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), follow_redirects=False
        ),
    )
    result = await tools.run_checkout_quote(release, subtotal, percent)
    assert result.status == "success" and result.response.total_cents == total
    assert result.request.subtotal_cents == subtotal
    assert result.request.discount_percent == percent


@pytest.mark.parametrize(
    "subtotal,percent",
    [
        (-1, 15),
        (100_000_001, 15),
        (True, 15),
        ("11000", 15),
        (11000.0, 15),
        (None, 15),
        (11000, -1),
        (11000, 101),
        (11000, True),
        (11000, "15"),
        (11000, 15.0),
        (11000, None),
    ],
)
async def test_strict_checkout_bounds(subtotal, percent, mock_checkout):
    requests = mock_checkout(lambda r: pytest.fail("Invalid arguments reached HTTP"))
    with pytest.raises(ValidationError):
        await tools.run_checkout_quote("v1.0", subtotal, percent)
    assert requests == []


@pytest.mark.parametrize("release", ["v2.0", "main", "checkout-v1.0", None, 1])
async def test_release_allowlist(release):
    with pytest.raises(ValidationError):
        await tools.run_checkout_quote(release, 10000, 0)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"url": "https://excluded.invalid"},
        {"method": "DELETE"},
        {"headers": {"Authorization": "arbitrary"}},
        {"path": "/health"},
        {"reserve_experiment": {"remaining": 8}},
    ],
)
async def test_no_arbitrary_targets_methods_or_budget_dict(kwargs):
    with pytest.raises(ValidationError):
        await tools.run_checkout_quote("v1.0", 10000, 0, **kwargs)


@pytest.mark.parametrize(
    "origin",
    [
        "",
        "https://excluded.invalid",
        "http://169.254.169.254",
        "http://192.168.0.1",
        "https://supportbridge-agentathon.vercel.app.evil.invalid",
        "http://localhost.evil.invalid",
        "http://localhost:8000/path",
        "http://localhost:8000?x=y",
        "http://localhost#x",
        "http://user:secret@localhost",
        "http://127.0.0.1:0",
        "http://127.0.0.1:65536",
        "http://127.0.0.1%2f@excluded.invalid",
        "http://localhost\\excluded.invalid",
        "https://supportbridge-agentathon.vercel.app//",
        " http://localhost:8000",
    ],
)
async def test_unapproved_configuration_never_makes_request(
    origin, monkeypatch, mock_checkout
):
    monkeypatch.setenv("SANDBOX_API_BASE_URL", origin)
    requests = mock_checkout(lambda r: pytest.fail("Invalid origin reached HTTP"))
    with pytest.raises(_config.ConfigurationError) as error:
        await tools.run_checkout_quote("v1.0", 10000, 0)
    assert "secret" not in str(error.value) and requests == []


@pytest.mark.parametrize(
    "origin",
    [
        "http://localhost:8001",
        "http://127.0.0.1:8000/",
        "http://localhost",
        "https://supportbridge-agentathon.vercel.app/",
    ],
)
async def test_approved_origin_is_used_without_switching(
    origin, monkeypatch, mock_checkout
):
    monkeypatch.setenv("SANDBOX_API_BASE_URL", origin)
    requests = mock_checkout(lambda r: httpx.Response(503))
    result = await tools.run_checkout_quote("v1.0", 11000, 15)
    assert (
        len(requests) == 1
        and str(requests[0].url) == origin.rstrip("/") + tools.QUOTE_PATH
    )
    assert result.http_status == 503 and result.response is None


@pytest.mark.parametrize(
    "status,code",
    [
        (401, "http_error"),
        (422, "http_error"),
        (500, "http_error"),
        (429, "rate_limited"),
        (307, "redirect_denied"),
    ],
)
async def test_http_failure_and_redirect_are_not_quotes(status, code, mock_checkout):
    requests = mock_checkout(
        lambda r: httpx.Response(
            status, headers={"Location": "https://excluded.invalid"}, text="PRIVATE"
        )
    )
    result = await tools.run_checkout_quote("v1.0", 11000, 15)
    assert result.status == "http_error" and result.error.code == code
    assert result.http_status == status and result.response is None
    assert len(requests) == 1 and "PRIVATE" not in result.model_dump_json()


@pytest.mark.parametrize(
    "exception,code",
    [
        (httpx.ConnectTimeout, "timeout"),
        (httpx.ReadTimeout, "timeout"),
        (httpx.ConnectError, "environment_unavailable"),
    ],
)
async def test_network_failure_preserves_unavailability(exception, code, mock_checkout):
    def handler(request):
        raise exception("PRIVATE", request=request)

    mock_checkout(handler)
    result = await tools.run_checkout_quote("v1.0", 11000, 15)
    assert result.status == "environment_unavailable" and result.error.code == code
    assert result.http_status is None and result.response is None
    assert "PRIVATE" not in result.model_dump_json()


@pytest.mark.parametrize(
    "damage",
    [
        "json",
        "missing",
        "extra",
        "string_amount",
        "float_amount",
        "echo",
        "release",
    ],
)
async def test_malformed_or_wrong_identity_is_not_a_quote(damage, mock_checkout):
    body = quote_body()
    if damage == "missing":
        del body["total_cents"]
    elif damage == "extra":
        body["diagnosis"] = "PRIVATE"
    elif damage == "string_amount":
        body["total_cents"] = "9350"
    elif damage == "float_amount":
        body["total_cents"] = 9350.0
    elif damage == "echo":
        body["subtotal_cents"] = 9999
    elif damage == "release":
        body["release"] = "v1.1"
    mock_checkout(
        lambda r: httpx.Response(
            200, content=b"{" if damage == "json" else json.dumps(body).encode()
        )
    )
    result = await tools.run_checkout_quote("v1.0", 11000, 15)
    assert result.status == "invalid_response" and result.response is None
    assert result.http_status == 200 and result.error.code == "invalid_response"


async def test_large_response_is_bounded(mock_checkout):
    mock_checkout(
        lambda r: httpx.Response(200, content=b"x" * (_http.MAX_RESPONSE_BYTES + 1))
    )
    result = await tools.run_checkout_quote("v1.0", 11000, 15)
    assert result.error.code == "response_too_large"


async def test_total_timeout_covers_slow_stream(monkeypatch):
    class SlowStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            await asyncio.sleep(0.05)
            yield b"{}"

    monkeypatch.setattr(_http, "TOTAL_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setattr(
        _http,
        "_client",
        lambda: httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda r: httpx.Response(200, stream=SlowStream())
            )
        ),
    )
    result = await tools.run_checkout_quote("v1.0", 11000, 15)
    assert result.error.code == "timeout" and result.http_status == 200


@pytest.mark.parametrize("decision", [True, False, "unavailable"])
async def test_host_budget_reservation_precedes_http(decision, mock_checkout):
    calls = []

    async def reserve(maximum):
        calls.append(maximum)
        if decision == "unavailable":
            raise RuntimeError("PRIVATE_BUDGET_ERROR")
        return decision

    requests = mock_checkout(lambda r: httpx.Response(200, json=quote_body()))
    result = await tools.run_checkout_quote(
        "v1.0", 11000, 15, reserve_experiment=reserve
    )
    assert calls == [8]
    assert len(requests) == (1 if decision is True else 0)
    assert result.status == ("success" if decision is True else "blocked")
    assert "PRIVATE_BUDGET_ERROR" not in result.model_dump_json()


async def test_tools_do_not_import_oracle_and_work_in_both_import_modes(tmp_path):
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    for prefix, import_root in (("backend.tools", root), ("tools", root / "backend")):
        code = (
            "import sys; sys.path.insert(0, sys.argv[1]); "
            f"from {prefix}.github_read import list_checkout_releases; "
            f"from {prefix}.experiments import run_checkout_quote; "
            "assert len(list_checkout_releases().releases) == 2; "
            "assert not any('oracle' in name for name in sys.modules); "
            "assert not any(name.endswith(('v1_0', 'v1_1')) for name in sys.modules); "
            "print('TECHNICAL_IMPORT_OK')"
        )
        result = subprocess.run(
            [sys.executable, "-c", code, str(import_root)],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=True,
        )
        assert result.stdout.strip() == "TECHNICAL_IMPORT_OK"


async def test_host_can_reserve_eight_calls_and_deny_the_ninth(mock_checkout):
    # A test host reservation, not a runtime global counter or persistence store.
    reserved = 0

    async def reserve(maximum):
        nonlocal reserved
        if reserved >= maximum:
            return False
        reserved += 1
        return True

    requests = mock_checkout(lambda r: httpx.Response(200, json=quote_body()))
    results = [
        await tools.run_checkout_quote("v1.0", 11000, 15, reserve_experiment=reserve)
        for _ in range(9)
    ]
    assert len(requests) == 8
    assert all(result.status == "success" for result in results[:8])
    assert results[8].error.code == "budget_exhausted"
