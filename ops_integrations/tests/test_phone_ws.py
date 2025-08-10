import os
from starlette.testclient import TestClient

# Ensure required env vars for settings before importing the app
os.environ.setdefault("TWILIO_ACCOUNT_SID", "AC_test")
os.environ.setdefault("TWILIO_AUTH_TOKEN", "token")
os.environ.setdefault("EXTERNAL_WEBHOOK_URL", "https://example.com")
os.environ.setdefault("OPENAI_API_KEY", "sk-test")

from ops_integrations.adapters.phone import app, manager  # noqa: E402


def test_websocket_extract_callsid_from_start_event():
    with TestClient(app) as client:
        with client.websocket_connect("/stream") as ws:
            ws.send_json({"event": "connected", "protocol": "Call", "version": "1.0"})
            start_payload = {
                "event": "start",
                "start": {
                    "callSid": "CA1234567890",
                    "streamSid": "MZabcdef",
                    "tracks": ["inbound_track"],
                    "customParameters": {}
                }
            }
            ws.send_json(start_payload)
            # Stop event to trigger cleanup
            ws.send_json({"event": "stop"})
        # After closing, ensure active connection cleaned up
        assert "CA1234567890" not in manager.active_connections


def test_websocket_with_query_param_callsid():
    with TestClient(app) as client:
        with client.websocket_connect("/stream?callSid=CAQPTEST") as ws:
            # Should not need start event; send stop to close
            ws.send_json({"event": "stop"})
        assert "CAQPTEST" not in manager.active_connections 


def test_ops_ws_receives_job_description_on_send(monkeypatch):
    from datetime import datetime
    from ops_integrations.adapters import phone as phone_mod

    # Prepare a dummy operator WebSocket using TestClient's websocket
    with TestClient(app) as client:
        received = {}
        # Connect ops websocket; server will add it to ops_ws_clients
        with client.websocket_connect("/ops") as ops_ws:
            call_sid = "CA_TEST_JOB"
            intent = {
                "customer": {"name": "Alice", "phone": "+15551234567"},
                "job": {"type": "leak", "description": "kitchen faucet leak"},
                "location": {"raw_address": "123 Main St"},
            }
            suggested_time = datetime.utcnow()

            # Drain initial metrics snapshot
            _ = ops_ws.receive_json()

            # Send a job to operator (run coroutine)
            import asyncio
            asyncio.get_event_loop().run_until_complete(
                phone_mod._send_booking_to_operator(call_sid, intent, suggested_time)
            )

            # Read one message from ops ws
            msg = ops_ws.receive_json()
            assert msg.get("type") == "job_description"
            data = msg.get("data", {})
            assert data.get("callSid") == call_sid
            job = data.get("job", {})
            assert job.get("customer_name") == "Alice"
            assert job.get("service_type") == "leak"
            assert "appointment_time" in job
            assert job.get("address") 