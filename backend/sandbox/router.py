"""HTTP interface for supported checkout releases."""

from collections.abc import Callable

from fastapi import APIRouter, Response

from .models import QuoteRequest, QuoteResponse, ReleaseId
from .releases import v1_0, v1_1

router = APIRouter(prefix="/svc/api/sandbox", tags=["sandbox"])

_QUOTE_CALCULATORS: dict[ReleaseId, Callable[[QuoteRequest], QuoteResponse]] = {
    "v1.0": v1_0.calculate_quote,
    "v1.1": v1_1.calculate_quote,
}


@router.post("/quote", response_model=QuoteResponse)
def quote(request: QuoteRequest, response: Response) -> QuoteResponse:
    response.headers["Cache-Control"] = "no-store"
    return _QUOTE_CALCULATORS[request.release](request)
