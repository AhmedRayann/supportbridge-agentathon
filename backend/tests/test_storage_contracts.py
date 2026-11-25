"""Database-independent contracts and adapter tests, not PostgreSQL durability proof."""

import inspect
import json
import secrets
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import httpx
import pytest
from pydantic import ValidationError

from backend.main import app
from backend.storage import models as m
from backend.storage.database import (
    Database,
    SessionDenied,
    Settings,
    StorageConfigurationError,
    StorageUnavailable,
)
from backend.storage.execution import (
    ExecutionContext,
    RecordedToolResult,
    evidence_records,
)
from backend.storage.repository import Store, credential_hash
from backend.storage.router import get_store
from backend.storage.safety import canonical_json, content_hash
from backend.tools import _http, support_corpus


def lease():
    return m.Lease(
        investigation_id=uuid4(),
        stage="reproduction",
        operation_key="stage_key_0001",
        lease_token=uuid4(),
        fence=1,
        expires_at=datetime.now(UTC) + timedelta(seconds=60),
        status="running",
    )


def test_canonical_hash_is_stable_and_exact():
    assert (
        canonical_json({"b": [1, True, None], "a": "USD"})
        == '{"a":"USD","b":[1,true,null]}'
    )
    assert content_hash({"b": 2, "a": 1}) == content_hash({"a": 1, "b": 2})
    assert content_hash({"total_cents": 9350}) != content_hash({"total_cents": 10100})


@pytest.mark.parametrize(
    "payload",
    [
        {"api_key": "hidden"},
        {"nested": {"Authorization": "hidden"}},
        {"chain_of_thought": "private"},
        {"analysis": "private"},
        {"message": "postgresql://user:secret@host/database"},
        {"message": "Bearer secretcredential"},
        {"message": secrets.token_urlsafe(32)},
        {"value": float("nan")},
        {"value": float("inf")},
        {"value": object()},
    ],
)
def test_private_or_non_json_payloads_are_denied(payload):
    with pytest.raises(ValueError):
        canonical_json(payload)


