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