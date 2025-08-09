from __future__ import annotations

import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, Tuple

from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError

JWT_SECRET = os.getenv("JWT_SECRET", "changeme")
JWT_ALG = "HS256"
JWT_TTL_MINUTES = int(os.getenv("JWT_TTL_MINUTES", "10"))
LOCATION_WRITE_SCOPE = "location:write"


def _now_utc_ts() -> int:
    return int(time.time())


def _exp_ts(ttl_minutes: int) -> int:
    return int((datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)).timestamp())


def mint_location_token(sid: str) -> Tuple[str, str, int]:
    jti = str(uuid.uuid4())
    exp = _exp_ts(JWT_TTL_MINUTES)
    claims = {
        "sid": sid,
        "jti": jti,
        "exp": exp,
        "scope": LOCATION_WRITE_SCOPE,
    }
    token = jwt.encode(claims, JWT_SECRET, algorithm=JWT_ALG)
    return token, jti, exp


def verify_token(token: str) -> Dict:
    # Let ExpiredSignatureError propagate distinctly
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        return payload
    except ExpiredSignatureError:
        raise
    except JWTError:
        # generic invalid token
        raise


def remaining_ttl_seconds(exp: int) -> int:
    remaining = exp - _now_utc_ts()
    # ensure at least 1 second ttl to mark consumption
    return max(1, remaining) 