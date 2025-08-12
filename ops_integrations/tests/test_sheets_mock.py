import os
import json
from datetime import datetime

from ops_integrations.adapters.sheets import GoogleSheetsCRM


def test_sheets_mock_log(tmp_path, monkeypatch):
    # Force disabled live Sheets and set mock log path
    monkeypatch.delenv("GOOGLE_SHEETS_SPREADSHEET_ID", raising=False)
    monkeypatch.delenv("GOOGLE_SHEETS_CREDENTIALS_PATH", raising=False)
    monkeypatch.delenv("GOOGLE_SHEETS_CREDENTIALS_JSON", raising=False)
    log_path = tmp_path / "bookings.jsonl"
    monkeypatch.setenv("SHEETS_MOCK_LOG_PATH", str(log_path))

    sheets = GoogleSheetsCRM()
    assert sheets.enabled is False

    rec = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "call_sid": "CA123",
        "customer_name": "Jane Doe",
        "phone": "+15551234567",
        "service_type": "water_heater_repair",
        "appointment_time_iso": datetime.utcnow().isoformat() + "Z",
        "address": "123 Main St",
        "notes": "leak under tank",
        "operator_note": "confirmed",
    }

    res = sheets.sync_booking(rec)
    assert res["ok"] is True
    assert res["mode"] == "mock"

    # Read back the log
    data = [json.loads(line) for line in open(log_path, "r", encoding="utf-8").read().splitlines() if line.strip()]
    assert len(data) == 1
    assert data[0]["call_sid"] == "CA123"
    assert data[0]["customer_name"] == "Jane Doe" 