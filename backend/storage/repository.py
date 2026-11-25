"""Explicit PostgreSQL transactions for ownership, fencing and append-only evidence."""

import hashlib
import json
import re
import secrets
from datetime import UTC, datetime
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb
from pydantic import TypeAdapter
from pydantic_core import to_json

from . import models as m
from .database import (
    Conflict,
    Database,
    ExecutionDisabled,
    LimitReached,
    NotFound,
    SessionDenied,
)
from .safety import canonical_json, content_hash

EXECUTION_ACTIVE = ("pending", "running", "awaiting_stage")
SESSION_OPEN = (*EXECUTION_ACTIVE, "awaiting_review")
PREREQUISITES = {
    "support": set(),
    "repository": set(),
    "reproduction": {"support", "repository"},
    "verification": {"reproduction"},
    "follow_up": {"verification"},
    "verification_recheck": {"follow_up"},
}


def decoded(model, row):
    return model.model_validate_json(to_json(row))


def credential_hash(credential: str) -> str:
    if not isinstance(credential, str) or not re.fullmatch(
        r"[A-Za-z0-9_-]{43}", credential
    ):
        raise SessionDenied("A valid anonymous session is required")
    return hashlib.sha256(credential.encode()).hexdigest()


def operation_key(value: str) -> str:
    return TypeAdapter(m.OperationKey).validate_python(value, strict=True)


