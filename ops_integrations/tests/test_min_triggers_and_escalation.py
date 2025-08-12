#!/usr/bin/env python3
import os
import asyncio
import types

# Ensure triggers JSON path points to repo file
HERE = os.path.dirname(__file__)
TRIGGERS = os.path.abspath(os.path.join(HERE, "..", "adapters", "min_triggers.json"))
os.environ.setdefault("MINI_TRIGGER_JSON", TRIGGERS)

from ops_integrations.adapters import phone as phone_mod  # type: ignore

# Patch: avoid real TTS/TwiML side effects
async def _fake_add_tts_or_say_to_twiml(twiml, call_sid: str, text: str):
    msgs = getattr(twiml, "_msgs", None)
    if msgs is None:
        twiml._msgs = []
        msgs = twiml._msgs
    msgs.append((call_sid, text))

# Patch: capture dispatcher handoff attempts
_HANDOFF = {}
async def _fake_perform_dispatch_transfer(call_sid: str) -> None:
    _HANDOFF[call_sid] = _HANDOFF.get(call_sid, 0) + 1

# Provide a stub extractor to simulate LLM behavior
def _set_extractor(async_fn):
    import ops_integrations.flows.intents as intents_mod  # type: ignore
    intents_mod.extract_plumbing_intent = async_fn  # type: ignore[attr-defined]

class _TwimlStub:
    pass

async def test_minimal_trigger_gas():
    call_sid = "CALL_GAS_1"
    # Reset state
    phone_mod.call_info_store[call_sid] = {"from": "+18005551212"}
    _HANDOFF.clear()
    # Patches
    phone_mod.add_tts_or_say_to_twiml = _fake_add_tts_or_say_to_twiml  # type: ignore
    phone_mod.perform_dispatch_transfer = _fake_perform_dispatch_transfer  # type: ignore
    # Extractor won't be used due to trigger
    async def _noop(txt):
        return None
    _set_extractor(_noop)
    twiml = _TwimlStub()
    # Gas trigger phrase
    await phone_mod.handle_followup_or_handoff(call_sid, "I smell gas in the house", twiml)
    st = phone_mod.call_info_store.get(call_sid, {})
    print("[gas trigger] handoff_requested=", st.get("handoff_requested"), "reason=", st.get("handoff_reason"), "handoff_calls=", _HANDOFF.get(call_sid))
    assert st.get("handoff_requested") is True, "handoff should be requested by minimal trigger"
    assert _HANDOFF.get(call_sid) == 1, "perform_dispatch_transfer should be called once"

async def test_two_strike_handoff():
    call_sid = "CALL_2STRIKE"
    phone_mod.call_info_store[call_sid] = {"from": "+18005551313"}
    _HANDOFF.clear()
    phone_mod.add_tts_or_say_to_twiml = _fake_add_tts_or_say_to_twiml  # type: ignore
    phone_mod.perform_dispatch_transfer = _fake_perform_dispatch_transfer  # type: ignore
    # Always unclear
    async def _always_unclear(txt):
        return None
    _set_extractor(_always_unclear)
    twiml = _TwimlStub()
    # First unclear -> prompt for specifics
    await phone_mod.handle_followup_or_handoff(call_sid, "it's broken", twiml)
    st1 = phone_mod.call_info_store.get(call_sid, {})
    print("[2-strike step1] attempts=", st1.get("unclear_intent_attempts"), "handoff=", st1.get("handoff_requested"))
    assert int(st1.get("unclear_intent_attempts", 0)) == 1
    assert _HANDOFF.get(call_sid) is None
    # Second unclear -> handoff
    await phone_mod.handle_followup_or_handoff(call_sid, "still need help", twiml)
    st2 = phone_mod.call_info_store.get(call_sid, {})
    print("[2-strike step2] attempts=", st2.get("unclear_intent_attempts"), "handoff=", st2.get("handoff_requested"), "handoff_calls=", _HANDOFF.get(call_sid))
    assert int(st2.get("unclear_intent_attempts", 0)) == 2
    assert st2.get("handoff_requested") is True
    assert _HANDOFF.get(call_sid) == 1

async def test_one_clarify_then_proceed():
    call_sid = "CALL_RECOVER"
    phone_mod.call_info_store[call_sid] = {"from": "+18005551414"}
    _HANDOFF.clear()
    phone_mod.add_tts_or_say_to_twiml = _fake_add_tts_or_say_to_twiml  # type: ignore
    phone_mod.perform_dispatch_transfer = _fake_perform_dispatch_transfer  # type: ignore
    # First unclear, second clear intent
    seq = {"count": 0}
    async def _extract(txt):
        seq["count"] += 1
        if seq["count"] == 1:
            return None
        return {"job": {"type": "water_heater_repair"}, "customer": {"name": "John"}, "location": {"raw_address": "123 Main"}, "confidence": {"overall": 0.9}}
    _set_extractor(_extract)
    twiml = _TwimlStub()
    await phone_mod.handle_followup_or_handoff(call_sid, "uh it's a thing", twiml)
    st1 = phone_mod.call_info_store.get(call_sid, {})
    print("[recover step1] attempts=", st1.get("unclear_intent_attempts"), "handoff=", st1.get("handoff_requested"))
    assert int(st1.get("unclear_intent_attempts", 0)) == 1
    # Now provide clearer message
    await phone_mod.handle_followup_or_handoff(call_sid, "water heater repair please", twiml)
    st2 = phone_mod.call_info_store.get(call_sid, {})
    print("[recover step2] attempts=", st2.get("unclear_intent_attempts"), "handoff=", st2.get("handoff_requested"))
    # Counter should reset on success and no handoff
    assert int(st2.get("unclear_intent_attempts", 0)) == 0
    assert not st2.get("handoff_requested")
    assert _HANDOFF.get(call_sid) is None

async def main():
    await test_minimal_trigger_gas()
    await test_two_strike_handoff()
    await test_one_clarify_then_proceed()
    print("All escalation/trigger tests passed")

if __name__ == "__main__":
    asyncio.run(main()) 