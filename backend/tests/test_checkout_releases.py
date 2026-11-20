import subprocess
from pathlib import Path

import httpx
import pytest

from backend.oracle.shipping_contract import compare_quote, expected_quote
from backend.sandbox.models import QuoteRequest, ReleaseId
from backend.sandbox.releases import v1_0, v1_1

# subtotal, percent, discount, discounted merchandise, v1.0 shipping, v1.1 shipping
RELEASE_CASES = [
    (11_000, 15, 1_650, 9_350, 0, 750),
    (11_000, 5, 550, 10_450, 0, 0),
    (8_000, 15, 1_200, 6_800, 750, 750),
    (10_000, 15, 1_500, 8_500, 0, 750),
    (9_999, 15, 1_500, 8_499, 750, 750),
    (10_001, 15, 1_500, 8_501, 0, 750),
    (9_999, 0, 0, 9_999, 750, 750),
    (10_000, 0, 0, 10_000, 0, 0),
    (10_001, 0, 0, 10_001, 0, 0),
    (12_499, 20, 2_500, 9_999, 0, 750),
    (12_500, 20, 2_500, 10_000, 0, 0),
    (12_501, 20, 2_500, 10_001, 0, 0),
    (10_100, 1, 101, 9_999, 0, 750),
    (10_101, 1, 101, 10_000, 0, 0),
    (19_999, 50, 10_000, 9_999, 0, 750),
    (20_000, 50, 10_000, 10_000, 0, 0),
    (20_001, 50, 10_001, 10_000, 0, 0),
    (0, 0, 0, 0, 750, 750),
    (0, 100, 0, 0, 750, 750),
    (1, 49, 0, 1, 750, 750),
    (1, 50, 1, 0, 750, 750),
    (3, 50, 2, 1, 750, 750),
    (101, 50, 51, 50, 750, 750),
    (8_000, 100, 8_000, 0, 750, 750),
    (10_000, 100, 10_000, 0, 0, 750),
    (100_000_000, 0, 0, 100_000_000, 0, 0),
    (100_000_000, 100, 100_000_000, 0, 0, 750),
]


@pytest.mark.anyio
@pytest.mark.parametrize("release", ["v1.0", "v1.1"])
@pytest.mark.parametrize(
    "subtotal,percent,discount,merchandise,shipping_v1_0,shipping_v1_1", RELEASE_CASES
)
async def test_both_releases_calculation_api_and_oracle(
    client: httpx.AsyncClient,
    release: ReleaseId,
    subtotal: int,
    percent: int,
    discount: int,
    merchandise: int,
    shipping_v1_0: int,
    shipping_v1_1: int,
) -> None:
    request = QuoteRequest(
        release=release, subtotal_cents=subtotal, discount_percent=percent
    )
    calculator = v1_0.calculate_quote if release == "v1.0" else v1_1.calculate_quote
    shipping = shipping_v1_0 if release == "v1.0" else shipping_v1_1
    expected = {
        **request.model_dump(),
        "discount_cents": discount,
        "discounted_subtotal_cents": merchandise,
        "shipping_cents": shipping,
        "total_cents": merchandise + shipping,
    }
    assert calculator(request).model_dump() == expected

    response = await client.post("/svc/api/sandbox/quote", json=request.model_dump())
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.headers["cache-control"] == "no-store"
    actual = response.json()
    assert actual == expected
    assert all(type(value) is int for key, value in actual.items() if key != "release")

    comparison = compare_quote(subtotal, percent, actual)
    mismatch = release == "v1.1" and shipping_v1_0 != shipping_v1_1
    assert comparison.matches is not mismatch
    assert comparison.mismatched_fields == (
        ("shipping_cents", "total_cents") if mismatch else ()
    )


@pytest.mark.parametrize("release", ["v1.0", "v1.1"])
@pytest.mark.parametrize(
    "subtotal",
    [
        0,
        1,
        3,
        101,
        8_000,
        9_999,
        10_000,
        10_001,
        10_101,
        11_000,
        12_500,
        20_000,
        99_999_999,
        100_000_000,
    ],
)
def test_release_behavior_across_all_discount_percentages(
    release: ReleaseId, subtotal: int
) -> None:
    calculator = v1_0.calculate_quote if release == "v1.0" else v1_1.calculate_quote
    for percent in range(101):
        policy = expected_quote(subtotal, percent)
        actual = calculator(
            QuoteRequest(
                release=release, subtotal_cents=subtotal, discount_percent=percent
            )
        )
        shipping = policy.shipping_cents
        if release == "v1.1":
            shipping = 750 if policy.discounted_subtotal_cents < 10_000 else 0
        assert actual.release == release
        assert actual.discount_cents == policy.discount_cents
        assert actual.discounted_subtotal_cents == policy.discounted_subtotal_cents
        assert actual.shipping_cents == shipping
        assert actual.total_cents == policy.discounted_subtotal_cents + shipping

        comparison = compare_quote(subtotal, percent, actual.model_dump())
        mismatch = (
            release == "v1.1"
            and policy.free_shipping_eligible
            and policy.discounted_subtotal_cents < 10_000
        )
        assert comparison.matches is not mismatch
        assert comparison.mismatched_fields == (
            ("shipping_cents", "total_cents") if mismatch else ()
        )


@pytest.mark.parametrize(
    "source",
    ["backend/sandbox/releases/v1_0.py", "backend/oracle/shipping_contract.py"],
)
def test_preserved_source_matches_v1_0_baseline(source: str) -> None:
    root = Path(__file__).resolve().parents[2]
    baseline = subprocess.check_output(
        [
            "git",
            "-c",
            f"safe.directory={root.as_posix()}",
            "show",
            f"a4eeea911604494f693e027cdaca5f2da2f78a7e:{source}",
        ],
        cwd=root,
    )
    assert (root / source).read_bytes().replace(b"\r\n", b"\n") == baseline.replace(
        b"\r\n", b"\n"
    )
