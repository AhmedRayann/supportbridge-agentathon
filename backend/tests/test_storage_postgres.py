"""Real PostgreSQL integration tests. No SQLite or in-memory substitute."""

import asyncio
import hashlib
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import httpx
import psycopg
import pytest
from psycopg import sql
from pydantic import ValidationError

from backend.main import app
from backend.storage import models as m
from backend.storage.database import (
    Conflict,
    Database,
    ExecutionDisabled,
    LimitReached,
    NotFound,
    SessionDenied,
    Settings,
    StorageError,
    StorageUnavailable,
)
from backend.storage.execution import ExecutionContext
from backend.storage.migrate import migrate
from backend.storage.repository import Store
from backend.storage.router import get_store
from backend.storage.safety import content_hash
from backend.tools import _http

pytestmark = pytest.mark.postgresql


@pytest.fixture
def store(request):
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to a disposable PostgreSQL database")
    schema = "sb_test_" + uuid4().hex
    settings = Settings(
        url,
        app_origin="http://localhost:3000",
        ai_enabled=True,
        global_active_limit=100,
        global_daily_limit=10000,
        session_daily_limit=100,
    )
    with psycopg.connect(url, connect_timeout=3, prepare_threshold=None) as c:
        c.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    database = Database(settings, schema=schema)
    try:
        if getattr(request, "param", None) == "001_only":
            source = (
                (Path(__file__).parents[1] / "storage/migrations/001_initial.sql")
                .read_bytes()
                .replace(b"\r\n", b"\n")
            )
            with database.transaction(migration=True) as connection:
                connection.execute("""CREATE TABLE sb_schema_migrations (
                    version text PRIMARY KEY, checksum text NOT NULL,
                    applied_at timestamptz NOT NULL DEFAULT clock_timestamp())""")
                connection.execute(source.decode(), prepare=False)
                connection.execute(
                    "INSERT INTO sb_schema_migrations(version,checksum) VALUES (%s,%s)",
                    ("001_initial", hashlib.sha256(source).hexdigest()),
                )
        else:
            migrate(database)
        yield Store(database)
    finally:
        assert schema.startswith("sb_test_") and len(schema) == 40
        with psycopg.connect(url, connect_timeout=3, prepare_threshold=None) as c:
            c.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


def new_investigation(store, *, key="create_call_0001"):
    session, credential = store.create_session()
    inv = store.create_investigation(
        session.id,
        m.CreateInvestigation(
            complaint="Synthetic checkout amount question", ticket_id="TKT-1001"
        ),
        key,
    )
    return session, credential, inv


def reproduction(store):
    session, credential, inv = new_investigation(store)
    for stage in ("support", "repository"):
        lease = store.acquire_stage(session.id, inv.id, stage, f"stage_{stage}_0001")
        store.complete_stage(session.id, lease, m.StageSummary())
    lease = store.acquire_stage(
        session.id, inv.id, "reproduction", "stage_reproduce_0001"
    )
    return session, credential, inv, lease


def test_migrations_are_idempotent_and_survive_connections(store):
    migrate(store.database)
    session, credential, inv = new_investigation(store)
    separate = Store(Database(store.settings, schema=store.database.schema))
    assert separate.resolve_session(credential) == session
    assert separate.get_investigation(session.id, inv.id).complaint == inv.complaint
    assert separate.get_investigation(session.id, inv.id).findings is None


def test_creation_is_idempotent_and_conflicting_inputs_are_rejected(store):
    session, _, inv = new_investigation(store)
    same = store.create_investigation(
        session.id,
        m.CreateInvestigation(complaint=inv.complaint, ticket_id=inv.ticket_id),
        "create_call_0001",
    )
    assert same.id == inv.id
    with pytest.raises(Conflict):
        store.create_investigation(
            session.id, m.CreateInvestigation(complaint="Different"), "create_call_0001"
        )


