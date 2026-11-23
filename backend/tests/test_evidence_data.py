import json
from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from backend.evidence import models, store
from backend.tools.support_corpus import get_order_payment_events, get_support_ticket


@pytest.fixture(autouse=True)
def clear_evidence_cache():
    store.load_corpus.cache_clear()
    yield
    store.load_corpus.cache_clear()


@pytest.mark.parametrize(
    "filename,model,count",
    [
        ("support_tickets.json", models.SupportTicket, 6),
        ("policy_documents.json", models.PolicyDocument, 3),
        ("payment_events.json", models.PaymentEvent, 13),
    ],
)
def test_packaged_json_validates_actual_records(filename: str, model: type, count: int):
    records = TypeAdapter(tuple[model, ...]).validate_json(
        (store._DATA_DIRECTORY / filename).read_bytes()
    )
    assert len(records) == count
    assert all(
        record.synthetic and record.content_trust == "untrusted_data"
        for record in records
    )
    assert all(record.source_type for record in records)


def test_unique_sources_and_valid_order_relationships():
    corpus = store.load_corpus()
    ids = [
        *(ticket.ticket_id for ticket in corpus.tickets),
        *(note.note_id for ticket in corpus.tickets for note in ticket.support_notes),
        *(document.document_id for document in corpus.policies),
        *(
            section.section_id
            for document in corpus.policies
            for section in document.sections
        ),
        *(event.event_id for event in corpus.payment_events),
    ]
    assert len(ids) == len(set(ids))
    orders = {ticket.order_id for ticket in corpus.tickets if ticket.order_id}
    assert len(orders) == 5
    assert {event.order_id for event in corpus.payment_events} == orders
    assert sum(len(document.sections) for document in corpus.policies) == 9
    assert (
        sum(path.stat().st_size for path in store._DATA_DIRECTORY.glob("*.json"))
        < 32_000
    )


@pytest.mark.parametrize("category", ["tickets", "policies", "payment_events"])
def test_duplicate_source_ids_are_rejected(category: str):
    data = store.load_corpus().model_dump(mode="json")
    data[category].append(data[category][0])
    with pytest.raises(ValidationError):
        models.EvidenceCorpus.model_validate_json(json.dumps(data))


@pytest.mark.parametrize(
    "change",
    [
        "note_id",
        "section_id",
        "order_reference",
        "event_reference",
        "parent_order",
        "parent_type",
        "parent_timestamp",
        "refund_amount",
        "amount_type",
        "negative_amount",
        "currency",
        "ticket_timestamp",
        "approval",
        "effective_dates",
        "extra_diagnosis",
        "blank_content",
    ],
)
def test_invalid_data_and_relationships_are_rejected(change: str):
    data = store.load_corpus().model_dump(mode="json")
    if change == "note_id":
        data["tickets"][1]["support_notes"][0]["note_id"] = "NOTE-1001-01"
    elif change == "section_id":
        data["policies"][1]["sections"][0]["section_id"] = "POL-100-S1"
    elif change == "order_reference":
        data["payment_events"][0]["order_id"] = "ORD-9999"
    elif change == "event_reference":
        data["payment_events"][1]["related_event_id"] = "EVT-9999-01"
    elif change == "parent_order":
        data["payment_events"][1]["related_event_id"] = "EVT-3201-01"
    elif change == "parent_type":
        data["payment_events"][5]["related_event_id"] = "EVT-3201-01"
    elif change == "parent_timestamp":
        data["payment_events"][0]["occurred_at"] = "2026-11-22T09:03:00Z"
    elif change == "refund_amount":
        data["payment_events"][5]["amount_cents"] = 4201
    elif change == "amount_type":
        data["payment_events"][0]["amount_cents"] = 10100.0
    elif change == "negative_amount":
        data["payment_events"][0]["amount_cents"] = -1
    elif change == "currency":
        data["payment_events"][0]["currency"] = "EUR"
    elif change == "ticket_timestamp":
        data["tickets"][0]["updated_at"] = "2026-11-20T09:10:00Z"
    elif change == "approval":
        data["policies"][0]["approved_at"] = None
    elif change == "effective_dates":
        data["policies"][0]["effective_until"] = "2026-10-01"
    elif change == "extra_diagnosis":
        data["tickets"][0]["root_cause"] = "test-only injected answer"
    elif change == "blank_content":
        data["policies"][0]["sections"][0]["content"] = "  "
    with pytest.raises(ValidationError):
        models.EvidenceCorpus.model_validate_json(json.dumps(data))


