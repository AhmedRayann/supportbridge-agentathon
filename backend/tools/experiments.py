"""Execute a caller-selected quote against the configured trusted sandbox."""

import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from pydantic import ValidationError, validate_call

from . import _http
from ._config import sandbox_origin
from .investigation_models import (
    CheckoutObservation,
    QuoteRequest,
    QuoteResponse,
    ReleaseId,
    ToolError,
)

if __package__ == "tools":
    from sandbox.models import Cents, Percent
else:
    from ..sandbox.models import Cents, Percent

__all__ = ["run_checkout_quote"]
MAX_EXPERIMENTS_PER_INVESTIGATION = 8
QUOTE_PATH = "/svc/api/sandbox/quote"


@validate_call(config={"strict": True})
async def run_checkout_quote(
    release: ReleaseId,
    subtotal_cents: Cents,
    discount_percent: Percent,
    *,
    reserve_experiment: Callable[[int], Awaitable[bool]] | None = None,
) -> CheckoutObservation:
    """Execute one quote. The optional budget reservation is supplied by the host."""
    request = QuoteRequest(
        release=release,
        subtotal_cents=subtotal_cents,
        discount_percent=discount_percent,
    )
    url = sandbox_origin() + QUOTE_PATH
    executed_at = datetime.now(UTC)
    start = time.perf_counter()
    error = None
    status = "success"
    http_status = None
    response = None
    if reserve_experiment is not None:
        try:
            reserved = await reserve_experiment(MAX_EXPERIMENTS_PER_INVESTIGATION)
            if reserved is not True:
                error = ToolError(
                    code="budget_exhausted", detail="Experiment reservation denied"
                )
        except Exception:
            error = ToolError(
                code="budget_unavailable", detail="Experiment reservation unavailable"
            )
        if error:
            status = "blocked"
    if error is None:
        raw = await _http.request(
            "POST",
            url,
            headers={"Accept": "application/json"},
            payload=request.model_dump(mode="json"),
        )
        http_status, error = raw.status, raw.error
        if error:
            status = (
                "environment_unavailable"
                if error.code in {"timeout", "environment_unavailable"}
                else "http_error"
            )
        else:
            try:
                response = QuoteResponse.model_validate_json(raw.body)
                if any(
                    getattr(response, field) != value
                    for field, value in request.model_dump().items()
                ):
                    raise ValueError
            except (ValueError, ValidationError, RecursionError):
                response = None
                error = ToolError(
                    code="invalid_response",
                    detail="Quote response failed schema or input-identity validation",
                )
                status = "invalid_response"
    return CheckoutObservation(
        status=status,
        request=request,
        url=url,
        executed_at=executed_at,
        elapsed_ms=round((time.perf_counter() - start) * 1000, 3),
        http_status=http_status,
        response=response,
        error=error,
    )