def test_session_isolation_and_expiry(store):
    session, credential, inv = new_investigation(store)
    other, _ = store.create_session()
    with pytest.raises(NotFound):
        store.get_investigation(other.id, inv.id)
    with store.database.transaction() as c:
        c.execute(
            """UPDATE sb_sessions SET expires_at=clock_timestamp()-interval '1
            second' WHERE id=%s""",
            (session.id,),
        )
    with pytest.raises(SessionDenied):
        store.resolve_session(credential)
    with pytest.raises(NotFound):
        store.get_investigation(session.id, inv.id)


def test_concurrent_creation_enforces_one_active_session_run(store):
    session, _ = store.create_session()

    def create(n):
        try:
            return store.create_investigation(
                session.id,
                m.CreateInvestigation(complaint="Concurrent test"),
                f"create_race_{n:04}",
            ).id
        except LimitReached:
            return None

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(create, range(12)))
    assert sum(result is not None for result in results) == 1


@pytest.mark.parametrize("capacity", [1, 6])
def test_global_active_limit_is_shared_across_stores(store, capacity):
    limited = Store(
        Database(
            replace(store.settings, global_active_limit=capacity),
            schema=store.database.schema,
        )
    )
    for _ in range(capacity):
        new_investigation(limited)
    with pytest.raises(LimitReached):
        new_investigation(
            Store(Database(limited.settings, schema=store.database.schema))
        )


def test_daily_limits_remain_after_terminal_status(store):
    limited = Store(
        Database(
            replace(store.settings, session_daily_limit=1), schema=store.database.schema
        )
    )
    session, _, inv = new_investigation(limited)
    lease = limited.acquire_stage(session.id, inv.id, "support", "stage_support_0001")
    limited.fail_stage(session.id, lease)
    with pytest.raises(LimitReached):
        limited.create_investigation(
            session.id, m.CreateInvestigation(complaint="New"), "create_again_0001"
        )


def test_parallel_stages_and_completion_do_not_lose_state(store):
    session, _, inv = new_investigation(store)
    leases = [
        store.acquire_stage(session.id, inv.id, s, f"stage_{s}_0001")
        for s in ("support", "repository")
    ]
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(
            pool.map(
                lambda lease: store.complete_stage(
                    session.id,
                    lease,
                    m.StageSummary(explanation="Host test stage completion"),
                ),
                leases,
            )
        )
    current = store.get_investigation(session.id, inv.id)
    assert set(current.state.stage_outputs) == {"support", "repository"}
    assert len(current.stages) == 2
    assert all(s.status == "completed" for s in current.stages)


def test_leases_reject_duplicates_bad_transitions_and_stale_commits(store):
    session, _, inv = new_investigation(store)
    with pytest.raises(Conflict):
        store.acquire_stage(session.id, inv.id, "verification", "verify_stage_0001")
    old = store.acquire_stage(session.id, inv.id, "support", "support_stage_0001")
    with pytest.raises(Conflict):
        store.acquire_stage(session.id, inv.id, "support", "support_stage_0001")
    with store.database.transaction() as c:
        c.execute(
            """UPDATE sb_stage_executions SET
            expires_at=clock_timestamp()-interval '1 second' WHERE
            investigation_id=%s""",
            (inv.id,),
        )
    newer = store.acquire_stage(session.id, inv.id, "support", "support_stage_0001")
    assert newer.fence == old.fence + 1 and newer.lease_token != old.lease_token
    with pytest.raises(Conflict):
        store.complete_stage(session.id, old, m.StageSummary())
    store.complete_stage(session.id, newer, m.StageSummary())
    assert (
        store.acquire_stage(session.id, inv.id, "support", "support_stage_0001").status
        == "completed"
    )
    store.complete_stage(session.id, newer, m.StageSummary())


def test_lease_renewal_and_kill_switch(store):
    session, _, inv = new_investigation(store)
    lease = store.acquire_stage(session.id, inv.id, "support", "support_stage_0001")
    assert store.renew_stage(session.id, lease).expires_at >= lease.expires_at
    disabled = Store(
        Database(
            replace(store.settings, ai_enabled=False), schema=store.database.schema
        )
    )
    with pytest.raises(ExecutionDisabled):
        disabled.begin_tool(
            session.id,
            lease,
            "get_support_ticket",
            {"ticket_id": "TKT-1001"},
            "tool_disabled_0001",
        )