class Store:
    def __init__(self, database: Database):
        self.database, self.settings = database, database.settings

    def create_session(self) -> tuple[m.Session, str]:
        credential = secrets.token_urlsafe(32)
        with self.database.transaction() as c:
            row = c.execute(
                """INSERT INTO sb_sessions(id, credential_hash, expires_at) VALUES
                (%s, %s, clock_timestamp()+make_interval(secs=>%s)) RETURNING id,
                created_at, expires_at""",
                (uuid4(), credential_hash(credential), self.settings.session_ttl),
            ).fetchone()
            return decoded(m.Session, row), credential

    def resolve_session(self, credential: str | None) -> m.Session:
        digest = credential_hash(credential)
        with self.database.transaction() as c:
            row = c.execute(
                """SELECT id, created_at, expires_at FROM sb_sessions WHERE
                credential_hash=%s AND expires_at>clock_timestamp()""",
                (digest,),
            ).fetchone()
            if row is None:
                raise SessionDenied("A valid anonymous session is required")
            return decoded(m.Session, row)

    def _owned(self, c, session_id, investigation_id, *, lock=True):
        row = c.execute(
            """SELECT i.* FROM sb_investigations i JOIN sb_sessions s ON
            s.id=i.owner_session_id WHERE i.id=%s AND s.id=%s AND
            s.expires_at>clock_timestamp()"""
            + (" FOR UPDATE OF i" if lock else ""),
            (investigation_id, session_id),
        ).fetchone()
        if row is None:
            raise NotFound("Investigation record not found")
        return row

    def _investigation(self, row):
        fields = m.Investigation.model_fields
        return decoded(m.Investigation, {key: row[key] for key in fields if key in row})

    def create_investigation(
        self, session_id: UUID, request: m.CreateInvestigation, key: str
    ) -> m.Investigation:
        operation_key(key)
        data = request.model_dump(mode="json")
        digest = content_hash(data)
        with self.database.transaction() as c:
            c.execute("""SELECT id FROM sb_controls WHERE id=1 FOR UPDATE""").fetchone()
            session = c.execute(
                """SELECT id FROM sb_sessions WHERE id=%s AND
                expires_at>clock_timestamp() FOR UPDATE""",
                (session_id,),
            ).fetchone()
            if session is None:
                raise SessionDenied("A valid anonymous session is required")
            existing = c.execute(
                """SELECT * FROM sb_investigations WHERE owner_session_id=%s AND
                operation_key=%s""",
                (session_id, key),
            ).fetchone()
            if existing:
                if existing["request_hash"] != digest:
                    raise Conflict("Idempotency key already has different inputs")
                return self._investigation(existing)
            counts = c.execute(
                """SELECT count(*) FILTER(WHERE i.owner_session_id=%s AND
                i.status=ANY(%s)) AS own_open, count(*) FILTER(WHERE
                i.owner_session_id=%s AND i.created_at>clock_timestamp()-interval
                '24 hours') AS own_daily, count(*) FILTER(WHERE i.status=ANY(%s)
                AND s.expires_at>clock_timestamp()) AS global_active, count(*)
                FILTER(WHERE i.created_at>clock_timestamp()-interval '24 hours')
                AS global_daily FROM sb_investigations i JOIN sb_sessions s ON
                s.id=i.owner_session_id""",
                (session_id, list(SESSION_OPEN), session_id, list(EXECUTION_ACTIVE)),
            ).fetchone()
            if (
                counts["own_open"] >= 1
                or counts["own_daily"] >= self.settings.session_daily_limit
                or counts["global_active"] >= self.settings.global_active_limit
                or counts["global_daily"] >= self.settings.global_daily_limit
            ):
                raise LimitReached("Investigation creation limit reached")
            row = c.execute(
                """INSERT INTO sb_investigations(id, owner_session_id, operation_key,
                request_hash, complaint, ticket_id, experiment_limit,
                model_call_limit) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *""",
                (
                    uuid4(),
                    session_id,
                    key,
                    digest,
                    request.complaint,
                    request.ticket_id,
                    self.settings.experiment_limit,
                    self.settings.model_limit,
                ),
            ).fetchone()
            self._event(c, row["id"], "coordinator", "investigation_created", {})
            return self._investigation(
                c.execute(
                    """SELECT * FROM sb_investigations WHERE id=%s""", (row["id"],)
                ).fetchone()
            )

    def get_investigation(
        self, session_id: UUID, investigation_id: UUID
    ) -> m.Investigation:
        with self.database.transaction() as c:
            row = self._owned(c, session_id, investigation_id, lock=False)
            row["stages"] = c.execute(
                """SELECT stage, fence, expires_at, status FROM sb_stage_executions
                WHERE investigation_id=%s ORDER BY stage""",
                (investigation_id,),
            ).fetchall()
            return self._investigation(row)

    def _citations(self, c, investigation_id, evidence_ids):
        ids = set(evidence_ids)
        if not ids:
            return
        count = c.execute(
            """SELECT count(*) AS n FROM sb_evidence WHERE investigation_id=%s AND
            id=ANY(%s)""",
            (investigation_id, list(ids)),
        ).fetchone()["n"]
        if count != len(ids):
            raise NotFound("Cited evidence is not part of this investigation")

    def validate_citations(
        self, session_id: UUID, investigation_id: UUID, evidence_ids: tuple[UUID, ...]
    ) -> bool:
        with self.database.transaction() as c:
            self._owned(c, session_id, investigation_id, lock=False)
            self._citations(c, investigation_id, evidence_ids)
            return True

    def _event(
        self,
        c,
        investigation_id,
        actor,
        event_type,
        payload,
        *,
        tool_name=None,
        evidence_ids=(),
    ):
        stage = actor if actor in PREREQUISITES else None
        actor = {
            "follow_up": "reproduction",
            "verification_recheck": "verification",
        }.get(actor, actor)
        TypeAdapter(m.Actor).validate_python(actor, strict=True)
        TypeAdapter(m.EventType).validate_python(event_type, strict=True)
        content = canonical_json(payload, maximum=16384)
        self._citations(c, investigation_id, evidence_ids)
        seq = c.execute(
            """UPDATE sb_investigations SET event_sequence=event_sequence+1,
            updated_at=clock_timestamp() WHERE id=%s RETURNING event_sequence""",
            (investigation_id,),
        ).fetchone()["event_sequence"]
        row = c.execute(
            """INSERT INTO sb_events(id, investigation_id, sequence, actor, stage,
            event_type, tool_name, payload, evidence_ids) VALUES (%s, %s, %s, %s,
            %s, %s, %s, %s, %s) RETURNING *""",
            (
                uuid4(),
                investigation_id,
                seq,
                actor,
                stage,
                event_type,
                tool_name,
                Jsonb(json.loads(content)),
                list(evidence_ids),
            ),
        ).fetchone()
        return decoded(m.Event, row)

    def append_event(
        self,
        session_id: UUID,
        lease: m.Lease,
        event_type: m.EventType,
        payload: dict,
        *,
        evidence_ids=(),
    ) -> m.Event:
        with self.database.transaction() as c:
            self._fence(c, session_id, lease)
            return self._event(
                c,
                lease.investigation_id,
                lease.stage,
                event_type,
                payload,
                evidence_ids=evidence_ids,
            )

    def list_events(
        self, session_id: UUID, investigation_id: UUID, *, after=0, limit=50
    ) -> m.EventPage:
        if (
            type(after) is not int
            or after < 0
            or type(limit) is not int
            or not 1 <= limit <= 100
        ):
            raise ValueError("Invalid timeline pagination")
        with self.database.transaction() as c:
            self._owned(c, session_id, investigation_id, lock=False)
            rows = c.execute(
                """SELECT * FROM sb_events WHERE investigation_id=%s AND sequence>%s
                ORDER BY sequence LIMIT %s""",
                (investigation_id, after, limit + 1),
            ).fetchall()
            return m.EventPage(
                events=tuple(decoded(m.Event, row) for row in rows[:limit]),
                next_after=rows[limit - 1]["sequence"] if len(rows) > limit else None,
            )

    def get_evidence(
        self, session_id: UUID, investigation_id: UUID, evidence_id: UUID
    ) -> m.Evidence:
        with self.database.transaction() as c:
            self._owned(c, session_id, investigation_id, lock=False)
            row = c.execute(
                """SELECT * FROM sb_evidence WHERE id=%s AND investigation_id=%s""",
                (evidence_id, investigation_id),
            ).fetchone()
            if row is None:
                raise NotFound("Evidence record not found")
            return decoded(m.Evidence, row)

    def acquire_stage(
        self, session_id: UUID, investigation_id: UUID, stage: m.Stage, key: str
    ) -> m.Lease:
        if not self.settings.ai_enabled:
            raise ExecutionDisabled("Investigation execution is disabled")
        operation_key(key)
        if not self.settings.ai_enabled:
            raise ExecutionDisabled("AI execution is disabled")
        TypeAdapter(m.Stage).validate_python(stage, strict=True)
        with self.database.transaction() as c:
            inv = self._owned(c, session_id, investigation_id)
            existing = c.execute(
                """SELECT *, expires_at>clock_timestamp() AS live FROM
                sb_stage_executions WHERE investigation_id=%s AND stage=%s FOR
                UPDATE""",
                (investigation_id, stage),
            ).fetchone()
            if existing and existing["status"] == "completed":
                if existing["operation_key"] != key:
                    raise Conflict("Stage is already completed")
                return decoded(m.Lease, {k: existing[k] for k in m.Lease.model_fields})
            if inv["status"] not in ("pending", "running", "awaiting_stage"):
                raise Conflict("Investigation is not executable")
            completed = inv["state"]["stage_outputs"]
            if not PREREQUISITES[stage].issubset(completed):
                raise Conflict("Stage prerequisites are incomplete")
            if existing and existing["status"] == "running" and existing["live"]:
                raise Conflict("Stage already has an active lease")
            row = c.execute(
                """INSERT INTO sb_stage_executions(investigation_id, stage,
                operation_key, lease_token, fence, expires_at, status) VALUES (%s,
                %s, %s, %s, 1, clock_timestamp()+make_interval(secs=>%s),
                'running') ON CONFLICT(investigation_id, stage) DO UPDATE SET
                operation_key=EXCLUDED.operation_key,
                lease_token=EXCLUDED.lease_token,
                fence=sb_stage_executions.fence+1, expires_at=EXCLUDED.expires_at,
                status='running', output_hash=NULL RETURNING *""",
                (investigation_id, stage, key, uuid4(), self.settings.lease_seconds),
            ).fetchone()
            c.execute(
                """UPDATE sb_investigations SET status='running', current_stage=%s
                WHERE id=%s""",
                (stage, investigation_id),
            )
            self._event(
                c, investigation_id, stage, "stage_started", {"fence": row["fence"]}
            )
            return decoded(m.Lease, {k: row[k] for k in m.Lease.model_fields})

    def _fence(self, c, session_id, lease):
        if not self.settings.ai_enabled:
            raise ExecutionDisabled("AI execution is disabled")
        inv = self._owned(c, session_id, lease.investigation_id)
        row = c.execute(
            """SELECT * FROM sb_stage_executions WHERE investigation_id=%s AND
            stage=%s AND lease_token=%s AND fence=%s AND status='running' AND
            expires_at>clock_timestamp() FOR UPDATE""",
            (lease.investigation_id, lease.stage, lease.lease_token, lease.fence),
        ).fetchone()
        if row is None or inv["status"] not in ("running", "awaiting_stage"):
            raise Conflict("Execution lease is stale or unavailable")
        return inv

    def renew_stage(self, session_id: UUID, lease: m.Lease) -> m.Lease:
        with self.database.transaction() as c:
            self._fence(c, session_id, lease)
            row = c.execute(
                """UPDATE sb_stage_executions SET
                expires_at=clock_timestamp()+make_interval(secs=>%s) WHERE
                investigation_id=%s AND stage=%s RETURNING *""",
                (self.settings.lease_seconds, lease.investigation_id, lease.stage),
            ).fetchone()
            return decoded(m.Lease, {k: row[k] for k in m.Lease.model_fields})

    def complete_stage(
        self, session_id: UUID, lease: m.Lease, summary: m.StageSummary
    ) -> m.Investigation:
        digest = content_hash(summary.model_dump(mode="json"))
        with self.database.transaction() as c:
            inv = self._owned(c, session_id, lease.investigation_id)
            old = c.execute(
                """SELECT * FROM sb_stage_executions WHERE investigation_id=%s AND
                stage=%s""",
                (lease.investigation_id, lease.stage),
            ).fetchone()
            if (
                old
                and old["status"] == "completed"
                and old["lease_token"] == lease.lease_token
            ):
                if old["output_hash"] != digest:
                    raise Conflict("Completed stage has different output")
                return self._investigation(inv)
            self._fence(c, session_id, lease)
            self._citations(c, lease.investigation_id, summary.evidence_ids)
            state = inv["state"]
            state["stage_outputs"][lease.stage] = summary.model_dump(mode="json")
            canonical_json(state, maximum=32768)
            decoded(m.WorkflowState, state)
            c.execute(
                """UPDATE sb_stage_executions SET status='completed', output_hash=%s
                WHERE investigation_id=%s AND stage=%s""",
                (digest, lease.investigation_id, lease.stage),
            )
            c.execute(
                """UPDATE sb_investigations SET state=%s, status='awaiting_stage'
                WHERE id=%s""",
                (Jsonb(state), lease.investigation_id),
            )
            self._event(
                c,
                lease.investigation_id,
                lease.stage,
                "stage_completed",
                {},
                evidence_ids=summary.evidence_ids,
            )
            return self._investigation(
                c.execute(
                    """SELECT * FROM sb_investigations WHERE id=%s""",
                    (lease.investigation_id,),
                ).fetchone()
            )

    def fail_stage(
        self, session_id: UUID, lease: m.Lease, *, environment_blocked=False
    ) -> None:
        with self.database.transaction() as c:
            self._fence(c, session_id, lease)
            status = "environment_blocked" if environment_blocked else "failed"
            c.execute(
                """UPDATE sb_stage_executions SET status='failed' WHERE
                investigation_id=%s AND stage=%s""",
                (lease.investigation_id, lease.stage),
            )
            c.execute(
                """UPDATE sb_investigations SET status=%s WHERE id=%s""",
                (status, lease.investigation_id),
            )
            self._event(
                c, lease.investigation_id, lease.stage, "error", {"status": status}
            )

    def finish_investigation(
        self,
        session_id: UUID,
        lease: m.Lease,
        summary: m.StageSummary,
        findings: m.Findings | None = None,
    ):
        """Persist host-supplied completion without inferring a finding."""
        if lease.stage not in ("verification", "verification_recheck"):
            raise Conflict("Completion requires the verification stage")
        if findings and findings.behavior == "verified_regression":
            raise Conflict("Verified escalation must enter human review")
        digest = content_hash(
            {
                "summary": summary.model_dump(mode="json"),
                "findings": findings.model_dump(mode="json") if findings else None,
            }
        )
        with self.database.transaction() as c:
            inv = self._owned(c, session_id, lease.investigation_id)
            old = c.execute(
                """SELECT * FROM sb_stage_executions WHERE investigation_id=%s AND
                stage=%s""",
                (lease.investigation_id, lease.stage),
            ).fetchone()
            if (
                old
                and old["status"] == "completed"
                and old["lease_token"] == lease.lease_token
                and old["output_hash"] == digest
            ):
                return self._investigation(inv)
            self._fence(c, session_id, lease)
            self._citations(c, lease.investigation_id, summary.evidence_ids)
            state = inv["state"]
            state["stage_outputs"][lease.stage] = summary.model_dump(mode="json")
            canonical_json(state, maximum=32768)
            c.execute(
                """UPDATE sb_stage_executions SET status='completed', output_hash=%s
                WHERE investigation_id=%s AND stage=%s""",
                (digest, lease.investigation_id, lease.stage),
            )
            c.execute(
                """UPDATE sb_investigations SET status='completed', state=%s,
                findings=%s WHERE id=%s""",
                (
                    Jsonb(state),
                    Jsonb(findings.model_dump(mode="json")) if findings else None,
                    lease.investigation_id,
                ),
            )
            self._event(
                c,
                lease.investigation_id,
                lease.stage,
                "stage_completed",
                {},
                evidence_ids=summary.evidence_ids,
            )
            self._event(
                c, lease.investigation_id, "coordinator", "investigation_completed", {}
            )
            return self._investigation(
                c.execute(
                    """SELECT * FROM sb_investigations WHERE id=%s""",
                    (lease.investigation_id,),
                ).fetchone()
            )

    def begin_tool(
        self,
        session_id: UUID,
        lease: m.Lease,
        tool_name: str,
        arguments: dict,
        key: str,
    ) -> tuple[m.ToolExecution, bool]:
        operation_key(key)
        args = json.loads(canonical_json(arguments, maximum=8192))
        digest = content_hash(args)
        with self.database.transaction() as c:
            self._fence(c, session_id, lease)
            old = c.execute(
                """SELECT * FROM sb_tool_executions WHERE investigation_id=%s AND
                operation_key=%s""",
                (lease.investigation_id, key),
            ).fetchone()
            if old:
                if (
                    old["tool_name"] != tool_name
                    or old["arguments_hash"] != digest
                    or old["stage"] != lease.stage
                ):
                    raise Conflict("Tool idempotency key has different inputs")
                if old["status"] == "running":
                    raise Conflict(
                        "Prior tool execution is active or interrupted; inspect "
                        "before a new attempt"
                    )
                return decoded(m.ToolExecution, old), False
            row = c.execute(
                """INSERT INTO sb_tool_executions(id, investigation_id, stage, fence,
                operation_key, tool_name, arguments, arguments_hash, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'running') RETURNING *""",
                (
                    uuid4(),
                    lease.investigation_id,
                    lease.stage,
                    lease.fence,
                    key,
                    tool_name,
                    Jsonb(args),
                    digest,
                ),
            ).fetchone()
            self._event(
                c,
                lease.investigation_id,
                lease.stage,
                "tool_selected",
                {},
                tool_name=tool_name,
            )
            self._event(
                c,
                lease.investigation_id,
                lease.stage,
                "tool_arguments",
                args,
                tool_name=tool_name,
            )
            return decoded(m.ToolExecution, row), True

    def _evidence(
        self,
        c,
        lease,
        category,
        source_id,
        payload,
        *,
        execution_id=None,
        reference=None,
        sha=None,
        observed_at=None,
        trust="untrusted_data",
        provenance=None,
    ):
        TypeAdapter(m.Category).validate_python(category, strict=True)
        data = json.loads(canonical_json(payload))
        provenance = json.loads(canonical_json(provenance or {}, maximum=8192))
        if (
            len(source_id) > 300
            or reference
            and len(reference) > 2000
            or sha
            and not re.fullmatch(r"[0-9a-f]{40}", sha)
        ):
            raise ValueError("Invalid source provenance")
        canonical_json({"source_id": source_id, "source_reference": reference})
        row = c.execute(
            """INSERT INTO sb_evidence(id, investigation_id, category, source_id,
            payload, source_reference, historical_sha, observed_at, content_hash,
            provenance, trust, execution_id) VALUES (%s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s) RETURNING *""",
            (
                uuid4(),
                lease.investigation_id,
                category,
                source_id,
                Jsonb(data),
                reference,
                sha,
                observed_at or datetime.now(UTC),
                content_hash(data),
                Jsonb(provenance),
                trust,
                execution_id,
            ),
        ).fetchone()
        self._event(
            c,
            lease.investigation_id,
            lease.stage,
            "evidence_recorded",
            {"category": category},
            evidence_ids=(row["id"],),
        )
        return decoded(m.Evidence, row)

    def finish_tool(
        self,
        session_id: UUID,
        lease: m.Lease,
        execution: m.ToolExecution,
        result: dict,
        records: list[dict],
        *,
        failed=False,
    ) -> tuple[UUID, ...]:
        data = json.loads(canonical_json(result))
        with self.database.transaction() as c:
            self._fence(c, session_id, lease)
            old = c.execute(
                """SELECT * FROM sb_tool_executions WHERE id=%s AND
                investigation_id=%s AND stage=%s AND fence=%s AND status='running'
                FOR UPDATE""",
                (execution.id, lease.investigation_id, lease.stage, lease.fence),
            ).fetchone()
            if old is None:
                raise Conflict("Tool execution is stale or already completed")
            self._event(
                c,
                lease.investigation_id,
                lease.stage,
                "tool_result",
                {
                    "execution_id": str(execution.id),
                    "status": "failed" if failed else "received",
                },
                tool_name=execution.tool_name,
            )
            evidence = [
                self._evidence(c, lease, execution_id=execution.id, **record)
                for record in records
            ]
            ids = tuple(item.id for item in evidence)
            c.execute(
                """UPDATE sb_tool_executions SET status=%s, result=%s,
                evidence_ids=%s, completed_at=clock_timestamp() WHERE id=%s""",
                (
                    "failed" if failed else "succeeded",
                    Jsonb(data),
                    list(ids),
                    execution.id,
                ),
            )
            if failed:
                self._event(
                    c,
                    lease.investigation_id,
                    lease.stage,
                    "error",
                    {"execution_id": str(execution.id)},
                    tool_name=execution.tool_name,
                )
            return ids

    def reserve(
        self,
        session_id: UUID,
        lease: m.Lease,
        kind: str,
        key: str,
        *,
        execution_id=None,
        provider=None,
        model=None,
    ) -> m.Reservation | None:
        if not self.settings.ai_enabled:
            raise ExecutionDisabled("Investigation execution is disabled")
        operation_key(key)
        if kind not in ("experiment", "model") or (
            kind == "experiment" and execution_id is None
        ):
            raise ValueError("Invalid execution reservation")
        canonical_json({"provider": provider, "model": model}, maximum=2000)
        if kind == "model" and (
            not provider or not model or len(provider) > 100 or len(model) > 200
        ):
            raise ValueError("Model identity is required")
        with self.database.transaction() as c:
            inv = self._fence(c, session_id, lease)
            if execution_id:
                execution = c.execute(
                    """SELECT id FROM sb_tool_executions WHERE id=%s AND
                    investigation_id=%s AND stage=%s AND fence=%s AND
                    status='running'""",
                    (execution_id, lease.investigation_id, lease.stage, lease.fence),
                ).fetchone()
                if execution is None:
                    raise Conflict("No active tool execution for reservation")
            old = c.execute(
                """SELECT id FROM sb_usage_reservations WHERE investigation_id=%s AND
                kind=%s AND operation_key=%s""",
                (lease.investigation_id, kind, key),
            ).fetchone()
            if old:
                return None
            count = "experiment_count" if kind == "experiment" else "model_call_count"
            limit = (
                inv["experiment_limit"]
                if kind == "experiment"
                else inv["model_call_limit"]
            )
            if inv[count] >= limit:
                self._event(
                    c,
                    lease.investigation_id,
                    lease.stage,
                    "budget_exhausted",
                    {"kind": kind},
                )
                return None
            # Column names are fixed host constants; values remain bound parameters.
            c.execute(
                f"UPDATE sb_investigations SET {count}={count}+1 WHERE id=%s",
                (lease.investigation_id,),
            )
            row = c.execute(
                """INSERT INTO sb_usage_reservations(id, investigation_id, stage,
                kind, ordinal, operation_key, execution_id, provider, model,
                outcome) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'reserved')
                RETURNING *""",
                (
                    uuid4(),
                    lease.investigation_id,
                    lease.stage,
                    kind,
                    inv[count] + 1,
                    key,
                    execution_id,
                    provider,
                    model,
                ),
            ).fetchone()
            self._event(
                c,
                lease.investigation_id,
                lease.stage,
                "usage_reserved",
                {"kind": kind, "ordinal": row["ordinal"]},
            )
            return decoded(m.Reservation, row)

    def record_usage(
        self,
        session_id: UUID,
        lease: m.Lease,
        reservation_id: UUID,
        *,
        outcome: str,
        input_tokens=None,
        output_tokens=None,
    ) -> m.Reservation:
        if outcome not in ("succeeded", "failed", "unknown") or any(
            v is not None and (type(v) is not int or v < 0)
            for v in (input_tokens, output_tokens)
        ):
            raise ValueError("Invalid observed usage")
        with self.database.transaction() as c:
            self._fence(c, session_id, lease)
            row = c.execute(
                """UPDATE sb_usage_reservations SET outcome=%s, input_tokens=%s,
                output_tokens=%s, completed_at=clock_timestamp() WHERE id=%s AND
                investigation_id=%s AND stage=%s AND completed_at IS NULL
                RETURNING *""",
                (
                    outcome,
                    input_tokens,
                    output_tokens,
                    reservation_id,
                    lease.investigation_id,
                    lease.stage,
                ),
            ).fetchone()
            if row is None:
                raise Conflict("Usage reservation is missing or already completed")
            self._event(
                c,
                lease.investigation_id,
                lease.stage,
                "usage_recorded",
                {
                    "kind": row["kind"],
                    "outcome": outcome,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                },
            )
            return decoded(m.Reservation, row)

    def record_assertion(
        self, session_id: UUID, lease: m.Lease, assertion: m.VerifiedAssertion
    ) -> m.Evidence:
        if lease.stage not in ("verification", "verification_recheck"):
            raise Conflict("Independent assertion requires verification stage")
        with self.database.transaction() as c:
            self._fence(c, session_id, lease)
            self._citations(c, lease.investigation_id, assertion.evidence_ids)
            quotes = c.execute(
                """SELECT e.id FROM sb_evidence e JOIN sb_tool_executions t
                ON t.id=e.execution_id AND t.investigation_id=e.investigation_id
                WHERE e.investigation_id=%s AND e.id=ANY(%s)
                AND e.category='checkout_observation'
                AND e.payload->>'status'='success'
                AND e.payload->>'http_status'='200'
                AND t.stage=%s AND t.fence=%s""",
                (
                    lease.investigation_id,
                    list(assertion.evidence_ids),
                    lease.stage,
                    lease.fence,
                ),
            ).fetchall()
            if not quotes:
                raise Conflict(
                    "Independent assertion needs recorded successful HTTP evidence"
                )
            return self._evidence(
                c,
                lease,
                "verified_assertion",
                str(uuid4()),
                assertion.model_dump(mode="json"),
                trust="host_assertion",
                provenance={"stage": lease.stage, "fence": lease.fence},
            )

    def prepare_review(
        self,
        session_id: UUID,
        lease: m.Lease,
        draft: m.EscalationDraft,
        findings: m.Findings,
        assertion_id: UUID,
    ) -> None:
        if (
            lease.stage not in ("verification", "verification_recheck")
            or findings.behavior != "verified_regression"
        ):
            raise Conflict(
                "Only independently verified cases can enter escalation review"
            )
        payload = draft.model_dump(mode="json")
        canonical_json(payload, maximum=32768)
        with self.database.transaction() as c:
            inv = self._fence(c, session_id, lease)
            self._citations(
                c, lease.investigation_id, (*draft.evidence_ids, assertion_id)
            )
            assertion = c.execute(
                """SELECT * FROM sb_evidence WHERE id=%s AND investigation_id=%s AND
                category='verified_assertion' AND trust='host_assertion'""",
                (assertion_id, lease.investigation_id),
            ).fetchone()
            if assertion is None:
                raise Conflict("Verified assertion is required")
            checked_assertion = decoded(m.VerifiedAssertion, assertion["payload"])
            if assertion["provenance"] != {
                "stage": lease.stage,
                "fence": lease.fence,
            } or not set(draft.evidence_ids).issubset(checked_assertion.evidence_ids):
                raise Conflict(
                    "Draft must cite the current independently verified evidence"
                )
            state = inv["state"]
            state["stage_outputs"][lease.stage] = m.StageSummary(
                evidence_ids=draft.evidence_ids
            ).model_dump(mode="json")
            c.execute(
                """INSERT INTO sb_review_drafts(investigation_id, draft,
                assertion_id) VALUES (%s, %s, %s)""",
                (lease.investigation_id, Jsonb(payload), assertion_id),
            )
            c.execute(
                """UPDATE sb_stage_executions SET status='completed', output_hash=%s
                WHERE investigation_id=%s AND stage=%s""",
                (content_hash(payload), lease.investigation_id, lease.stage),
            )
            c.execute(
                """UPDATE sb_investigations SET status='awaiting_review', state=%s,
                findings=%s WHERE id=%s""",
                (
                    Jsonb(state),
                    Jsonb(findings.model_dump(mode="json")),
                    lease.investigation_id,
                ),
            )
            self._event(
                c,
                lease.investigation_id,
                lease.stage,
                "stage_completed",
                {},
                evidence_ids=draft.evidence_ids,
            )
            self._event(
                c,
                lease.investigation_id,
                "coordinator",
                "review_requested",
                {},
                evidence_ids=(assertion_id,),
            )

    def decide_review(
        self, session_id: UUID, investigation_id: UUID, decision: str, note: str = ""
    ) -> m.ReviewDecision:
        if (
            decision not in ("approved", "rejected")
            or not isinstance(note, str)
            or len(note) > 2000
        ):
            raise ValueError("Invalid human review")
        canonical_json({"reviewer_note": note})
        with self.database.transaction() as c:
            inv = self._owned(c, session_id, investigation_id)
            old = c.execute(
                """SELECT * FROM sb_reviews WHERE investigation_id=%s""",
                (investigation_id,),
            ).fetchone()
            if old:
                if old["decision"] != decision or old["reviewer_note"] != note:
                    raise Conflict("A final review decision already exists")
                return decoded(m.ReviewDecision, old)
            draft = c.execute(
                """SELECT * FROM sb_review_drafts WHERE investigation_id=%s""",
                (investigation_id,),
            ).fetchone()
            if (
                inv["status"] != "awaiting_review"
                or inv["findings"] is None
                or inv["findings"]["behavior"] != "verified_regression"
                or draft is None
            ):
                raise Conflict("Investigation is ineligible for escalation review")
            escalation_id = None
            if decision == "approved":
                escalation_id = uuid4()
                c.execute(
                    """INSERT INTO sb_escalations(id, investigation_id, draft) VALUES
                    (%s, %s, %s)""",
                    (escalation_id, investigation_id, Jsonb(draft["draft"])),
                )
            row = c.execute(
                """INSERT INTO sb_reviews(investigation_id, decision, reviewer_note,
                escalation_id) VALUES (%s, %s, %s, %s) RETURNING *""",
                (investigation_id, decision, note, escalation_id),
            ).fetchone()
            c.execute(
                """UPDATE sb_investigations SET status='completed' WHERE id=%s""",
                (investigation_id,),
            )
            self._event(
                c, investigation_id, "human", "review_decided", {"decision": decision}
            )
            self._event(
                c, investigation_id, "coordinator", "investigation_completed", {}
            )
            return decoded(m.ReviewDecision, row)
