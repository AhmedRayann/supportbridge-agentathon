"""Checkout quote calculation for release v1.0."""

from ..models import QuoteRequest, QuoteResponse


def calculate_quote(request: QuoteRequest) -> QuoteResponse:
    discount_cents = (request.subtotal_cents * request.discount_percent + 50) // 100
    discounted_subtotal_cents = request.subtotal_cents - discount_cents
    shipping_cents = 0 if request.subtotal_cents >= 10_000 else 750

    return QuoteResponse(
        release="v1.0",
        subtotal_cents=request.subtotal_cents,
        discount_percent=request.discount_percent,
        discount_cents=discount_cents,
        discounted_subtotal_cents=discounted_subtotal_cents,
        shipping_cents=shipping_cents,
        total_cents=discounted_subtotal_cents + shipping_cents,
    )
