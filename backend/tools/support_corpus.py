"""Retrieve packaged synthetic source records; record content is untrusted data."""

import re
from collections.abc import Iterable, Iterator

from pydantic import BaseModel, validate_call

if __package__ == "tools":
    from evidence import models
    from evidence.store import load_corpus
else:
    from ..evidence import models
    from ..evidence.store import load_corpus

__all__ = [
    "search_support_tickets",
    "get_support_ticket",
    "search_policy_documents",
    "get_policy_document",
    "get_order_payment_events",
]


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[^\W_]+", text.casefold(), re.UNICODE))


def _text_values(value: object) -> Iterator[str]:
    if isinstance(value, str) or type(value) is int:
        yield str(value)
    elif isinstance(value, dict):
        for item in value.values():
            yield from _text_values(item)
    elif isinstance(value, list):
        for item in value:
            yield from _text_values(item)


def _record_tokens(record: BaseModel) -> set[str]:
    return _tokens(" ".join(_text_values(record.model_dump(mode="json"))))


def _rank[Record: BaseModel](
    query: str, records: Iterable[tuple[str, Record]], limit: int
) -> list[tuple[int, str, Record]]:
    terms = _tokens(query)
    ranked = [
        (len(terms & _record_tokens(record)), source_id, record)
        for source_id, record in records
    ]
    return sorted(
        (item for item in ranked if item[0] > 0), key=lambda item: (-item[0], item[1])
    )[:limit]


@validate_call(config={"strict": True})
def search_support_tickets(
    query: models.SearchQuery, limit: models.ResultLimit = 5
) -> models.TicketSearchResult:
    """Search ticket content and metadata using bounded lexical relevance."""
    ranked = _rank(query, ((t.ticket_id, t) for t in load_corpus().tickets), limit)
    return models.TicketSearchResult(
        query=query,
        limit=limit,
        matches=tuple(
            models.TicketMatch(score=score, ticket=t) for score, _, t in ranked
        ),
    )


@validate_call(config={"strict": True})
def get_support_ticket(ticket_id: models.TicketId) -> models.TicketResult:
    """Read a ticket by exact source ID; missing records remain absent."""
    ticket = next((t for t in load_corpus().tickets if t.ticket_id == ticket_id), None)
    return models.TicketResult(ticket_id=ticket_id, ticket=ticket)


@validate_call(config={"strict": True})
def search_policy_documents(
    query: models.SearchQuery, limit: models.ResultLimit = 5
) -> models.PolicySearchResult:
    """Search policy text and metadata; preserve approval and effective dates."""
    terms = _tokens(query)
    ranked = _rank(query, ((p.document_id, p) for p in load_corpus().policies), limit)
    return models.PolicySearchResult(
        query=query,
        limit=limit,
        matches=tuple(
            models.PolicyMatch(
                score=score,
                document=document,
                matched_section_ids=tuple(
                    section.section_id
                    for section in document.sections
                    if terms & _record_tokens(section)
                ),
            )
            for score, _, document in ranked
        ),
    )


@validate_call(config={"strict": True})
def get_policy_document(document_id: models.DocumentId) -> models.PolicyResult:
    """Read a policy revision and its sections without asserting applicability."""
    document = next(
        (p for p in load_corpus().policies if p.document_id == document_id), None
    )
    return models.PolicyResult(document_id=document_id, document=document)


@validate_call(config={"strict": True})
def get_order_payment_events(order_id: models.OrderId) -> models.OrderPaymentEvents:
    """Return recorded events in timestamp/ID order, without a charge verdict."""
    events = tuple(
        sorted(
            (
                event
                for event in load_corpus().payment_events
                if event.order_id == order_id
            ),
            key=lambda event: (event.occurred_at, event.event_id),
        )
    )
    return models.OrderPaymentEvents(order_id=order_id, events=events)
