## Magiclink Location Capture API

### Env
Create a `.env` or export environment variables:

```
APP_BASE_URL=http://localhost:8000
FRONTEND_ORIGIN=http://localhost:3000
JWT_SECRET=change-me
JWT_TTL_MINUTES=10
REDIS_URL=redis://localhost:6379/0
```

### Install & Run

```
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r Magiclink/requirements.txt
uvicorn Magiclink.magic:app --host 0.0.0.0 --port 8000
```

Redis 5+ is required and must be reachable at `REDIS_URL`.

### Endpoints
- POST `/tokens/location?sid=<CALL_SID>` → mint single-use JWT
- POST `/introspect` (Bearer) → returns `{"sid": "..."}`
- POST `/calls/{sid}/location` (Bearer) → write-once payload, idempotent by sid

### Manual Tests
The following must pass (requires `jq`):

```bash
# 0) Health (optional)
curl -s http://localhost:8000/ | grep -q Location && echo OK

# 1) Mint token
SID="CA1234567890"
TOKEN=$(curl -s -X POST "http://localhost:8000/tokens/location?sid=${SID}" | jq -r .token)
test "$TOKEN" != "null" && echo "token ok"

# 2) Introspect -> sid
curl -s -X POST http://localhost:8000/introspect -H "Authorization: Bearer $TOKEN" | jq -e ".sid==\"$SID\""

# 3) First POST -> 200
curl -s -X POST "http://localhost:8000/calls/$SID/location" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"lat":33.2101,"lng":-97.1504,"accuracy":20,"timestamp":1710000000000,"address":"Denton, TX"}' | jq -e '.status=="ok" and .idempotent==false'

# 4) Second POST with same token -> 409 used OR 200 idempotent (if record exists)
curl -s -o /dev/null -w "%{http_code}" -X POST "http://localhost:8000/calls/$SID/location" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"lat":33,"lng":-97}' | grep -E "^(200|409)$"

# 5) New token but same SID -> 200 idempotent
TOKEN2=$(curl -s -X POST "http://localhost:8000/tokens/location?sid=${SID}" | jq -r .token)
curl -s -X POST "http://localhost:8000/calls/$SID/location" \
  -H "Authorization: Bearer $TOKEN2" -H "Content-Type: application/json" \
  -d '{"lat":33,"lng":-97}' | jq -e '.idempotent==true'

# 6) Expired token -> 401 expired (simulate by env TTL=0)
# Expect: {"status":"expired","reason":"token expired"}

# 7) Denied/Timeout reports
SID3="CA_timeouts"
TK3=$(curl -s -X POST "http://localhost:8000/tokens/location?sid=${SID3}" | jq -r .token)
curl -s -X POST "http://localhost:8000/calls/$SID3/location" \
  -H "Authorization: Bearer $TK3" -H "Content-Type: application/json" \
  -d '{"denied":true,"user_agent":"test"}' | jq -e '.status=="ok"'
```

### Start Uvicorn
- Quick start (inline env):
  ```bash
  APP_BASE_URL=http://localhost:8000 \
  FRONTEND_ORIGIN=http://localhost:3000 \
  JWT_SECRET=change-me \
  JWT_TTL_MINUTES=10 \
  REDIS_URL=redis://localhost:6379/0 \
  uvicorn Magiclink.magic:app --host 0.0.0.0 --port 8000
  ```
- Dev with reload:
  ```bash
  uvicorn Magiclink.magic:app --host 0.0.0.0 --port 8000 --reload
  ```
- Note: the module path is case-sensitive: `Magiclink.magic:app`.

### Troubleshooting: jose import not found
If your editor shows "Import 'jose' could not be resolved from source":
- Ensure your virtualenv is active and dependencies installed:
  ```bash
  source .venv/bin/activate
  pip install -r Magiclink/requirements.txt
  python -c "import jose, sys; print(jose.__version__, sys.executable)"
  ```
- If `python -c` fails, install directly:
  ```bash
  pip install "python-jose[cryptography]"
  ```
- VS Code: select the correct interpreter (`.venv` or `.venv-magic`):
  - Command Palette → "Python: Select Interpreter" → pick your env.
- Restart the editor/Pylance after installing. 