def test_env_secret_bytes_depth_and_size_are_bounded(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-only-credential-sentinel")
    with pytest.raises(ValueError):
        canonical_json({"message": "leaked test-only-credential-sentinel"})
    with pytest.raises(ValueError):
        canonical_json({"message": "x" * 100}, maximum=30)
    value = {}
    for _ in range(32):
        value = {"nested": value}
    with pytest.raises(ValueError):
        canonical_json(value)


@pytest.mark.parametrize(
    "token", [None, "", "client-session-id", "x" * 42, "x" * 44, "../"]
)
def test_session_credentials_reject_client_ids(token):
    with pytest.raises(SessionDenied):
        credential_hash(token)


def test_credential_hash_does_not_store_the_credential():
    token = secrets.token_urlsafe(32)
    assert len(token) == 43 and len(credential_hash(token)) == 64
    assert token != credential_hash(token)


@pytest.mark.parametrize(
    "name,value",
    [
        ("DATABASE_URL", ""),
        ("DATABASE_URL", "sqlite:///local.db"),
        ("PUBLIC_APP_ORIGIN", "https://user:secret@example.invalid"),
        ("MAX_EXPERIMENTS_PER_RUN", "9"),
        ("MAX_MODEL_CALLS_PER_RUN", "21"),
        ("STAGE_LEASE_SECONDS", "0"),
        ("AI_RUNS_ENABLED", "yes"),
    ],
)
def test_bad_environment_is_sanitized(name, value, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:secret@127.0.0.1/example")
    monkeypatch.setenv(name, value)
    with pytest.raises(StorageConfigurationError) as error:
        Settings.from_env()
    assert "secret" not in str(error.value)


def test_settings_defaults_are_safe(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:secret@127.0.0.1/example")
    monkeypatch.delenv("AI_RUNS_ENABLED", raising=False)
    settings = Settings.from_env()
    assert (
        not settings.ai_enabled
        and settings.experiment_limit == 8
        and settings.model_limit == 10
    )
    assert "secret" not in repr(settings)


@pytest.mark.parametrize("bad", [True, "11000", 1.1])
def test_state_counters_are_strict(bad):
    with pytest.raises(ValidationError):
        m.StageSummary(evidence_ids=(bad,))


def test_lifecycle_is_separate_from_findings():
    assert (
        m.Findings(behavior="insufficient_evidence", cause="unknown").cause == "unknown"
    )
    with pytest.raises(ValidationError):
        m.Findings(behavior="completed", cause="verified")
    with pytest.raises(ValidationError):
        m.WorkflowState(chain_of_thought="private")


def test_real_database_unavailability_fails_without_memory_fallback():
    db = Database(Settings("postgresql://unused:private-password@127.0.0.1:1/unused"))
    with pytest.raises(StorageUnavailable) as error:
        Store(db).create_session()
    assert "private-password" not in str(error.value)


def test_packaged_policy_sections_and_payment_provenance():
    execution_id = uuid4()
    policy = support_corpus.get_policy_document("POL-100").model_dump(mode="json")
    records = evidence_records("get_policy_document", policy, execution_id)
    assert records[0]["payload"] == policy
    sections = [r for r in records if r["category"] == "policy_section"]
    assert [r["source_id"] for r in sections] == [
        "POL-100-S1",
        "POL-100-S2",
        "POL-100-S3",
    ]
    assert sections[0]["payload"]["document"]["approval_status"] == "approved"
    ledger = support_corpus.get_order_payment_events("ORD-4101").model_dump(mode="json")
    events = evidence_records("get_order_payment_events", ledger, execution_id)
    assert [r["source_id"] for r in events[1:]] == ["EVT-4101-01", "EVT-4101-02"]
    assert events[2]["payload"]["event_type"] == "capture"


@pytest.fixture
def recording_spy():
    # A host-boundary spy only: no claims about database persistence/concurrency.
    store = MagicMock(spec=Store)
    store.begin_tool.return_value = (SimpleNamespace(id=uuid4()), True)
    store.finish_tool.return_value = (uuid4(),)
    return store


@pytest.mark.anyio
async def test_registry_has_only_bounded_public_arguments(recording_spy):
    registry = ExecutionContext(recording_spy, uuid4(), lease()).tools_for(
        "tool_call_0001"
    )
    assert set(registry) == set(support_corpus.__all__) | {
        "list_checkout_releases",
        "get_checkout_source",
        "get_checkout_history",
        "compare_checkout_sources",
        "run_checkout_quote",
    }
    quote = registry["run_checkout_quote"]
    assert (
        inspect.signature(registry["get_support_ticket"]).return_annotation
        is RecordedToolResult
    )
    assert list(inspect.signature(quote).parameters) == [
        "release",
        "subtotal_cents",
        "discount_percent",
    ]
    with pytest.raises(ValidationError):
        await quote("v1.0", 11000, 15, reserve_experiment=None)
    with pytest.raises(ValidationError):
        await quote("v1.0", 11000, 15, model_call_limit=20)
    with pytest.raises(ValidationError):
        m.CreateInvestigation(complaint="Synthetic complaint", model_call_limit=20)
    with pytest.raises(KeyError):
        registry["record_assertion"]


@pytest.mark.anyio
async def test_actual_corpus_tool_is_recorded_exactly(recording_spy):
    context = ExecutionContext(recording_spy, uuid4(), lease())
    result = await context.tools_for("ticket_call_0001")["get_support_ticket"](
        "TKT-1001"
    )
    expected = support_corpus.get_support_ticket("TKT-1001").model_dump(mode="json")
    assert result.result == expected and result.evidence_ids
    args = recording_spy.finish_tool.call_args.args
    assert args[3] == expected
    assert any(
        r["category"] == "support_ticket" and r["source_id"] == "TKT-1001"
        for r in args[4]
    )


@pytest.mark.anyio
async def test_failed_reservation_cannot_make_http_request(recording_spy, monkeypatch):
    monkeypatch.setenv("SANDBOX_API_BASE_URL", "http://127.0.0.1:8000")
    recording_spy.reserve.side_effect = StorageUnavailable(
        "Private database diagnostic"
    )
    calls = []
    monkeypatch.setattr(
        _http,
        "_client",
        lambda: httpx.AsyncClient(
            transport=httpx.MockTransport(lambda r: calls.append(r))
        ),
    )
    result = await ExecutionContext(recording_spy, uuid4(), lease()).tools_for(
        "quote_call_0001"
    )["run_checkout_quote"]("v1.0", 11000, 15)
    assert calls == [] and result.result["status"] == "blocked"
    assert result.result["error"]["code"] == "budget_unavailable"
    assert "Private" not in json.dumps(result.result)


@pytest.mark.anyio
async def test_db_failure_before_tool_dispatch_stops_execution(recording_spy):
    recording_spy.begin_tool.side_effect = StorageUnavailable("Store unavailable")
    with pytest.raises(StorageUnavailable):
        await ExecutionContext(recording_spy, uuid4(), lease()).tools_for(
            "ticket_call_0002"
        )["get_support_ticket"]("TKT-1001")
    recording_spy.finish_tool.assert_not_called()


@pytest.mark.anyio
async def test_storage_missing_does_not_break_health_or_checkout(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        assert (await client.get("/health")).status_code == 200
        response = await client.post(
            "/svc/api/sandbox/quote",
            json={"release": "v1.0", "subtotal_cents": 11000, "discount_percent": 15},
        )
        assert response.json()["total_cents"] == 9350
        blocked = await client.post(
            "/svc/api/sessions",
            headers={"Origin": "https://supportbridge-agentathon.vercel.app"},
        )
        assert blocked.status_code == 503 and "DATABASE_URL" in blocked.json()["detail"]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "origin,secure",
    [
        ("http://localhost:3000", False),
        ("https://supportbridge-agentathon.vercel.app", True),
    ],
)
async def test_cookie_flags_origin_and_no_credential_response(origin, secure):
    store = MagicMock(spec=Store)
    store.settings = Settings("not-used", app_origin=origin)
    now = datetime.now(UTC)
    session = m.Session(id=uuid4(), created_at=now, expires_at=now + timedelta(hours=8))
    token = secrets.token_urlsafe(32)
    store.create_session.return_value = (session, token)
    app.dependency_overrides[get_store] = lambda: store
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url=origin
        ) as client:
            for headers in (
                {},
                {"Origin": "https://excluded.invalid"},
                {"Origin": origin, "Sec-Fetch-Site": "cross-site"},
            ):
                assert (
                    await client.post("/svc/api/sessions", headers=headers)
                ).status_code == 403
            response = await client.post(
                "/svc/api/sessions", headers={"Origin": origin}
            )
            cookie = response.headers["set-cookie"].lower()
            assert (
                "httponly" in cookie
                and "samesite=strict" in cookie
                and "max-age=28800" in cookie
            )
            assert ("; secure" in cookie) is secure
            assert (
                token not in response.text
                and response.headers["cache-control"] == "no-store"
            )
    finally:
        app.dependency_overrides.clear()


def test_no_fake_execution_or_approval_routes():
    paths = set(app.openapi()["paths"])
    assert not any(
        p.endswith(("/step", "/approve", "/reject", "/execute")) for p in paths
    )


def test_storage_imports_both_layouts_without_git_or_database(tmp_path):
    root = Path(__file__).resolve().parents[2]
    for prefix, path in (("backend.storage", root), ("storage", root / "backend")):
        source = (
            "import sys; sys.path.insert(0, sys.argv[1]); "
            f"import {prefix}.execution; import {prefix}.router; "
            "print('STORAGE_IMPORT_OK')"
        )
        result = subprocess.run(
            [sys.executable, "-c", source, str(path)],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=True,
        )
        assert result.stdout.strip() == "STORAGE_IMPORT_OK"


def test_hosted_postgres_requires_explicit_tls(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql://user:private@host.invalid/database"
    )
    with pytest.raises(StorageConfigurationError):
        Settings.from_env()
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://user:private@host.invalid/database?sslmode=require",
    )
    assert Settings.from_env().database_url.endswith("sslmode=require")


def test_unavailable_database_fails_closed_without_driver_details():
    database = Database(Settings("postgresql://user:private@127.0.0.1:1/unavailable"))
    with pytest.raises(StorageUnavailable) as error:
        with database.transaction():
            pytest.fail("Unavailable database yielded a connection")
    assert "private" not in str(error.value) and "127.0.0.1" not in str(error.value)


@pytest.mark.parametrize("limit", [1, 10, 11, 16, 20])
def test_model_limit_configuration_accepts_only_the_host_selected_range(
    monkeypatch, limit
):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:private@127.0.0.1/example")
    monkeypatch.setenv("MAX_MODEL_CALLS_PER_RUN", str(limit))
    assert Settings.from_env().model_limit == limit


@pytest.mark.parametrize("limit", ["0", "21", "100", "10.5", "true"])
def test_invalid_model_limits_fail_configuration(monkeypatch, limit):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:private@127.0.0.1/example")
    monkeypatch.setenv("MAX_MODEL_CALLS_PER_RUN", limit)
    with pytest.raises(StorageConfigurationError):
        Settings.from_env()


@pytest.mark.parametrize("capacity", [1, 4, 12, 100])
def test_global_execution_capacity_is_configurable_and_bounded(monkeypatch, capacity):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:private@127.0.0.1/example")
    monkeypatch.setenv("MAX_GLOBAL_ACTIVE_RUNS", str(capacity))
    assert Settings.from_env().global_active_limit == capacity


@pytest.mark.parametrize("capacity", ["0", "101"])
def test_invalid_execution_capacity_is_rejected(monkeypatch, capacity):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:private@127.0.0.1/example")
    monkeypatch.setenv("MAX_GLOBAL_ACTIVE_RUNS", capacity)
    with pytest.raises(StorageConfigurationError):
        Settings.from_env()


@pytest.mark.anyio
@pytest.mark.parametrize(
    "origin", ["http://localhost:3000", "https://supportbridge-agentathon.vercel.app"]
)
async def test_rejected_session_cookie_rotates_with_original_security_flags(origin):
    store = MagicMock(spec=Store)
    store.settings = Settings("unused", app_origin=origin)
    store.resolve_session.side_effect = SessionDenied(
        "A valid anonymous session is required"
    )
    now = datetime.now(UTC)
    fresh = m.Session(id=uuid4(), created_at=now, expires_at=now + timedelta(hours=8))
    credential = secrets.token_urlsafe(32)
    store.create_session.return_value = (fresh, credential)
    app.dependency_overrides[get_store] = lambda: store
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url=origin
        ) as client:
            response = await client.post(
                "/svc/api/sessions",
                headers={"Origin": origin, "Cookie": "sb_session=rejected"},
            )
        assert response.status_code == 200 and response.json()["id"] == str(fresh.id)
        cookie = response.headers["set-cookie"].lower()
        assert "httponly" in cookie and "samesite=strict" in cookie
        assert ("; secure" in cookie) == origin.startswith("https://")
        assert "max-age=28800" in cookie and credential not in response.text
        assert response.headers["cache-control"] == "no-store"
        store.create_session.assert_called_once()
    finally:
        app.dependency_overrides.clear()


