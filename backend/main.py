"""Milestone 1A: a real Python health endpoint, without external dependencies."""

from typing import Literal

from fastapi import FastAPI, Response
from pydantic import BaseModel, ConfigDict

app = FastAPI(title="SupportBridge API", version="0.1.0")


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"] = "ok"
    service: Literal["supportbridge-api"] = "supportbridge-api"


@app.get("/health", response_model=HealthResponse)
@app.get("/svc/api/health", response_model=HealthResponse)
def health(response: Response) -> HealthResponse:
    """Liveness only: does not claim model, database or checkout readiness."""
    response.headers["Cache-Control"] = "no-store"
    return HealthResponse()
