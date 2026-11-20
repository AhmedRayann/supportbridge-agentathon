from dataclasses import asdict

import pytest

from backend.oracle.shipping_contract import compare_quote, expected_quote
from backend.sandbox.models import QuoteRequest
from backend.sandbox.releases.v1_0 import calculate_quote


@pytest.mark.parametrize(
    "subtotal,percent,discount,shipping,total",
    [
        (11_000, 15, 1_650, 0, 9_350),
        (11_000, 5, 550, 0, 10_450),
        (8_000, 15, 1_200, 750, 7_550),
        (10_000, 15, 1_500, 0, 8_500),
        (9_999, 15, 1_500, 750, 9_249),
        (10_001, 15, 1_500, 0, 8_501),
        (1, 49, 0, 750, 751),
        (1, 50, 1, 750, 750),
        (8_000, 100, 8_000, 750, 750),
        (10_000, 100, 10_000, 0, 0),
    ],
)
def test_oracle_expected_policy(
    subtotal: int, percent: int, discount: int, shipping: int, total: int
) -> None:
    expected = expected_quote(subtotal, percent)
    assert expected.discount_cents == discount
    assert expected.discounted_subtotal_cents == subtotal - discount
    assert expected.free_shipping_eligible == (subtotal >= 10_000)
    assert expected.shipping_cents == shipping
    assert expected.total_cents == total


@pytest.mark.parametrize(
    "subtotal", [0, 1, 101, 8_000, 9_999, 10_000, 10_001, 100_000_000]
)
def test_v1_0_agrees_with_oracle_across_discount_range(subtotal: int) -> None:
    for percent in range(101):
        actual = calculate_quote(
            QuoteRequest(
                release="v1.0", subtotal_cents=subtotal, discount_percent=percent
            )
        )
        result = compare_quote(subtotal, percent, actual.model_dump())
        assert result.matches, (subtotal, percent, result.mismatched_fields)


@pytest.mark.parametrize(
    "field",
    [
        "subtotal_cents",
        "discount_percent",
        "discount_cents",
        "discounted_subtotal_cents",
        "shipping_cents",
        "total_cents",
    ],
)
def test_oracle_detects_each_incorrect_amount(field: str) -> None:
    observed = asdict(expected_quote(11_000, 15))
    observed[field] += 1
    result = compare_quote(11_000, 15, observed)
    assert not result.matches
    assert result.mismatched_fields == (field,)


@pytest.mark.parametrize("invalid", [None, True, 9350.0, "9350"])
def test_oracle_rejects_missing_or_malformed_observed_total(invalid: object) -> None:
    observed = asdict(expected_quote(11_000, 15))
    observed["total_cents"] = invalid
    assert not compare_quote(11_000, 15, observed).matches


def test_oracle_reports_missing_fields() -> None:
    assert compare_quote(11_000, 15, {}).mismatched_fields == (
        "subtotal_cents",
        "discount_percent",
        "discount_cents",
        "discounted_subtotal_cents",
        "shipping_cents",
        "total_cents",
    )


@pytest.mark.parametrize(
    "subtotal,percent",
    [
        (-1, 15),
        (100_000_001, 15),
        (True, 15),
        (1.0, 15),
        (100, -1),
        (100, 101),
        (100, False),
        (100, "15"),
    ],
)
def test_oracle_validates_trusted_inputs(subtotal: object, percent: object) -> None:
    with pytest.raises(ValueError):
        expected_quote(subtotal, percent)
