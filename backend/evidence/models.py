"""Source records, provenance and bounded retrieval contracts."""

import re
from datetime import date
from typing import Annotated, Literal, Self

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

TicketId = Annotated[str, Field(pattern=r"^TKT-[0-9]{4}$", max_length=8)]
DocumentId = Annotated[str, Field(pattern=r"^POL-[0-9]{3}$", max_length=7)]
OrderId = Annotated[str, Field(pattern=r"^ORD-[0-9]{4}$", max_length=8)]
EventId = Annotated[str, Field(pattern=r"^EVT-[0-9]{4}-[0-9]{2}$", max_length=11)]
Cents = Annotated[int, Field(ge=0, le=100_000_000)]
Percent = Annotated[int, Field(ge=0, le=100)]
Text = Annotated[str, Field(min_length=1, max_length=3000, pattern=r"\S")]
ResultLimit = Annotated[int, Field(ge=1, le=10)]


def _searchable_query(value: str) -> str:
    if any(ord(character) < 32 for character in value) or not re.search(
        r"[^\W_]", value, re.UNICODE
    ):
        raise ValueError(
            "Query must contain letters or numbers without control characters"
        )
    return value


SearchQuery = Annotated[
    str, Field(min_length=1, max_length=200), AfterValidator(_searchable_query)
]


class FrozenModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)


class SourceRecord(FrozenModel):
    synthetic: Literal[True] = True
    content_trust: Literal["untrusted_data"] = "untrusted_data"


class SupportNote(SourceRecord):
    source_type: Literal["support_note"] = "support_note"
    note_id: Annotated[str, Field(pattern=r"^NOTE-[0-9]{4}-[0-9]{2}$")]
    created_at: AwareDatetime
    kind: Literal["observation", "resolution", "request_for_information"]
    content: Text


class SupportTicket(SourceRecord):
    source_type: Literal["support_ticket"] = "support_ticket"
    ticket_id: TicketId
    product: Text
    title: Text
    created_at: AwareDatetime
    updated_at: AwareDatetime
    status: Literal["open", "resolved", "awaiting_details"]
    order_id: OrderId | None
    reported_release: Literal["v1.0", "v1.1"] | None
    promotion_label: Text | None
    reported_subtotal_cents: Cents | None
    reported_discount_percent: Percent | None
    reported_total_cents: Cents | None
    customer_message: Text
    support_notes: Annotated[tuple[SupportNote, ...], Field(max_length=20)]

    @model_validator(mode="after")
    def consistent_timestamps(self) -> Self:
        if self.updated_at < self.created_at or any(
            not self.created_at <= note.created_at <= self.updated_at
            for note in self.support_notes
        ):
            raise ValueError("Ticket and note timestamps are inconsistent")
        return self


class PolicySection(SourceRecord):
    source_type: Literal["policy_section"] = "policy_section"
    section_id: Annotated[str, Field(pattern=r"^POL-[0-9]{3}-S[1-9][0-9]?$")]
    number: Annotated[int, Field(ge=1, le=20)]
    title: Text
    content: Text


class PolicyDocument(SourceRecord):
    source_type: Literal["policy_document"] = "policy_document"
    document_id: DocumentId
    title: Text
    revision: Annotated[str, Field(min_length=1, max_length=30)]
    effective_from: date
    effective_until: date | None
    approval_status: Literal["approved", "draft", "superseded"]
    approved_at: AwareDatetime | None
    applies_to: Text
    sections: Annotated[tuple[PolicySection, ...], Field(min_length=1, max_length=20)]

    @model_validator(mode="after")
    def consistent_sections_and_dates(self) -> Self:
        if self.effective_until and self.effective_until < self.effective_from:
            raise ValueError("Invalid policy effective-date range")
        if self.approval_status == "approved" and self.approved_at is None:
            raise ValueError("Approved policy needs an approval timestamp")
        if [section.number for section in self.sections] != list(
            range(1, len(self.sections) + 1)
        ) or any(
            section.section_id != f"{self.document_id}-S{section.number}"
            for section in self.sections
        ):
            raise ValueError("Policy sections must have ordered, document-scoped IDs")
        return self


class PaymentEvent(SourceRecord):
    source_type: Literal["payment_event"] = "payment_event"
    event_id: EventId
    order_id: OrderId
    occurred_at: AwareDatetime
    amount_cents: Annotated[int, Field(gt=0, le=100_000_000)]
    currency: Literal["USD"]
    event_type: Literal["authorization", "capture", "refund", "void"]
    status: Literal["succeeded", "failed"]
    related_event_id: EventId | None


class EvidenceCorpus(FrozenModel):
    tickets: Annotated[tuple[SupportTicket, ...], Field(max_length=100)]
    policies: Annotated[tuple[PolicyDocument, ...], Field(max_length=30)]
    payment_events: Annotated[tuple[PaymentEvent, ...], Field(max_length=100)]

    @model_validator(mode="after")
    def valid_identifiers_and_links(self) -> Self:
        groups = (
            [ticket.ticket_id for ticket in self.tickets],
            [note.note_id for ticket in self.tickets for note in ticket.support_notes],
            [document.document_id for document in self.policies],
            [section.section_id for doc in self.policies for section in doc.sections],
            [event.event_id for event in self.payment_events],
        )
        if any(len(ids) != len(set(ids)) for ids in groups):
            raise ValueError("Source identifiers must be unique")
        orders = {ticket.order_id for ticket in self.tickets if ticket.order_id}
        events = {event.event_id: event for event in self.payment_events}
        for event in self.payment_events:
            if event.order_id not in orders:
                raise ValueError("Payment event has an unknown order reference")
            parent = events.get(event.related_event_id)
            if event.related_event_id:
                if (
                    parent is None
                    or parent.order_id != event.order_id
                    or parent.currency != event.currency
                    or parent.occurred_at > event.occurred_at
                    or parent.status != "succeeded"
                ):
                    raise ValueError("Payment event link is inconsistent")
                expected_type = (
                    "capture" if event.event_type == "refund" else "authorization"
                )
                if parent.event_type != expected_type:
                    raise ValueError("Payment event link has an invalid event type")
            if event.event_type == "authorization" and parent is not None:
                raise ValueError("Authorization cannot reference another event")
            if event.event_type in {"refund", "void"} and parent is None:
                raise ValueError("Refund/void needs its recorded parent event")
            if parent and event.event_type in {"refund", "void"}:
                if event.amount_cents > parent.amount_cents:
                    raise ValueError("Refund/void exceeds its referenced event amount")
        return self


class TicketMatch(FrozenModel):
    score: Annotated[int, Field(ge=1)]
    ticket: SupportTicket


class TicketSearchResult(FrozenModel):
    query: str
    limit: int
    matches: tuple[TicketMatch, ...]


class TicketResult(FrozenModel):
    ticket_id: TicketId
    ticket: SupportTicket | None


class PolicyMatch(FrozenModel):
    score: Annotated[int, Field(ge=1)]
    document: PolicyDocument
    matched_section_ids: tuple[str, ...]


class PolicySearchResult(FrozenModel):
    query: str
    limit: int
    matches: tuple[PolicyMatch, ...]


class PolicyResult(FrozenModel):
    document_id: DocumentId
    document: PolicyDocument | None


class OrderPaymentEvents(FrozenModel):
    order_id: OrderId
    events: tuple[PaymentEvent, ...]
    coverage: Literal["recorded_events_only"] = "recorded_events_only"
