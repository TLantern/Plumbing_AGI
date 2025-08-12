import os
import json
from datetime import datetime, timedelta
from starlette.testclient import TestClient

# Ensure basic env before importing app
os.environ.setdefault("TWILIO_ACCOUNT_SID", "AC_test")
os.environ.setdefault("TWILIO_AUTH_TOKEN", "token")
os.environ.setdefault("EXTERNAL_WEBHOOK_URL", "https://example.com")
os.environ.setdefault("OPENAI_API_KEY", "sk-test")

# Point Sheets mock to specific file path requested
MOCK_PATH = os.path.abspath("ops_integrations/Mock_crm/Google_sheets_mock.json")
os.makedirs(os.path.dirname(MOCK_PATH), exist_ok=True)
# Clean file before tests
if os.path.exists(MOCK_PATH):
    os.remove(MOCK_PATH)

os.environ["SHEETS_MOCK_LOG_PATH"] = MOCK_PATH
os.environ.pop("GOOGLE_SHEETS_SPREADSHEET_ID", None)
os.environ.pop("GOOGLE_SHEETS_CREDENTIALS_PATH", None)
os.environ.pop("GOOGLE_SHEETS_CREDENTIALS_JSON", None)

from ops_integrations.adapters.phone import app, call_dialog_state, call_info_store  # noqa: E402


def _simulate_voice_webhook(client: TestClient, call_sid: str, from_num: str = "+15551234567"):
    # Create call info via voice webhook to populate metadata and ws_base
    form = {
        "CallSid": call_sid,
        "From": from_num,
        "To": "+18885551212",
        "Direction": "inbound",
    }
    r = client.post("/voice", data=form)
    assert r.status_code == 200


def _set_dialog_for_call(call_sid: str, job_type: str, address: str = "", customer_name: str = "Customer"):
    appt = datetime.utcnow() + timedelta(hours=2)
    call_dialog_state[call_sid] = {
        "intent": {
            "customer": {"name": customer_name, "phone": "+15551234567"},
            "job": {"type": job_type, "description": f"desc for {job_type}"},
            "location": {"raw_address": address},
        },
        "step": "awaiting_operator_confirm",
        "suggested_time": appt,
    }
    # Minimal call_info metadata
    st = call_info_store.setdefault(call_sid, {})
    st.update({
        "from": "+15551234567",
        "from_city": "Denton",
        "from_state": "TX",
        "from_zip": "76201",
        "direction": "inbound",
        "caller_name": customer_name,
    })
    call_info_store[call_sid] = st


def _read_mock_rows():
    if not os.path.exists(MOCK_PATH):
        return []
    with open(MOCK_PATH, "r", encoding="utf-8") as f:
        lines = [ln.strip() for ln in f if ln.strip()]
    return [json.loads(ln) for ln in lines]


def test_crm_sync_5_cases_with_outliers():
    cases = [
        {"call_sid": "CA_CASE1", "job": "leak", "addr": "123 Main St", "name": "Alice"},
        {"call_sid": "CA_CASE2", "job": "clog", "addr": "456 Oak Ave", "name": "Bob"},
        # Outlier 1: missing address
        {"call_sid": "CA_CASE3", "job": "water_heater_repair", "addr": "", "name": "Charlie"},
        # Outlier 2: unusual characters in name and job
        {"call_sid": "CA_CASE4", "job": "install_😊_fixture", "addr": "789 Pine Rd", "name": "D'Artagnan"},
        {"call_sid": "CA_CASE5", "job": "sewer_cam", "addr": "101 Maple Blvd", "name": "Eve"},
    ]

    with TestClient(app) as client:
        for c in cases:
            _simulate_voice_webhook(client, c["call_sid"])  # Establish call context
            _set_dialog_for_call(c["call_sid"], c["job"], c["addr"], c["name"])  # Skip SMS/location
            # Trigger operator approval
            res = client.post("/ops/action/approve", json={
                "call_sid": c["call_sid"],
                "appointment_iso": (datetime.utcnow() + timedelta(hours=3)).isoformat() + "Z",
                "note": "",
            })
            assert res.status_code == 200

    rows = _read_mock_rows()
    # Expect one row per case
    assert len(rows) >= 5
    # Basic validations
    have = {r.get("call_sid") for r in rows}
    for c in cases:
        assert c["call_sid"] in have
    # Spot-check outliers were recorded
    row3 = next(r for r in rows if r.get("call_sid") == "CA_CASE3")
    assert row3.get("address", "") == ""
    row4 = next(r for r in rows if r.get("call_sid") == "CA_CASE4")
    assert "install" in row4.get("service_type", "") 