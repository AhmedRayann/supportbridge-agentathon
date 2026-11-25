"""SupportBridge health and synthetic checkout API."""

from typing import Literal

from fastapi import FastAPI, Response
from pydantic import BaseModel, ConfigDict

# Support both package execution locally and main:app from the Vercel service root.
if __package__:
    from .sandbox.router import router as sandbox_router
    from .storage.database import StorageError
    from .storage.router import router as storage_router
    from .storage.router import storage_error_handler
else:
    from sandbox.router import router as sandbox_router
    from storage.database import StorageError
    from storage.router import router as storage_router
    from storage.router import storage_error_handler

app = FastAPI(title="SupportBridge API", version="0.1.0")
app.include_router(sandbox_router)
app.include_router(storage_router)
app.add_exception_handler(StorageError, storage_error_handler)


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
