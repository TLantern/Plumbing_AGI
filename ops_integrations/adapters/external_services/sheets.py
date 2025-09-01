import os
import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

# Google API imports guarded to avoid hard dependency in tests
try:
    from googleapiclient.discovery import build  # type: ignore
    from google.oauth2 import service_account  # type: ignore
except Exception:  # pragma: no cover
    build = None  # type: ignore
    service_account = None  # type: ignore


class GoogleSheetsCRM:
    """Append booking confirmations to a Google Sheets worksheet.

    Configuration via env:
      - GOOGLE_SHEETS_SPREADSHEET_ID: target spreadsheet ID
      - SHEETS_BOOKINGS_TAB_NAME: worksheet/tab name (default: Bookings)
      - GOOGLE_SHEETS_CREDENTIALS_PATH: path to service account JSON
      - GOOGLE_SHEETS_CREDENTIALS_JSON: credentials JSON payload (alternative to PATH)
      - SHEETS_MOCK_LOG_PATH: if set (and Google creds missing), append JSONL records to this local file
    """

    SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

    def __init__(self) -> None:
        self.spreadsheet_id: Optional[str] = os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID")
        self.tab_name: str = os.getenv("SHEETS_BOOKINGS_TAB_NAME", "Bookings")
        self.creds_path: Optional[str] = os.getenv("GOOGLE_SHEETS_CREDENTIALS_PATH")
        self.creds_json: Optional[str] = os.getenv("GOOGLE_SHEETS_CREDENTIALS_JSON")
        self.mock_log_path: Optional[str] = os.getenv("SHEETS_MOCK_LOG_PATH")
        self.enabled: bool = bool(self.spreadsheet_id and (self.creds_path or self.creds_json) and build and service_account)
        self._service = None
        if self.enabled:
            try:
                self._service = self._build_service()
            except Exception as e:  # pragma: no cover
                logging.error(f"Sheets service init failed: {e}")
                self.enabled = False

    def _build_service(self):  # pragma: no cover - networked path
        if self.creds_path and os.path.exists(self.creds_path):
            creds = service_account.Credentials.from_service_account_file(self.creds_path, scopes=self.SCOPES)
        else:
            info = json.loads(self.creds_json or "{}")
            creds = service_account.Credentials.from_service_account_info(info, scopes=self.SCOPES)
        return build('sheets', 'v4', credentials=creds)

    def _headers(self) -> List[str]:
        return [
            "Timestamp",
            "Call SID", 
            "Customer Name",
            "Phone Number",
            "Call Status",
            "Call Duration (sec)",
            "After Hours",
            "Service Requested",
            "Appointment Date",
            "Recording URL",
            "Notes",
            "Source",
            "Direction",
            "Error Code"
        ]

    def _record_to_row(self, rec: Dict[str, Any]) -> List[str]:
        return [
            rec.get("timestamp") or datetime.utcnow().isoformat() + "Z",
            rec.get("call_sid", ""),
            rec.get("customer_name", ""),
            rec.get("phone", ""),
            rec.get("call_status", ""),
            rec.get("call_duration", ""),
            rec.get("after_hours", ""),
            rec.get("service_requested", ""),
            rec.get("appointment_date", ""),
            rec.get("recording_url", ""),
            rec.get("notes", ""),
            rec.get("source", "phone_system"),
            rec.get("direction", "inbound"),
            rec.get("error_code", "")
        ]

    def _ensure_headers(self) -> bool:  # pragma: no cover
        """Ensure headers are present in the sheet"""
        try:
            # Check if headers exist by reading the first row
            result = self._service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.tab_name}!A1:M1"
            ).execute()
            
            values = result.get('values', [])
            if not values or not values[0]:
                # No headers found, add them
                headers = self._headers()
                body = {"values": [headers]}
                self._service.spreadsheets().values().update(
                    spreadsheetId=self.spreadsheet_id,
                    range=f"{self.tab_name}!A1",
                    valueInputOption="USER_ENTERED",
                    body=body
                ).execute()
                logging.info(f"Added headers to {self.tab_name} sheet")
                return True
            else:
                # Headers already exist
                return True
        except Exception as e:
            logging.error(f"Failed to ensure headers: {e}")
            return False

    def _append_to_sheets(self, row_values: List[str]) -> bool:  # pragma: no cover
        try:
            # Ensure headers are present first
            if not self._ensure_headers():
                return False
                
            sheet_range = f"{self.tab_name}!A:Z"
            body = {"values": [row_values]}
            self._service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range=sheet_range,
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body=body,
            ).execute()
            return True
        except Exception as e:
            logging.error(f"Sheets append failed: {e}")
            return False

    def _append_to_mock_log(self, row_dict: Dict[str, Any]) -> bool:
        try:
            if not self.mock_log_path:
                return False
            os.makedirs(os.path.dirname(self.mock_log_path), exist_ok=True)
            with open(self.mock_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(row_dict) + "\n")
            return True
        except Exception as e:
            logging.error(f"Mock log append failed: {e}")
            return False

    def sync_booking(self, booking: Dict[str, Any]) -> Dict[str, Any]:
        """Append a booking record to Sheets or mock log. Returns {ok: bool, mode: 'sheets'|'mock'|'disabled'}."""
        # Prepare canonical record
        row_dict = {
            "timestamp": booking.get("timestamp") or datetime.utcnow().isoformat() + "Z",
            "call_sid": booking.get("call_sid"),
            "customer_name": booking.get("customer_name") or booking.get("name") or "Unknown",
            "phone": booking.get("phone") or "",
            "call_status": booking.get("call_status") or "",
            "call_duration": booking.get("call_duration") or "",
            "after_hours": booking.get("after_hours") or "",
            "service_requested": booking.get("service_requested") or booking.get("service_type") or "",
            "appointment_date": booking.get("appointment_date") or "",
            "recording_url": booking.get("recording_url") or "",
            "notes": booking.get("notes") or "",
            "source": booking.get("source") or "phone_system",
            "direction": booking.get("direction") or "inbound",
            "error_code": booking.get("error_code") or ""
        }

        if self.enabled and self._service is not None:
            ok = self._append_to_sheets(self._record_to_row(row_dict))
            return {"ok": ok, "mode": "sheets"}

        if self.mock_log_path:
            ok = self._append_to_mock_log(row_dict)
            return {"ok": ok, "mode": "mock"}

        logging.info("Sheets CRM disabled and no mock_log_path set; skipping booking sync")
        return {"ok": False, "mode": "disabled"} 