def test_real_corpus_execution_is_persisted_and_idempotent(store):
    session, _, inv = new_investigation(store)
    lease = store.acquire_stage(session.id, inv.id, "support", "support_stage_0001")
    context = ExecutionContext(store, session.id, lease)

    async def execute():
        tool = context.tools_for("ticket_lookup_0001")["get_support_ticket"]
        first, second = await tool("TKT-1001"), await tool("TKT-1001")
        return first, second

    first, second = asyncio.run(execute())
    assert second.replayed and first.execution_id == second.execution_id
    assert first.evidence_ids == second.evidence_ids
    records = [
        store.get_evidence(session.id, inv.id, eid) for eid in first.evidence_ids
    ]
    ticket = next(e for e in records if e.category == "support_ticket")
    assert ticket.source_id == "TKT-1001" and ticket.payload == first.result["ticket"]
    assert ticket.content_hash == content_hash(ticket.payload)
    assert ticket.trust == "untrusted_data"
    assert store.validate_citations(session.id, inv.id, first.evidence_ids)
    events = store.list_events(session.id, inv.id).events
    types = [event.event_type for event in events]
    assert types[:5] == [
        "investigation_created",
        "stage_started",
        "tool_selected",
        "tool_arguments",
        "tool_result",
    ]
    assert [e.sequence for e in events] == list(range(1, len(events) + 1))


def test_citations_and_evidence_cannot_cross_sessions_or_be_fabricated(store):
    session, _, inv = new_investigation(store)
    lease = store.acquire_stage(session.id, inv.id, "support", "support_stage_0001")
    result = asyncio.run(
        ExecutionContext(store, session.id, lease).tools_for("ticket_lookup_0001")[
            "get_support_ticket"
        ]("TKT-1001")
    )
    other, _ = store.create_session()
    with pytest.raises(NotFound):
        store.get_evidence(other.id, inv.id, result.evidence_ids[0])
    with pytest.raises(NotFound):
        store.validate_citations(session.id, inv.id, (uuid4(),))
    other_inv = store.create_investigation(
        other.id, m.CreateInvestigation(complaint="Other"), "other_create_0001"
    )
    with pytest.raises(NotFound):
        store.validate_citations(other.id, other_inv.id, result.evidence_ids)


@pytest.mark.parametrize("table", ["sb_evidence", "sb_events"])
def test_append_only_records_reject_direct_sql_edits(store, table):
    session, _, inv = new_investigation(store)
    lease = store.acquire_stage(session.id, inv.id, "support", "support_stage_0001")
    asyncio.run(
        ExecutionContext(store, session.id, lease).tools_for("ticket_lookup_0001")[
            "get_support_ticket"
        ]("TKT-1001")
    )
    with pytest.raises(Exception):
        with store.database.transaction() as c:
            c.execute(
                sql.SQL("DELETE FROM {} WHERE investigation_id=%s").format(
                    sql.Identifier(table)
                ),
                (inv.id,),
            )
    assert store.list_events(session.id, inv.id).events


def test_concurrent_event_append_has_no_duplicate_sequences(store):
    session, _, inv = new_investigation(store)
    lease = store.acquire_stage(session.id, inv.id, "support", "support_stage_0001")
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(
            pool.map(
                lambda n: store.append_event(
                    session.id,
                    lease,
                    "hypothesis_proposed",
                    {"explanation": f"Test host observation {n}"},
                ),
                range(20),
            )
        )
    events = store.list_events(session.id, inv.id, limit=100).events
    assert [e.sequence for e in events] == list(range(1, 23))
    page = store.list_events(session.id, inv.id, limit=5)
    assert len(page.events) == 5 and page.next_after == 5


