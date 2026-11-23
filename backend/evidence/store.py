"""Load only the packaged, validated evidence corpus."""

from functools import lru_cache
from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from .models import EvidenceCorpus, PaymentEvent, PolicyDocument, SupportTicket

_DATA_DIRECTORY = Path(__file__).resolve().parent / "data"


class EvidenceDataError(RuntimeError):
    """An operator must repair the packaged evidence before retrieval can run."""


@lru_cache(maxsize=1)
def load_corpus() -> EvidenceCorpus:
    try:
        tickets = TypeAdapter(tuple[SupportTicket, ...]).validate_json(
            (_DATA_DIRECTORY / "support_tickets.json").read_bytes()
        )
        policies = TypeAdapter(tuple[PolicyDocument, ...]).validate_json(
            (_DATA_DIRECTORY / "policy_documents.json").read_bytes()
        )
        events = TypeAdapter(tuple[PaymentEvent, ...]).validate_json(
            (_DATA_DIRECTORY / "payment_events.json").read_bytes()
        )
        return EvidenceCorpus(tickets=tickets, policies=policies, payment_events=events)
    except (OSError, ValidationError):
        raise EvidenceDataError(
            "Packaged support evidence is unavailable or invalid"
        ) from None
