import httpx
import pytest

from backend.main import app


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


pytestmark = pytest.mark.anyio


@pytest.mark.parametrize("path", ["/health", "/svc/api/health"])
async def test_health_contract(path: str) -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(path)

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {"status": "ok", "service": "supportbridge-api"}


async def test_health_does_not_expose_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A sentinel proves that arbitrary environment values never enter the response.
    monkeypatch.setenv("GEMINI_API_KEY", "test-only-secret-sentinel")
    monkeypatch.setenv("DATABASE_URL", "test-only-database-sentinel")
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health")

    assert "sentinel" not in response.text
    assert set(response.json()) == {"status", "service"}