@pytest.mark.anyio
@pytest.mark.parametrize("failure", [StorageUnavailable, StorageConfigurationError])
async def test_session_infrastructure_failure_does_not_issue_a_new_credential(failure):
    store = MagicMock(spec=Store)
    store.settings = Settings("unused", app_origin="http://localhost:3000")
    store.resolve_session.side_effect = failure("Investigation storage is unavailable")
    app.dependency_overrides[get_store] = lambda: store
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://localhost:3000"
        ) as client:
            response = await client.post(
                "/svc/api/sessions",
                headers={
                    "Origin": store.settings.app_origin,
                    "Cookie": "sb_session=existing",
                },
            )
        assert response.status_code == 503 and "set-cookie" not in response.headers
        store.create_session.assert_not_called()
    finally:
        app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_session_creation_failure_remains_an_infrastructure_error():
    store = MagicMock(spec=Store)
    store.settings = Settings("unused", app_origin="http://localhost:3000")
    store.resolve_session.side_effect = SessionDenied("Rejected credential")
    store.create_session.side_effect = StorageUnavailable(
        "Investigation storage is unavailable"
    )
    app.dependency_overrides[get_store] = lambda: store
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://localhost:3000"
        ) as client:
            response = await client.post(
                "/svc/api/sessions",
                headers={
                    "Origin": store.settings.app_origin,
                    "Cookie": "sb_session=rejected",
                },
            )
        assert response.status_code == 503 and "set-cookie" not in response.headers
    finally:
        app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_session_rotation_still_requires_same_origin():
    store = MagicMock(spec=Store)
    store.settings = Settings("unused", app_origin="http://localhost:3000")
    app.dependency_overrides[get_store] = lambda: store
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://localhost:3000"
        ) as client:
            response = await client.post(
                "/svc/api/sessions",
                headers={
                    "Origin": "https://excluded.invalid",
                    "Cookie": "sb_session=rejected",
                },
            )
        assert response.status_code == 403
        store.resolve_session.assert_not_called()
        store.create_session.assert_not_called()
    finally:
        app.dependency_overrides.clear()
