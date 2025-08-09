from __future__ import annotations

import os
import logging
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from jose.exceptions import ExpiredSignatureError

from .logging_conf import configure_json_logging
from .models import LocationIn, TokenOut
from .security import (
    LOCATION_WRITE_SCOPE,
    mint_location_token,
    remaining_ttl_seconds,
    verify_token,
)
from .storage import (
    get_location_for_sid,
    mark_jti_used,
    save_location_for_sid,
)

APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8000")
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY")

configure_json_logging()
logger = logging.getLogger("magiclink")

app = FastAPI(title="Location Capture")

# CORS: allow only FRONTEND_ORIGIN and APP_BASE_URL
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN, APP_BASE_URL],
    allow_credentials=True,
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "x-api-key"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.info(
        "validation_error",
        extra={"evt": "validation_error", "decision": "reject", "reason": "validation error", "status_code": 400},
    )
    return JSONResponse(status_code=400, content={"status": "error", "reason": "validation error"})


@app.get("/")
def health() -> Dict[str, str]:
    return {"service": "Location"}


@app.post("/tokens/location", response_model=TokenOut)
async def mint_token(sid: str) -> TokenOut:
    token, jti, exp = mint_location_token(sid)
    logger.info("mint_token", extra={"evt": "mint", "sid": sid, "jti": jti, "decision": "ok", "status_code": 200})
    return TokenOut(token=token, exp=exp, jti=jti)


# Helper to extract bearer token

def _extract_bearer_token(request: Request) -> str:
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return auth.split(" ", 1)[1]


@app.post("/introspect")
async def introspect(request: Request) -> Dict[str, str]:
    token = _extract_bearer_token(request)
    try:
        payload = verify_token(token)
        sid = payload.get("sid")
        if not sid:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
        logger.info("introspect", extra={"evt": "introspect", "sid": sid, "jti": payload.get("jti"), "decision": "ok", "status_code": 200})
        return {"sid": sid}
    except ExpiredSignatureError:
        logger.info("introspect_expired", extra={"evt": "introspect", "decision": "reject", "reason": "token expired", "status_code": 401})
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    except Exception:
        logger.info("introspect_invalid", extra={"evt": "introspect", "decision": "reject", "reason": "invalid token", "status_code": 401})
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)


@app.post("/calls/{sid}/location")
async def submit_location(sid: str, request: Request, body: LocationIn) -> JSONResponse:
    token = _extract_bearer_token(request)

    # Verify token
    try:
        payload = verify_token(token)
    except ExpiredSignatureError:
        logger.info("submit_expired", extra={"evt": "submit", "sid": sid, "decision": "reject", "reason": "token expired", "status_code": 401})
        return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"status": "expired", "reason": "token expired"})
    except Exception:
        logger.info("submit_invalid_token", extra={"evt": "submit", "sid": sid, "decision": "reject", "reason": "invalid token", "status_code": 401})
        return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"status": "unauthorized", "reason": "invalid token"})

    token_sid = payload.get("sid")
    jti = payload.get("jti")
    exp = int(payload.get("exp", 0))
    scope = payload.get("scope")

    # Validate claims
    if scope != LOCATION_WRITE_SCOPE or token_sid is None or jti is None or exp <= 0:
        logger.info("submit_invalid", extra={"evt": "submit", "sid": sid, "jti": jti, "decision": "reject", "reason": "invalid token", "status_code": 401})
        return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"status": "unauthorized", "reason": "invalid token"})

    if token_sid != sid:
        logger.info("submit_sid_mismatch", extra={"evt": "submit", "sid": sid, "jti": jti, "decision": "reject", "reason": "sid mismatch", "status_code": 401})
        return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"status": "unauthorized", "reason": "sid mismatch"})

    # Idempotent by sid
    existing = get_location_for_sid(sid)
    if existing is not None:
        logger.info("submit_idempotent_exists", extra={"evt": "submit", "sid": sid, "jti": jti, "decision": "ok", "reason": "location already present", "status_code": 200})
        return JSONResponse(status_code=status.HTTP_200_OK, content={"status": "ok", "idempotent": True, "reason": "location already present"})

    # Single-use by jti using SETNX
    ttl_seconds = remaining_ttl_seconds(exp)
    first_use = mark_jti_used(jti, ttl_seconds)
    if not first_use:
        # Re-check if sid now has a stored location; if so, idempotent true
        existing_after = get_location_for_sid(sid)
        if existing_after is not None:
            logger.info("submit_used_but_idempotent", extra={"evt": "submit", "sid": sid, "jti": jti, "decision": "ok", "reason": "location already present", "status_code": 200})
            return JSONResponse(status_code=status.HTTP_200_OK, content={"status": "ok", "idempotent": True, "reason": "location already present"})
        logger.info("submit_used", extra={"evt": "submit", "sid": sid, "jti": jti, "decision": "reject", "reason": "token already consumed", "status_code": 409})
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"status": "used", "reason": "token already consumed"})

    # Accept denied/timeout reports
    payload_to_save: Dict[str, Any] = body.model_dump(exclude_none=True)

    saved = save_location_for_sid(sid, payload_to_save)
    if not saved:
        logger.info("submit_race_idempotent", extra={"evt": "submit", "sid": sid, "jti": jti, "decision": "ok", "reason": "location already present", "status_code": 200})
        return JSONResponse(status_code=status.HTTP_200_OK, content={"status": "ok", "idempotent": True, "reason": "location already present"})

    logger.info("submit_ok", extra={"evt": "submit", "sid": sid, "jti": jti, "decision": "ok", "status_code": 200})
    return JSONResponse(status_code=status.HTTP_200_OK, content={"status": "ok", "idempotent": False})


@app.get("/admin/calls/{sid}/location/status")
async def admin_location_status(sid: str, request: Request) -> Dict[str, Any]:
    if not ADMIN_API_KEY:
        raise HTTPException(status_code=404, detail="not found")
    api_key = request.headers.get("x-api-key")
    if api_key != ADMIN_API_KEY:
        raise HTTPException(status_code=403, detail="forbidden")
    present = get_location_for_sid(sid) is not None
    return {"present": present} 