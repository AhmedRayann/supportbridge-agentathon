"""Independent expected results and comparisons for the USD shipping policy."""

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class PolicyExpectation:
    subtotal_cents: int
    discount_percent: int
    discount_cents: int
    discounted_subtotal_cents: int
    free_shipping_eligible: bool
    shipping_cents: int
    total_cents: int


@dataclass(frozen=True)
class PolicyComparison:
    expected: PolicyExpectation
    mismatched_fields: tuple[str, ...]

    @property
    def matches(self) -> bool:
        return not self.mismatched_fields


def expected_quote(subtotal_cents: int, discount_percent: int) -> PolicyExpectation:
    if type(subtotal_cents) is not int or not 0 <= subtotal_cents <= 100_000_000:
        raise ValueError("subtotal_cents must be an integer from 0 to 100000000")
    if type(discount_percent) is not int or not 0 <= discount_percent <= 100:
        raise ValueError("discount_percent must be an integer from 0 to 100")

    whole_discount, fraction = divmod(subtotal_cents * discount_percent, 100)
    discount_cents = whole_discount + int(fraction >= 50)
    merchandise_cents = subtotal_cents - discount_cents
    eligible = subtotal_cents >= 10_000
    shipping_cents = 0 if eligible else 750

    return PolicyExpectation(
        subtotal_cents=subtotal_cents,
        discount_percent=discount_percent,
        discount_cents=discount_cents,
        discounted_subtotal_cents=merchandise_cents,
        free_shipping_eligible=eligible,
        shipping_cents=shipping_cents,
        total_cents=merchandise_cents + shipping_cents,
    )


def compare_quote(
    subtotal_cents: int, discount_percent: int, observed: Mapping[str, object]
) -> PolicyComparison:
    """Check amounts against trusted inputs; check release provenance separately."""
    expected = expected_quote(subtotal_cents, discount_percent)
    fields = (
        "subtotal_cents",
        "discount_percent",
        "discount_cents",
        "discounted_subtotal_cents",
        "shipping_cents",
        "total_cents",
    )
    mismatched_fields = tuple(
        field
        for field in fields
        if type(observed.get(field)) is not int
        or observed.get(field) != getattr(expected, field)
    )
    return PolicyComparison(expected=expected, mismatched_fields=mismatched_fields)