def test_primary_allegation_and_recorded_capture_are_distinct():
    ticket = get_support_ticket("TKT-1001").ticket
    events = get_order_payment_events(ticket.order_id).events
    assert "thinks the payment was duplicated" in ticket.customer_message
    captures = [
        e for e in events if e.event_type == "capture" and e.status == "succeeded"
    ]
    assert len(captures) == 1
    assert captures[0].amount_cents == ticket.reported_total_cents == 10100
    assert len(events) == 2
    assert events[0].event_type == "authorization"


def test_historical_duplicate_captures_and_refund_are_underlying_records():
    events = get_order_payment_events("ORD-3201").events
    captures = [
        e for e in events if e.event_type == "capture" and e.status == "succeeded"
    ]
    assert len(captures) == 2
    assert [event.amount_cents for event in captures] == [4200, 4200]
    refund = next(e for e in events if e.event_type == "refund")
    assert refund.related_event_id == captures[1].event_id
    assert refund.amount_cents == 4200
    assert (
        "ORD-3201 only"
        in get_support_ticket("TKT-1002").ticket.support_notes[0].content
    )


@pytest.mark.parametrize(
    "order,amount", [("ORD-4102", 7550), ("ORD-4103", 10450), ("ORD-4104", 10000)]
)
def test_other_orders_authorizations_and_failures(order: str, amount: int):
    events = get_order_payment_events(order).events
    successful = [
        e for e in events if e.event_type == "capture" and e.status == "succeeded"
    ]
    assert len(successful) == 1 and successful[0].amount_cents == amount
    authorization = next(e for e in events if e.event_type == "authorization")
    assert successful[0].related_event_id == authorization.event_id
    if order == "ORD-4104":
        assert events[0].event_type == "capture" and events[0].status == "failed"


def test_missing_ticket_details_remain_unknown():
    ticket = get_support_ticket("TKT-1004").ticket
    assert ticket.status == "awaiting_details"
    assert ticket.order_id is None and ticket.reported_release is None
    assert ticket.reported_subtotal_cents is None
    assert (
        ticket.reported_discount_percent is None and ticket.reported_total_cents is None
    )


def test_approved_policy_sections_preserve_business_rules():
    policies = {p.document_id: p for p in store.load_corpus().policies}
    assert all(
        p.approval_status == "approved" and p.approved_at for p in policies.values()
    )
    assert policies["POL-100"].sections[0].section_id == "POL-100-S1"
    assert "before promotional discounts" in policies["POL-100"].sections[0].content
    assert "750 USD cents" in policies["POL-100"].sections[1].content
    assert "half-cent ties rounded up" in policies["POL-110"].sections[1].content
    assert "not automatically two charges" in policies["POL-200"].sections[0].content
    assert "absence alone does not establish" in policies["POL-200"].sections[2].content


@pytest.mark.parametrize("damage", ["missing", "invalid_json", "invalid_schema"])
def test_packaged_data_failure_is_clear_and_not_a_fake_empty_result(
    monkeypatch, tmp_path: Path, damage: str
):
    for source in store._DATA_DIRECTORY.glob("*.json"):
        (tmp_path / source.name).write_bytes(source.read_bytes())
    target = tmp_path / "support_tickets.json"
    if damage == "missing":
        target.unlink()
    elif damage == "invalid_json":
        target.write_text("{", encoding="utf-8")
    else:
        target.write_text('[{"secret_internal_path":"not a record"}]', encoding="utf-8")
    monkeypatch.setattr(store, "_DATA_DIRECTORY", tmp_path)
    with pytest.raises(
        store.EvidenceDataError, match="unavailable or invalid"
    ) as error:
        store.load_corpus()
    assert str(tmp_path) not in str(error.value) and "secret_internal_path" not in str(
        error.value
    )


def test_module_relative_loading_outside_repository_cwd(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    assert len(store.load_corpus().tickets) == 6
