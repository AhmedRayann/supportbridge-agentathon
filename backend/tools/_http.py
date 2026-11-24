"""Bounded HTTP transport shared by the two fixed-target adapters."""

import asyncio
from dataclasses import dataclass
from typing import Literal

import httpx

from .investigation_models import ToolError

MAX_RESPONSE_BYTES = 262_144
TOTAL_TIMEOUT_SECONDS = 15


@dataclass(frozen=True)
class HttpResult:
    status: int | None
    body: bytes = b""
    error: ToolError | None = None


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=httpx.Timeout(5.0),
        follow_redirects=False,
        trust_env=False,
        limits=httpx.Limits(max_connections=2),
    )


async def request(
    method: Literal["GET", "POST"],
    url: str,
    *,
    headers: dict[str, str],
    payload: dict | None = None,
) -> HttpResult:
    status = None
    try:
        async with asyncio.timeout(TOTAL_TIMEOUT_SECONDS), _client() as client:
            async with client.stream(
                method, url, headers=headers, json=payload
            ) as response:
                status = response.status_code
                if 300 <= status < 400:
                    return HttpResult(
                        status,
                        error=ToolError(
                            code="redirect_denied", detail="Redirects are not permitted"
                        ),
                    )
                if status == 429 or (
                    status == 403
                    and response.headers.get("x-ratelimit-remaining") == "0"
                ):
                    return HttpResult(
                        status,
                        error=ToolError(
                            code="rate_limited", detail="Upstream rate limit reached"
                        ),
                    )
                if status != 200:
                    return HttpResult(
                        status,
                        error=ToolError(
                            code="http_error",
                            detail="Upstream returned an unsuccessful HTTP status",
                        ),
                    )
                content = bytearray()
                async for chunk in response.aiter_bytes(chunk_size=8192):
                    if len(content) + len(chunk) > MAX_RESPONSE_BYTES:
                        return HttpResult(
                            status,
                            error=ToolError(
                                code="response_too_large",
                                detail="Response exceeded the byte limit",
                            ),
                        )
                    content.extend(chunk)
                return HttpResult(status, bytes(content))
    except (TimeoutError, httpx.TimeoutException):
        return HttpResult(
            status,
            error=ToolError(
                code="timeout", detail="Upstream request exceeded its time limit"
            ),
        )
    except httpx.HTTPError:
        return HttpResult(
            status,
            error=ToolError(
                code="environment_unavailable",
                detail="Upstream environment is unavailable",
            ),
        )
