"""Validated checkout request and response contracts."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

ReleaseId = Literal["v1.0", "v1.1"]
Cents = Annotated[int, Field(ge=0, le=100_000_000)]
Percent = Annotated[int, Field(ge=0, le=100)]


class QuoteRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    release: ReleaseId
    subtotal_cents: Cents
    discount_percent: Percent


class QuoteResponse(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    release: ReleaseId
    subtotal_cents: Cents
    discount_percent: Percent
    discount_cents: Cents
    discounted_subtotal_cents: Cents
    shipping_cents: Cents
    total_cents: Cents