def test_concurrent_experiment_reservations_cannot_overspend(store):
    session, _, inv, lease = reproduction(store)

    def reserve(n):
        execution, _ = store.begin_tool(
            session.id,
            lease,
            "run_checkout_quote",
            {"release": "v1.0", "subtotal_cents": 11000, "discount_percent": 15},
            f"quote_race_{n:04}",
        )
        return store.reserve(
            session.id,
            lease,
            "experiment",
            f"quote_race_{n:04}",
            execution_id=execution.id,
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        reservations = list(pool.map(reserve, range(12)))
    successful = [r for r in reservations if r is not None]
    assert len(successful) == 8 and sorted(r.ordinal for r in successful) == list(
        range(1, 9)
    )
    assert store.get_investigation(session.id, inv.id).experiment_count == 8


def test_failed_http_attempts_consume_the_shared_reproduction_verifier_budget(
    store, monkeypatch
):
    session, _, inv, lease = reproduction(store)
    monkeypatch.setenv("SANDBOX_API_BASE_URL", "http://127.0.0.1:8000")
    calls = []

    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout("test timeout", request=request)

    monkeypatch.setattr(
        _http,
        "_client",
        lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    async def execute():
        context = ExecutionContext(store, session.id, lease)
        for n in range(8):
            result = await context.tools_for(f"failed_quote_{n:04}")[
                "run_checkout_quote"
            ]("v1.1", 11000, 15)
            assert result.result["status"] == "environment_unavailable"

    asyncio.run(execute())
    store.complete_stage(session.id, lease, m.StageSummary())
    verifier = store.acquire_stage(
        session.id, inv.id, "verification", "verify_stage_0001"
    )
    result = asyncio.run(
        ExecutionContext(store, session.id, verifier).tools_for("verifier_quote_0001")[
            "run_checkout_quote"
        ]("v1.0", 12500, 20)
    )
    assert result.result["error"]["code"] == "budget_exhausted" and len(calls) == 8
    assert store.get_investigation(session.id, inv.id).experiment_count == 8
    with store.database.transaction() as c:
        assert (
            c.execute(
                """SELECT count(*) AS n FROM sb_usage_reservations WHERE
                kind='experiment'"""
            ).fetchone()["n"]
            == 8
        )


@pytest.mark.parametrize("limit", [10, 16, 20])
def test_model_usage_reservations_are_atomic_and_unknown_metrics_remain_null(
    store, limit
):
    store = Store(
        Database(
            replace(store.settings, model_limit=limit), schema=store.database.schema
        )
    )
    session, _, inv = new_investigation(store)
    lease = store.acquire_stage(session.id, inv.id, "support", "support_stage_0001")

    def reserve(n):
        return store.reserve(
            session.id,
            lease,
            "model",
            f"model_call_{n:04}",
            provider="test-provider",
            model="test-model",
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        records = list(pool.map(reserve, range(limit + 4)))
    assert sum(r is not None for r in records) == limit
    record = next(r for r in records if r)
    completed = store.record_usage(session.id, lease, record.id, outcome="unknown")
    assert completed.input_tokens is None and completed.output_tokens is None
    assert store.get_investigation(session.id, inv.id).model_call_count == limit


def review_ready(store, monkeypatch):
    session, _, inv, reproduction_lease = reproduction(store)
    store.complete_stage(session.id, reproduction_lease, m.StageSummary())
    verifier = store.acquire_stage(
        session.id, inv.id, "verification", "verify_stage_0001"
    )
    monkeypatch.setenv("SANDBOX_API_BASE_URL", "http://127.0.0.1:8000")
    monkeypatch.setattr(
        _http,
        "_client",
        lambda: httpx.AsyncClient(transport=httpx.ASGITransport(app=app)),
    )
    observed = asyncio.run(
        ExecutionContext(store, session.id, verifier).tools_for("verifier_quote_0001")[
            "run_checkout_quote"
        ]("v1.0", 12500, 20)
    )
    # Explicit host fixture assertion for storage eligibility, not a real verifier.
    assertion = store.record_assertion(
        session.id,
        verifier,
        m.VerifiedAssertion(
            independently_verified=True,
            statement="Test-only host assertion fixture",
            evidence_ids=observed.evidence_ids,
        ),
    )
    draft = m.EscalationDraft(
        title="Test-only review fixture",
        description="Storage eligibility test; no agent diagnosis",
        evidence_ids=observed.evidence_ids,
    )
    store.prepare_review(
        session.id,
        verifier,
        draft,
        m.Findings(behavior="verified_regression", cause="unknown"),
        assertion.id,
    )
    return session, inv


@pytest.mark.parametrize("decision", ["approved", "rejected"])
def test_human_decision_is_final_and_approval_creates_at_most_one_escalation(
    store, monkeypatch, decision
):
    session, inv = review_ready(store, monkeypatch)
    first = store.decide_review(session.id, inv.id, decision, "Human fixture decision")
    second = store.decide_review(session.id, inv.id, decision, "Human fixture decision")
    assert first == second
    assert (first.escalation_id is not None) == (decision == "approved")
    with store.database.transaction() as c:
        assert c.execute("SELECT count(*) AS n FROM sb_escalations").fetchone()[
            "n"
        ] == (1 if decision == "approved" else 0)
    with pytest.raises(Conflict):
        store.decide_review(
            session.id, inv.id, "rejected" if decision == "approved" else "approved"
        )
    other, _ = store.create_session()
    with pytest.raises(NotFound):
        store.decide_review(other.id, inv.id, decision)


def test_unverified_pending_investigations_cannot_be_escalated(store):
    session, _, inv = new_investigation(store)
    with pytest.raises(Conflict):
        store.decide_review(session.id, inv.id, "approved")


def test_assertion_cannot_use_unreplayed_reproduction_evidence(store, monkeypatch):
    session, _, inv, lease = reproduction(store)
    monkeypatch.setenv("SANDBOX_API_BASE_URL", "http://127.0.0.1:8000")
    monkeypatch.setattr(
        _http,
        "_client",
        lambda: httpx.AsyncClient(transport=httpx.ASGITransport(app=app)),
    )
    result = asyncio.run(
        ExecutionContext(store, session.id, lease).tools_for("initial_quote_0001")[
            "run_checkout_quote"
        ]("v1.0", 12500, 20)
    )
    store.complete_stage(session.id, lease, m.StageSummary())
    verifier = store.acquire_stage(
        session.id, inv.id, "verification", "verify_stage_0001"
    )
    with pytest.raises(Conflict):
        store.record_assertion(
            session.id,
            verifier,
            m.VerifiedAssertion(
                independently_verified=True,
                statement="Test un-replayed evidence",
                evidence_ids=result.evidence_ids,
            ),
        )


def test_concurrent_duplicate_approvals_save_only_one_escalation(store, monkeypatch):
    session, inv = review_ready(store, monkeypatch)
    with ThreadPoolExecutor(max_workers=4) as pool:
        decisions = list(
            pool.map(
                lambda _: store.decide_review(session.id, inv.id, "approved"), range(4)
            )
        )
    assert len({item.escalation_id for item in decisions}) == 1
    with store.database.transaction() as c:
        assert (
            c.execute("SELECT count(*) AS n FROM sb_escalations").fetchone()["n"] == 1
        )


def test_completed_lifecycle_does_not_invent_a_finding(store):
    session, _, inv, lease = reproduction(store)
    store.complete_stage(session.id, lease, m.StageSummary())
    verifier = store.acquire_stage(
        session.id, inv.id, "verification", "verify_stage_0001"
    )
    result = store.finish_investigation(session.id, verifier, m.StageSummary())
    assert result.status == "completed" and result.findings is None


def test_http_api_uses_cookie_ownership_and_no_public_execution_routes(store):
    app.dependency_overrides[get_store] = lambda: store

    async def requests():
        transport = httpx.ASGITransport(app=app)
        headers = {"Origin": "http://localhost:3000"}
        async with (
            httpx.AsyncClient(
                transport=transport, base_url="http://localhost:3000"
            ) as a,
            httpx.AsyncClient(
                transport=transport, base_url="http://localhost:3000"
            ) as b,
        ):
            assert (
                await a.post("/svc/api/sessions", headers=headers)
            ).status_code == 200
            assert (
                await b.post("/svc/api/sessions", headers=headers)
            ).status_code == 200
            created = await a.post(
                "/svc/api/investigations",
                headers={**headers, "Idempotency-Key": "create_http_0001"},
                json={"complaint": "Synthetic amount question"},
            )
            assert created.status_code == 201
            url = "/svc/api/investigations/" + created.json()["id"]
            assert (await a.get(url)).status_code == 200
            assert (await b.get(url)).status_code == 404
            assert (await b.get(url + "/events")).status_code == 404
            assert (await b.get(url + "/evidence/" + str(uuid4()))).status_code == 404
            assert (await a.get(url + "/events?limit=101")).status_code == 422
            assert (await a.post(url + "/step")).status_code in (404, 405)

    try:
        asyncio.run(requests())
    finally:
        app.dependency_overrides.clear()


def test_concurrent_stage_acquisition_has_only_one_winner(store):
    session, _, inv = new_investigation(store)

    def acquire(n):
        try:
            return store.acquire_stage(
                session.id, inv.id, "support", f"stage_race_{n:04}"
            )
        except Conflict:
            return None

    with ThreadPoolExecutor(max_workers=4) as pool:
        leases = list(pool.map(acquire, range(4)))
    assert sum(item is not None for item in leases) == 1


def test_stale_tool_cannot_commit_after_recovery_and_reservation_is_not_refunded(store):
    session, _, inv, old = reproduction(store)
    execution, _ = store.begin_tool(
        session.id,
        old,
        "run_checkout_quote",
        {"release": "v1.0", "subtotal_cents": 11000, "discount_percent": 15},
        "interrupted_call_0001",
    )
    assert store.reserve(
        session.id,
        old,
        "experiment",
        "interrupted_call_0001",
        execution_id=execution.id,
    )
    with store.database.transaction() as c:
        c.execute(
            """UPDATE sb_stage_executions SET
            expires_at=clock_timestamp()-interval '1 second' WHERE
            investigation_id=%s AND stage='reproduction'""",
            (inv.id,),
        )
    current = store.acquire_stage(
        session.id, inv.id, "reproduction", "recover_stage_0001"
    )
    with pytest.raises(Conflict):
        store.finish_tool(session.id, old, execution, {"status": "success"}, [])
    with pytest.raises(Conflict):
        store.begin_tool(
            session.id,
            current,
            "run_checkout_quote",
            dict(execution.arguments),
            "interrupted_call_0001",
        )
    assert store.get_investigation(session.id, inv.id).experiment_count == 1


def test_global_creation_limit_is_atomic_across_sessions(store):
    limited = Store(
        Database(
            replace(store.settings, global_active_limit=1), schema=store.database.schema
        )
    )
    owners = [limited.create_session()[0] for _ in range(4)]

    def create(owner):
        try:
            return limited.create_investigation(
                owner.id,
                m.CreateInvestigation(complaint="Global admission test"),
                "global_create_0001",
            )
        except LimitReached:
            return None

    with ThreadPoolExecutor(max_workers=4) as pool:
        result = list(pool.map(create, owners))
    assert sum(item is not None for item in result) == 1


def test_independent_processes_share_the_same_experiment_cap(store):
    import subprocess
    import sys

    session, _, inv, lease = reproduction(store)
    program = """
import os
from uuid import UUID
from backend.storage.database import Database, Settings
from backend.storage.models import Lease
from backend.storage.repository import Store
store = Store(Database(Settings(os.environ['TEST_DATABASE_URL'], ai_enabled=True),
                       schema=os.environ['SB_TEST_SCHEMA']))
lease = Lease.model_validate_json(os.environ['SB_TEST_LEASE'])
owner = UUID(os.environ['SB_TEST_OWNER'])
accepted = 0
for n in range(3):
    key = 'process_' + os.environ['SB_TEST_WORKER'] + '_quote_' + str(n)
    execution, _ = store.begin_tool(owner, lease, 'run_checkout_quote',
        {'release':'v1.0','subtotal_cents':12500,'discount_percent':20}, key)
    accepted += store.reserve(owner, lease, 'experiment', key,
                              execution_id=execution.id) is not None
print(accepted)
"""
    children = []
    try:
        for worker in range(4):
            environment = {
                **os.environ,
                "SB_TEST_SCHEMA": store.database.schema,
                "SB_TEST_OWNER": str(session.id),
                "SB_TEST_LEASE": lease.model_dump_json(),
                "SB_TEST_WORKER": str(worker),
            }
            children.append(
                subprocess.Popen(
                    [sys.executable, "-c", program],
                    env=environment,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
            )
        accepted = 0
        for process in children:
            stdout, stderr = process.communicate(timeout=30)
            assert process.returncode == 0, stderr
            accepted += int(stdout.strip())
        assert accepted == 8
        assert store.get_investigation(session.id, inv.id).experiment_count == 8
    finally:
        for process in children:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=5)


def test_review_waiting_runs_do_not_occupy_global_execution_capacity(
    store, monkeypatch
):
    limited = Store(
        Database(
            replace(store.settings, global_active_limit=1), schema=store.database.schema
        )
    )
    waiting = [review_ready(limited, monkeypatch) for _ in range(3)]
    for owner, inv in waiting:
        assert limited.get_investigation(owner.id, inv.id).status == "awaiting_review"
        with pytest.raises(LimitReached):
            limited.create_investigation(
                owner.id,
                m.CreateInvestigation(complaint="Another open run"),
                "another_open_0001",
            )
    owners = [limited.create_session()[0] for _ in range(4)]

    def create(owner):
        try:
            return limited.create_investigation(
                owner.id,
                m.CreateInvestigation(complaint="Eligible visitor"),
                "eligible_create_0001",
            )
        except LimitReached:
            return None

    with ThreadPoolExecutor(max_workers=4) as pool:
        admitted = list(pool.map(create, owners))
    assert sum(item is not None for item in admitted) == 1
    assert next(item for item in admitted if item).status == "pending"


def test_review_waiting_runs_still_consume_daily_creation_quota(store, monkeypatch):
    limited = Store(
        Database(
            replace(store.settings, global_active_limit=1, global_daily_limit=2),
            schema=store.database.schema,
        )
    )
    review_ready(limited, monkeypatch)
    review_ready(limited, monkeypatch)
    with pytest.raises(LimitReached):
        new_investigation(limited)


def test_existing_model_budget_cannot_be_raised_by_new_host_configuration(store):
    session, _, inv = new_investigation(store)
    raised = Store(
        Database(replace(store.settings, model_limit=20), schema=store.database.schema)
    )
    lease = raised.acquire_stage(session.id, inv.id, "support", "model_snapshot_0001")
    results = [
        raised.reserve(
            session.id,
            lease,
            "model",
            f"model_snapshot_{n:04}",
            provider="test-provider",
            model="test-model",
        )
        for n in range(11)
    ]
    assert sum(item is not None for item in results) == 10
    assert raised.get_investigation(session.id, inv.id).model_call_limit == 10


def test_model_budget_contract_and_sql_constraints_stop_at_twenty(store):
    owner, _, inv = new_investigation(store)
    payload = inv.model_dump(mode="json")
    payload.update(model_call_count=20, model_call_limit=20)
    import json

    assert (
        m.Investigation.model_validate_json(json.dumps(payload)).model_call_count == 20
    )
    for field in ("model_call_count", "model_call_limit"):
        with pytest.raises(ValidationError):
            m.Investigation.model_validate_json(json.dumps({**payload, field: 21}))
        with pytest.raises(StorageUnavailable):
            with store.database.transaction() as c:
                c.execute(
                    sql.SQL("UPDATE sb_investigations SET {}=21 WHERE id=%s").format(
                        sql.Identifier(field)
                    ),
                    (inv.id,),
                )
    assert store.get_investigation(owner.id, inv.id).model_call_limit == 10


@pytest.mark.parametrize("store", ["001_only"], indirect=True)
def test_additive_model_ceiling_migration_preserves_existing_rows_and_checksum(store):
    owner, _, inv = new_investigation(store)
    with store.database.transaction() as c:
        before = c.execute(
            "SELECT checksum FROM sb_schema_migrations WHERE version='001_initial'"
        ).fetchone()["checksum"]
    migrate(store.database)
    migrate(store.database)
    with store.database.transaction() as c:
        after = c.execute(
            "SELECT checksum FROM sb_schema_migrations WHERE version='001_initial'"
        ).fetchone()["checksum"]
        assert before == after
        assert (
            c.execute("SELECT count(*) AS n FROM sb_schema_migrations").fetchone()["n"]
            == 2
        )
    assert store.get_investigation(owner.id, inv.id).model_call_limit == 10
    raised = Store(
        Database(replace(store.settings, model_limit=20), schema=store.database.schema)
    )
    _, _, new_run = new_investigation(raised)
    assert new_run.model_call_limit == 20


def test_migration_checksum_tampering_is_still_rejected(store):
    with store.database.transaction() as c:
        c.execute(
            "UPDATE sb_schema_migrations SET checksum=%s WHERE version='001_initial'",
            ("0" * 64,),
        )
    with pytest.raises(StorageError, match="checksum changed"):
        migrate(store.database)


@pytest.mark.parametrize("kind", ["expired", "malformed", "unknown"])
def test_session_bootstrap_rotates_rejected_credentials_without_transferring_runs(
    store, kind
):
    import secrets

    app.dependency_overrides[get_store] = lambda: store

    async def exercise():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://localhost:3000"
        ) as client:
            headers = {"Origin": "http://localhost:3000"}
            initial = await client.post("/svc/api/sessions", headers=headers)
            assert initial.status_code == 200
            owner = store.resolve_session(client.cookies.get("sb_session"))
            inv = store.create_investigation(
                owner.id,
                m.CreateInvestigation(complaint="Original owner"),
                "session_original_0001",
            )
            credential = client.cookies.get("sb_session")
            if kind == "expired":
                with store.database.transaction() as c:
                    c.execute(
                        """UPDATE sb_sessions SET
                        expires_at=clock_timestamp()-interval '1 second'
                        WHERE id=%s""",
                        (owner.id,),
                    )
            else:
                client.cookies.clear()
                client.cookies.set(
                    "sb_session",
                    "invalid-cookie"
                    if kind == "malformed"
                    else secrets.token_urlsafe(32),
                    domain="localhost.local",
                    path="/svc/api",
                )
            url = f"/svc/api/investigations/{inv.id}"
            for path in (url, url + "/events", url + "/evidence/" + str(uuid4())):
                assert (await client.get(path)).status_code == 401
            rotated = await client.post("/svc/api/sessions", headers=headers)
            assert rotated.status_code == 200 and rotated.json()["id"] != str(owner.id)
            fresh_credential = client.cookies.get("sb_session")
            assert (
                fresh_credential != credential and fresh_credential not in rotated.text
            )
            assert (await client.get(url)).status_code == 404
            with store.database.transaction() as c:
                assert (
                    c.execute(
                        "SELECT owner_session_id FROM sb_investigations WHERE id=%s",
                        (inv.id,),
                    ).fetchone()["owner_session_id"]
                    == owner.id
                )

    try:
        asyncio.run(exercise())
    finally:
        app.dependency_overrides.clear()


def test_valid_session_bootstrap_reuses_owner_and_fixed_expiry(store):
    app.dependency_overrides[get_store] = lambda: store

    async def exercise():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://localhost:3000"
        ) as client:
            headers = {"Origin": "http://localhost:3000"}
            first = await client.post("/svc/api/sessions", headers=headers)
            credential = client.cookies.get("sb_session")
            second = await client.post("/svc/api/sessions", headers=headers)
            assert first.json() == second.json()
            assert client.cookies.get("sb_session") == credential
            assert "set-cookie" not in second.headers
            with store.database.transaction() as c:
                assert (
                    c.execute("SELECT count(*) AS n FROM sb_sessions").fetchone()["n"]
                    == 1
                )

    try:
        asyncio.run(exercise())
    finally:
        app.dependency_overrides.clear()
