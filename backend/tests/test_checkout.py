import json
import subprocess
import sys
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from backend.oracle.shipping_contract import compare_quote
from backend.sandbox.models import QuoteRequest, ReleaseId
from backend.sandbox.releases.v1_0 import calculate_quote

# subtotal, percentage, discount, merchandise after discount, shipping, total
QUOTE_CASES = [
    (11_000, 15, 1_650, 9_350, 0, 9_350),
    (11_000, 5, 550, 10_450, 0, 10_450),
    (8_000, 15, 1_200, 6_800, 750, 7_550),
    (10_000, 15, 1_500, 8_500, 0, 8_500),
    (9_999, 15, 1_500, 8_499, 750, 9_249),
    (10_001, 15, 1_500, 8_501, 0, 8_501),
    (8_000, 0, 0, 8_000, 750, 8_750),
    (10_000, 0, 0, 10_000, 0, 10_000),
    (8_000, 100, 8_000, 0, 750, 750),
    (10_000, 100, 10_000, 0, 0, 0),
    (0, 0, 0, 0, 750, 750),
    (0, 100, 0, 0, 750, 750),
    (1, 49, 0, 1, 750, 751),
    (1, 50, 1, 0, 750, 750),
    (3, 50, 2, 1, 750, 751),
    (101, 50, 51, 50, 750, 800),
    (100_000_000, 0, 0, 100_000_000, 0, 100_000_000),
    (100_000_000, 100, 100_000_000, 0, 0, 0),
]


def quote_body(
    subtotal: int, discount: int, release: ReleaseId = "v1.0"
) -> dict[str, object]:
    return {
        "release": release,
        "subtotal_cents": subtotal,
        "discount_percent": discount,
    }


@pytest.mark.parametrize(
    "subtotal,percent,discount,merchandise,shipping,total", QUOTE_CASES
)
def test_v1_0_calculations(
    subtotal: int,
    percent: int,
    discount: int,
    merchandise: int,
    shipping: int,
    total: int,
) -> None:
    request = QuoteRequest.model_validate(quote_body(subtotal, percent))
    response = calculate_quote(request)
    assert response.model_dump() == {
        **quote_body(subtotal, percent),
        "discount_cents": discount,
        "discounted_subtotal_cents": merchandise,
        "shipping_cents": shipping,
        "total_cents": total,
    }


@pytest.mark.anyio
@pytest.mark.parametrize(
    "subtotal,percent,discount,merchandise,shipping,total", QUOTE_CASES
)
async def test_quote_endpoint(
    client: httpx.AsyncClient,
    subtotal: int,
    percent: int,
    discount: int,
    merchandise: int,
    shipping: int,
    total: int,
) -> None:
    response = await client.post(
        "/svc/api/sandbox/quote", json=quote_body(subtotal, percent)
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        **quote_body(subtotal, percent),
        "discount_cents": discount,
        "discounted_subtotal_cents": merchandise,
        "shipping_cents": shipping,
        "total_cents": total,
    }
    assert compare_quote(subtotal, percent, response.json()).matches


INVALID_FIELDS = [
    ("subtotal_cents", -1),
    ("subtotal_cents", 100_000_001),
    ("subtotal_cents", 1.5),
    ("subtotal_cents", 11000.0),
    ("subtotal_cents", "11000"),
    ("subtotal_cents", True),
    ("subtotal_cents", None),
    ("subtotal_cents", {}),
    ("discount_percent", -1),
    ("discount_percent", 101),
    ("discount_percent", 15.5),
    ("discount_percent", 15.0),
    ("discount_percent", "15"),
    ("discount_percent", False),
    ("discount_percent", None),
    ("release", "v1.2"),
    ("release", "previous"),
    ("release", "current"),
    ("release", "working"),
    ("release", "buggy"),
    ("release", "../../main.py"),
    ("release", None),
    ("release", 1),
    ("url", "https://example.invalid"),
]


@pytest.mark.anyio
@pytest.mark.parametrize("release", ["v1.0", "v1.1"])
@pytest.mark.parametrize("field,value", INVALID_FIELDS)
async def test_invalid_quote_input(
    client: httpx.AsyncClient, release: ReleaseId, field: str, value: object
) -> None:
    body = {**quote_body(11_000, 15, release), field: value}
    with pytest.raises(ValidationError):
        QuoteRequest.model_validate(body)

    response = await client.post("/svc/api/sandbox/quote", json=body)
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)


@pytest.mark.anyio
@pytest.mark.parametrize("release", ["v1.0", "v1.1"])
@pytest.mark.parametrize("field", ["release", "subtotal_cents", "discount_percent"])
async def test_missing_quote_fields(
    client: httpx.AsyncClient, release: ReleaseId, field: str
) -> None:
    body = quote_body(11_000, 15, release)
    del body[field]
    response = await client.post("/svc/api/sandbox/quote", json=body)
    assert response.status_code == 422


@pytest.mark.anyio
@pytest.mark.parametrize("body", ["{", "null", "[]"])
async def test_malformed_quote_body(client: httpx.AsyncClient, body: str) -> None:
    response = await client.post(
        "/svc/api/sandbox/quote",
        content=body,
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422


@pytest.mark.parametrize("release,total", [("v1.0", 9_350), ("v1.1", 10_100)])
def test_service_root_import_and_quote(release: ReleaseId, total: int) -> None:
    # Vercel imports main:app with backend/ as the service root.
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import asyncio
import sys
import httpx
import main

assert not any(name.startswith('oracle') for name in sys.modules)

async def check():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=main.app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/svc/api/sandbox/quote",
            json={"release": sys.argv[1], "subtotal_cents": 11000,
                  "discount_percent": 15},
        )
        assert response.status_code == 200
        print(response.text)

asyncio.run(check())
""",
            release,
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=True,
    )
    actual = json.loads(result.stdout)
    assert actual["release"] == release
    assert actual["total_cents"] == total


def test_oracle_imports_no_checkout_code() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; from backend.oracle.shipping_contract import expected_quote; "
            "assert expected_quote(11000, 15).total_cents == 9350; "
            "assert not any(name.startswith(('backend.sandbox', 'sandbox')) "
            "for name in sys.modules)",
        ],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.returncode == 0
