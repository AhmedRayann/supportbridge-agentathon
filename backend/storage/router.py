"""Session-owned persistence API; tool execution and state writes remain host-only."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response

from . import models as m
from .database import (
    Conflict,
    Database,
    ExecutionDisabled,
    LimitReached,
    NotFound,
    SessionDenied,
    Settings,
    StorageError,
)
from .repository import Store

router = APIRouter(prefix="/svc/api", tags=["investigations"])
COOKIE = "sb_session"


def get_store() -> Store:
    return Store(Database(Settings.from_env()))


def origin_check(request: Request, store: Store):
    if (
        request.headers.get("origin") != store.settings.app_origin
        or request.headers.get("sec-fetch-site") == "cross-site"
    ):
        raise HTTPException(status_code=403, detail="Same-origin request required")


def owned_session(request: Request, store: Store):
    return store.resolve_session(request.cookies.get(COOKIE))


@router.post("/sessions", response_model=m.Session)
def session(
    request: Request, response: Response, store: Annotated[Store, Depends(get_store)]
):
    origin_check(request, store)
    response.headers["Cache-Control"] = "no-store"
    credential = request.cookies.get(COOKIE)
    if credential:
        try:
            return store.resolve_session(credential)
        except SessionDenied:
            # Rotate rejected credentials only; infrastructure failures propagate.
            pass
    result, credential = store.create_session()
    response.set_cookie(
        COOKIE,
        credential,
        httponly=True,
        secure=store.settings.app_origin.startswith("https://"),
        samesite="strict",
        max_age=store.settings.session_ttl,
        path="/svc/api",
    )
    return result


@router.post("/investigations", response_model=m.Investigation, status_code=201)
def create(
    request: Request,
    response: Response,
    body: m.CreateInvestigation,
    key: Annotated[m.OperationKey, Header(alias="Idempotency-Key")],
    store: Annotated[Store, Depends(get_store)],
):
    origin_check(request, store)
    response.headers["Cache-Control"] = "no-store"
    owner = owned_session(request, store)
    return store.create_investigation(owner.id, body, key)


@router.get("/investigations/{investigation_id}", response_model=m.Investigation)
def read(
    investigation_id: UUID,
    request: Request,
    response: Response,
    store: Annotated[Store, Depends(get_store)],
):
    response.headers["Cache-Control"] = "no-store"
    return store.get_investigation(owned_session(request, store).id, investigation_id)


@router.get("/investigations/{investigation_id}/events", response_model=m.EventPage)
def events(
    investigation_id: UUID,
    request: Request,
    response: Response,
    store: Annotated[Store, Depends(get_store)],
    after: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    response.headers["Cache-Control"] = "no-store"
    return store.list_events(
        owned_session(request, store).id, investigation_id, after=after, limit=limit
    )


@router.get(
    "/investigations/{investigation_id}/evidence/{evidence_id}",
    response_model=m.Evidence,
)
def evidence(
    investigation_id: UUID,
    evidence_id: UUID,
    request: Request,
    response: Response,
    store: Annotated[Store, Depends(get_store)],
):
    response.headers["Cache-Control"] = "no-store"
    return store.get_evidence(
        owned_session(request, store).id, investigation_id, evidence_id
    )


async def storage_error_handler(request: Request, error: StorageError):
    from fastapi.responses import JSONResponse

    if isinstance(error, SessionDenied):
        status = 401
    elif isinstance(error, NotFound):
        status = 404
    elif isinstance(error, Conflict):
        status = 409
    elif isinstance(error, LimitReached):
        status = 429
    elif isinstance(error, ExecutionDisabled):
        status = 503
    else:
        status = 503
    return JSONResponse(
        status_code=status,
        content={"detail": str(error)},
        headers={"Cache-Control": "no-store"},
    )
