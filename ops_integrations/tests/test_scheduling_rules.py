import os
import types
from datetime import datetime, timedelta

import pytest

# Patch CalendarAdapter to a stub for deterministic tests
class StubCalendar:
    def __init__(self, busy_intervals=None):
        self.enabled = True
        # busy_intervals: list of (start_dt, end_dt)
        self._busy = busy_intervals or []

    def get_events(self, start_date=None, end_date=None, max_results=100):
        items = []
        for s, e in self._busy:
            if end_date and e <= start_date:
                continue
            if start_date and s >= end_date:
                continue
            items.append({
                "start": {"dateTime": s.isoformat() + "Z"},
                "end": {"dateTime": e.isoformat() + "Z"},
            })
        return items


def with_stub_calendar(monkeypatch, intervals):
    from ops_integrations.adapters import phone as phone_mod
    stub = StubCalendar(intervals)
    monkeypatch.setattr(phone_mod, "CalendarAdapter", lambda: stub, raising=True)
    return phone_mod


def test_emergency_min_30_minutes_and_quarter_alignment(monkeypatch):
    phone_mod = with_stub_calendar(monkeypatch, [])
    now = datetime.now()
    earliest = now + timedelta(minutes=1)
    slot = phone_mod.find_next_compliant_slot(earliest, emergency=True)
    # At least 30 minutes out
    assert (slot - now) >= timedelta(minutes=30)
    # Quarter-hour aligned
    assert slot.minute % 15 == 0 and slot.second == 0 and slot.microsecond == 0


def test_regular_quarter_alignment_and_buffer(monkeypatch):
    now = datetime.now().replace(second=0, microsecond=0)
    # Busy event from +2:00 to +4:00
    busy_start = now + timedelta(hours=2)
    busy_end = busy_start + timedelta(hours=2)
    phone_mod = with_stub_calendar(monkeypatch, [(busy_start, busy_end)])
    # Request +2:30 should be rejected due to 1h buffer; next available should be >= busy_end + 1h, aligned to quarter
    requested = busy_start + timedelta(minutes=30)
    next_slot = phone_mod.find_next_compliant_slot(requested, emergency=False)
    min_allowed = busy_end + timedelta(hours=1)
    assert next_slot >= min_allowed
    assert next_slot.minute % 15 == 0


def test_buffer_blocks_before_and_after(monkeypatch):
    now = datetime.now().replace(second=0, microsecond=0)
    # Busy 10:00–12:00, buffer requires 9:00–13:00 to be blocked
    busy_start = now.replace(hour=((now.hour + 1) % 24), minute=0)
    busy_end = busy_start + timedelta(hours=2)
    phone_mod = with_stub_calendar(monkeypatch, [(busy_start, busy_end)])

    before = busy_start - timedelta(minutes=30)
    slot_before = phone_mod.find_next_compliant_slot(before, emergency=False)
    assert slot_before >= (busy_end + timedelta(hours=1)) 