"""Trusted tool recording boundary; no agents, diagnoses or scripted tool order."""

import asyncio
import inspect
from datetime import UTC, datetime
from functools import wraps
from uuid import UUID

from pydantic import ValidationError, validate_call

from . import models as m
from .repository import Store

if __package__ == "storage":
    from sandbox.models import Cents, Percent, QuoteRequest, ReleaseId
    from tools import experiments, github_read, support_corpus
    from tools.investigation_models import FrozenModel
else:
    from ..sandbox.models import Cents, Percent, QuoteRequest, ReleaseId
    from ..tools import experiments, github_read, support_corpus
    from ..tools.investigation_models import FrozenModel


class RecordedToolResult(FrozenModel):
    execution_id: UUID
    result: dict
    evidence_ids: tuple[UUID, ...]
    replayed: bool


READ_TOOLS = {
    name: getattr(module, name)
    for module in (support_corpus, github_read)
    for name in module.__all__
}


def evidence_records(name, result, execution_id):
    """Project genuine source references; the full tool envelope is always retained."""
    now = datetime.now(UTC)
    records = [
        {
            "category": "tool_result",
            "source_id": str(execution_id),
            "payload": result,
            "observed_at": now,
            "provenance": {"tool_name": name},
        }
    ]

    def add(category, source_id, payload, **metadata):
        records.append(
            {
                "category": category,
                "source_id": source_id,
                "payload": payload,
                "observed_at": now,
                **metadata,
            }
        )

    if name in ("get_support_ticket", "search_support_tickets"):
        tickets = (
            [result.get("ticket")]
            if name.startswith("get_")
            else [x["ticket"] for x in result["matches"]]
        )
        for ticket in filter(None, tickets):
            add("support_ticket", ticket["ticket_id"], ticket)
    elif name in ("get_policy_document", "search_policy_documents"):
        documents = (
            [result.get("document")]
            if name.startswith("get_")
            else [x["document"] for x in result["matches"]]
        )
        for document in filter(None, documents):
            metadata = {
                key: value for key, value in document.items() if key != "sections"
            }
            for section in document["sections"]:
                add(
                    "policy_section",
                    section["section_id"],
                    {"document": metadata, "section": section},
                )
    elif name == "get_order_payment_events":
        for event in result["events"]:
            add(
                "payment_event",
                event["event_id"],
                event,
                provenance={"coverage": result["coverage"]},
            )
    elif name in ("get_checkout_source", "compare_checkout_sources"):
        sources = (
            [result.get("source")] if name.startswith("get_") else result["sources"]
        )
        if name == "compare_checkout_sources" and result["status"] == "success":
            add("github_comparison", ":".join(s["commit_sha"] for s in sources), result)
        for source in filter(None, sources):
            add(
                "github_source",
                f"{source['commit_sha']}:{source['path']}",
                source,
                reference=source["permalink"],
                sha=source["commit_sha"],
                observed_at=datetime.fromisoformat(
                    source["retrieved_at"].replace("Z", "+00:00")
                ),
                provenance={
                    "retrieved_at": source["retrieved_at"],
                    "origin": "github_rest",
                },
            )
    elif name == "run_checkout_quote":
        add(
            "checkout_observation",
            str(execution_id),
            result,
            reference=result["url"],
            observed_at=datetime.fromisoformat(
                result["executed_at"].replace("Z", "+00:00")
            ),
            provenance={"executed_at": result["executed_at"]},
        )
    return records


class ExecutionContext:
    def __init__(self, store: Store, session_id: UUID, lease: m.Lease):
        self.store, self.session_id, self.lease = store, session_id, lease

    def tools_for(self, operation_key: str) -> dict:
        "Bind one durable host-generated action key; infrastruct"
        "ure is not model input."

        def bind(name, function):
            @wraps(function)
            async def invoke(*args, **kwargs):
                arguments = inspect.signature(function).bind(*args, **kwargs)
                arguments.apply_defaults()
                return await self._execute(
                    name, dict(arguments.arguments), operation_key
                )

            invoke.__signature__ = inspect.signature(function).replace(
                return_annotation=RecordedToolResult
            )
            invoke.__annotations__ = {
                **function.__annotations__,
                "return": RecordedToolResult,
            }
            return invoke

        tools = {name: bind(name, function) for name, function in READ_TOOLS.items()}

        @validate_call(config={"strict": True})
        async def run_checkout_quote(
            release: ReleaseId, subtotal_cents: Cents, discount_percent: Percent
        ) -> RecordedToolResult:
            request = QuoteRequest(
                release=release,
                subtotal_cents=subtotal_cents,
                discount_percent=discount_percent,
            )
            return await self._execute(
                "run_checkout_quote", request.model_dump(mode="json"), operation_key
            )

        tools["run_checkout_quote"] = run_checkout_quote
        return tools

    async def _execute(
        self, name: str, arguments: dict, key: str
    ) -> RecordedToolResult:
        execution, fresh = await asyncio.to_thread(
            self.store.begin_tool, self.session_id, self.lease, name, arguments, key
        )
        if not fresh:
            return RecordedToolResult(
                execution_id=execution.id,
                result=execution.result,
                evidence_ids=execution.evidence_ids,
                replayed=True,
            )
        reservation = None

        async def reserve(maximum):
            nonlocal reservation
            if maximum != 8:
                return False
            reservation = await asyncio.to_thread(
                self.store.reserve,
                self.session_id,
                self.lease,
                "experiment",
                key,
                execution_id=execution.id,
            )
            return reservation is not None

        try:
            if name == "run_checkout_quote":
                observed = await experiments.run_checkout_quote(
                    **arguments, reserve_experiment=reserve
                )
            else:
                function = READ_TOOLS[name]
                observed = (
                    await function(**arguments)
                    if inspect.iscoroutinefunction(function)
                    else await asyncio.to_thread(function, **arguments)
                )
            result = observed.model_dump(mode="json")
            failed = result.get("status") in (
                "error",
                "blocked",
                "http_error",
                "environment_unavailable",
                "invalid_response",
            )
            records = evidence_records(name, result, execution.id)
        except Exception as error:
            # Never persist exception strings, provider configuration or credentials.
            code = (
                "invalid_tool_arguments"
                if isinstance(error, (ValidationError, ValueError, TypeError))
                else "tool_failed"
            )
            result = {
                "status": "error",
                "error": {"code": code, "detail": "Tool execution failed"},
            }
            failed = True
            records = evidence_records("failed_tool", result, execution.id)
        if reservation:
            await asyncio.to_thread(
                self.store.record_usage,
                self.session_id,
                self.lease,
                reservation.id,
                outcome="failed" if failed else "succeeded",
            )
        ids = await asyncio.to_thread(
            self.store.finish_tool,
            self.session_id,
            self.lease,
            execution,
            result,
            records,
            failed=failed,
        )
        return RecordedToolResult(
            execution_id=execution.id, result=result, evidence_ids=ids, replayed=False
        )
