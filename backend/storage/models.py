"""Strict persisted contracts, separate lifecycle and evidence findings."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, Field, JsonValue

if __package__ == "storage":
    from tools.investigation_models import FrozenModel
else:
    from ..tools.investigation_models import FrozenModel

Stage = Literal[
    "support",
    "repository",
    "reproduction",
    "verification",
    "follow_up",
    "verification_recheck",
]
Actor = Literal[
    "coordinator", "support", "repository", "reproduction", "verification", "human"
]
Lifecycle = Literal[
    "pending",
    "running",
    "awaiting_stage",
    "awaiting_review",
    "completed",
    "failed",
    "environment_blocked",
]
Category = Literal[
    "support_ticket",
    "policy_section",
    "payment_event",
    "github_source",
    "github_comparison",
    "checkout_observation",
    "tool_result",
    "verified_assertion",
]
EventType = Literal[
    "investigation_created",
    "stage_started",
    "tool_selected",
    "tool_arguments",
    "tool_result",
    "evidence_recorded",
    "hypothesis_proposed",
    "hypothesis_revised",
    "contradiction_observed",
    "follow_up_requested",
    "verification_challenged",
    "stage_completed",
    "error",
    "budget_exhausted",
    "investigation_completed",
    "review_requested",
    "review_decided",
    "usage_reserved",
    "usage_recorded",
]
OperationKey = Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{8,80}$")]
ShortText = Annotated[str, Field(min_length=1, max_length=1000)]


class Findings(FrozenModel):
    behavior: Literal[
        "verified_regression",
        "not_reproduced_in_tested_scope",
        "insufficient_evidence",
        "environment_blocked",
    ]
    cause: Literal["unknown", "suspected"]


class StageSummary(FrozenModel):
    explanation: Annotated[str, Field(max_length=2000)] = ""
    evidence_ids: Annotated[tuple[UUID, ...], Field(max_length=128)] = ()


class WorkflowState(FrozenModel):
    stage_outputs: dict[Stage, StageSummary] = Field(default_factory=dict)


class CreateInvestigation(FrozenModel):
    complaint: Annotated[str, Field(min_length=1, max_length=4000, pattern=r"\S")]
    ticket_id: Annotated[str, Field(pattern=r"^TKT-[0-9]{4}$")] | None = None


class StageExecutionView(FrozenModel):
    stage: Stage
    fence: int
    expires_at: AwareDatetime
    status: Literal["running", "completed", "failed"]


class Investigation(FrozenModel):
    id: UUID
    owner_session_id: UUID
    complaint: str
    ticket_id: str | None
    created_at: AwareDatetime
    updated_at: AwareDatetime
    current_stage: Stage
    status: Lifecycle
    state: WorkflowState
    experiment_count: Annotated[int, Field(ge=0, le=8)]
    model_call_count: Annotated[int, Field(ge=0, le=20)]
    experiment_limit: Annotated[int, Field(ge=1, le=8)]
    model_call_limit: Annotated[int, Field(ge=1, le=20)]
    findings: Findings | None
    event_sequence: Annotated[int, Field(ge=0)]
    stages: tuple[StageExecutionView, ...] = ()


class Session(FrozenModel):
    id: UUID
    created_at: AwareDatetime
    expires_at: AwareDatetime


class Lease(FrozenModel):
    investigation_id: UUID
    stage: Stage
    operation_key: OperationKey
    lease_token: UUID
    fence: int
    expires_at: AwareDatetime
    status: Literal["running", "completed", "failed"]


class Evidence(FrozenModel):
    id: UUID
    investigation_id: UUID
    category: Category
    source_id: str
    payload: dict[str, JsonValue]
    source_reference: str | None
    historical_sha: str | None
    observed_at: AwareDatetime
    recorded_at: AwareDatetime
    content_hash: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    provenance: dict[str, JsonValue]
    trust: Literal["untrusted_data", "host_assertion"]
    execution_id: UUID | None


class Event(FrozenModel):
    id: UUID
    investigation_id: UUID
    sequence: int
    actor: Actor
    stage: Stage | None
    event_type: EventType
    tool_name: str | None
    payload: dict[str, JsonValue]
    created_at: AwareDatetime
    evidence_ids: tuple[UUID, ...]


class EventPage(FrozenModel):
    events: tuple[Event, ...]
    next_after: int | None


class ToolExecution(FrozenModel):
    id: UUID
    investigation_id: UUID
    stage: Stage
    fence: int
    operation_key: OperationKey
    tool_name: str
    arguments: dict[str, JsonValue]
    arguments_hash: str
    status: Literal["running", "succeeded", "failed"]
    result: dict[str, JsonValue] | None
    evidence_ids: tuple[UUID, ...]
    started_at: AwareDatetime
    completed_at: AwareDatetime | None


class Reservation(FrozenModel):
    id: UUID
    investigation_id: UUID
    stage: Stage
    kind: Literal["experiment", "model"]
    ordinal: int
    operation_key: OperationKey
    execution_id: UUID | None
    provider: str | None
    model: str | None
    created_at: AwareDatetime
    completed_at: AwareDatetime | None
    input_tokens: Annotated[int, Field(ge=0)] | None
    output_tokens: Annotated[int, Field(ge=0)] | None
    outcome: Literal["reserved", "succeeded", "failed", "unknown"]


class VerifiedAssertion(FrozenModel):
    independently_verified: Literal[True]
    statement: ShortText
    evidence_ids: Annotated[tuple[UUID, ...], Field(min_length=1, max_length=128)]


class EscalationDraft(FrozenModel):
    title: Annotated[str, Field(min_length=1, max_length=200)]
    description: Annotated[str, Field(min_length=1, max_length=8000)]
    evidence_ids: Annotated[tuple[UUID, ...], Field(min_length=1, max_length=128)]


class ReviewDecision(FrozenModel):
    investigation_id: UUID
    decision: Literal["approved", "rejected"]
    reviewer_note: Annotated[str, Field(max_length=2000)]
    decided_at: AwareDatetime
    escalation_id: UUID | None
