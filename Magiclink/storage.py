from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional

import redis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

_pool: Optional[redis.Redis] = None


def get_redis() -> redis.Redis:
    global _pool
    if _pool is None:
        _pool = redis.from_url(REDIS_URL, decode_responses=True)  # type: ignore[arg-type]
    return _pool


# Keys
# loc:jti:{jti}:used -> mark first-use with SETNX + TTL ≈ token remaining seconds.
# loc:sid:{sid}:payload -> JSON location payload; write-once (7d TTL).

JTI_KEY = "loc:jti:{jti}:used"
SID_PAYLOAD_KEY = "loc:sid:{sid}:payload"
SID_TTL_SECONDS = 7 * 24 * 60 * 60


def mark_jti_used(jti: str, ttl_seconds: int) -> bool:
    r = get_redis()
    key = JTI_KEY.format(jti=jti)
    was_set = r.set(name=key, value=str(int(time.time())), nx=True, ex=ttl_seconds)
    return bool(was_set)


def is_jti_used(jti: str) -> bool:
    r = get_redis()
    key = JTI_KEY.format(jti=jti)
    return r.exists(key) == 1


def get_location_for_sid(sid: str) -> Optional[Dict[str, Any]]:
    r = get_redis()
    key = SID_PAYLOAD_KEY.format(sid=sid)
    data = r.get(key)
    if not data:
        return None
    try:
        import json

        return json.loads(data)
    except Exception:
        return None


def save_location_for_sid(sid: str, payload: Dict[str, Any]) -> bool:
    r = get_redis()
    key = SID_PAYLOAD_KEY.format(sid=sid)
    import json

    # Returns True if set (first write), False if key already existed
    res = r.set(name=key, value=json.dumps(payload), ex=SID_TTL_SECONDS, nx=True)
    return bool(res) 