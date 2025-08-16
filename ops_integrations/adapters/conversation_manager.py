import asyncio
import logging
import time
from typing import Dict, Any, Optional, List
from collections import defaultdict

logger = logging.getLogger(__name__)

class ConversationManager:
    """Manages conversation state and dialog flow"""
    
    def __init__(self):
        # Dialog state per call
        self.dialog_states: Dict[str, Dict[str, Any]] = defaultdict(dict)
        
        # Call information store
        self.call_info_store: Dict[str, Dict[str, Any]] = defaultdict(dict)
        
        # Duplicate suppression tracking
        self.duplicate_tracking: Dict[str, Dict[str, Any]] = defaultdict(dict)
        
        # Clarification attempts tracking
        self.clarification_attempts: Dict[str, int] = defaultdict(int)
        
        # Repeated utterances tracking
        self.repeated_utterances: Dict[str, Dict[str, int]] = defaultdict(dict)
        
        # Configuration
        self.duplicate_window_seconds = 30
        self.max_clarification_attempts = 2
        self.max_repeated_utterances = 3
    
    def get_dialog_state(self, call_sid: str) -> Dict[str, Any]:
        """Get current dialog state for a call"""
        return self.dialog_states.get(call_sid, {}).copy()
    
    def set_dialog_state(self, call_sid: str, state: Dict[str, Any]) -> None:
        """Set dialog state for a call"""
        self.dialog_states[call_sid] = state.copy()
        logger.info(f"📝 Dialog state updated for {call_sid}: {state.get('step', 'unknown')}")
    
    def update_dialog_state(self, call_sid: str, updates: Dict[str, Any]) -> None:
        """Update dialog state with new information"""
        current_state = self.dialog_states.get(call_sid, {})
        current_state.update(updates)
        self.dialog_states[call_sid] = current_state
        logger.info(f"📝 Dialog state updated for {call_sid}: {updates}")
    
    def clear_dialog_state(self, call_sid: str) -> None:
        """Clear dialog state for a call"""
        self.dialog_states.pop(call_sid, None)
        logger.info(f"🗑️ Dialog state cleared for {call_sid}")
    
    def get_call_info(self, call_sid: str) -> Dict[str, Any]:
        """Get call information"""
        return self.call_info_store.get(call_sid, {}).copy()
    
    def set_call_info(self, call_sid: str, info: Dict[str, Any]) -> None:
        """Set call information"""
        self.call_info_store[call_sid] = info.copy()
    
    def update_call_info(self, call_sid: str, updates: Dict[str, Any]) -> None:
        """Update call information"""
        current_info = self.call_info_store.get(call_sid, {})
        current_info.update(updates)
        self.call_info_store[call_sid] = current_info
    
    def should_suppress_duplicate(self, call_sid: str, text: str) -> bool:
        """Check if text should be suppressed as a duplicate"""
        try:
            normalized_text = " ".join(text.lower().split())
            tracking = self.duplicate_tracking[call_sid]
            prev_text = tracking.get('last_text')
            prev_ts = tracking.get('last_ts', 0)
            now_ts = time.time()
            
            # Check for exact duplicates within window
            if prev_text == normalized_text and (now_ts - prev_ts) < self.duplicate_window_seconds:
                logger.info(f"Suppressing duplicate transcript for {call_sid}: '{text}'")
                return True
            
            # Check for very similar text (e.g., "James Brown" vs "James Brown.")
            if prev_text and normalized_text:
                clean_prev = ''.join(c for c in prev_text if c.isalnum() or c.isspace())
                clean_current = ''.join(c for c in normalized_text if c.isalnum() or c.isspace())
                if clean_prev == clean_current and (now_ts - prev_ts) < self.duplicate_window_seconds:
                    logger.info(f"Suppressing similar transcript for {call_sid}: '{text}' (similar to '{prev_text}')")
                    return True
            
            # Update tracking
            tracking['last_text'] = normalized_text
            tracking['last_ts'] = now_ts
            
            return False
            
        except Exception as e:
            logger.debug(f"Duplicate check failed for {call_sid}: {e}")
            return False
    
    def should_suppress_repeated_utterance(self, call_sid: str, text: str) -> bool:
        """Check if text should be suppressed due to repeated utterances"""
        try:
            normalized_text = " ".join(text.lower().split())
            utterances = self.repeated_utterances[call_sid]
            
            # Count how many times this exact text has been said
            if normalized_text in utterances:
                utterances[normalized_text] += 1
            else:
                utterances[normalized_text] = 1
            
            # If the same text has been said too many times, suppress it
            if utterances[normalized_text] >= self.max_repeated_utterances:
                logger.info(f"🔄 User appears stuck repeating '{text}' for {call_sid} ({utterances[normalized_text]} times)")
                return True
            
            return False
            
        except Exception as e:
            logger.debug(f"Repeated utterance check failed for {call_sid}: {e}")
            return False
    
    def increment_clarification_attempts(self, call_sid: str) -> int:
        """Increment clarification attempts and return current count"""
        self.clarification_attempts[call_sid] += 1
        count = self.clarification_attempts[call_sid]
        logger.info(f"🔢 Clarification attempt #{count} for {call_sid}")
        return count
    
    def get_clarification_attempts(self, call_sid: str) -> int:
        """Get current clarification attempts count"""
        return self.clarification_attempts.get(call_sid, 0)
    
    def should_handoff_due_to_clarification_attempts(self, call_sid: str) -> bool:
        """Check if handoff is needed due to too many clarification attempts"""
        return self.get_clarification_attempts(call_sid) >= self.max_clarification_attempts
    
    def reset_clarification_attempts(self, call_sid: str) -> None:
        """Reset clarification attempts counter"""
        if self.clarification_attempts.get(call_sid, 0) > 0:
            self.clarification_attempts[call_sid] = 0
            logger.info(f"✅ Reset clarification attempts for {call_sid}")
    
    def reset_repeated_utterances(self, call_sid: str) -> None:
        """Reset repeated utterances counter"""
        if self.repeated_utterances.get(call_sid):
            self.repeated_utterances[call_sid] = {}
            logger.info(f"✅ Reset repeated utterances for {call_sid}")
    
    def reset_all_counters(self, call_sid: str) -> None:
        """Reset all counters for a call"""
        self.reset_clarification_attempts(call_sid)
        self.reset_repeated_utterances(call_sid)
        self.duplicate_tracking.pop(call_sid, None)
    
    def get_conversation_summary(self, call_sid: str) -> Dict[str, Any]:
        """Get a summary of the conversation state"""
        dialog_state = self.get_dialog_state(call_sid)
        call_info = self.get_call_info(call_sid)
        
        return {
            'call_sid': call_sid,
            'dialog_step': dialog_state.get('step'),
            'customer_name': dialog_state.get('customer_name'),
            'clarification_attempts': self.get_clarification_attempts(call_sid),
            'repeated_utterances': dict(self.repeated_utterances.get(call_sid, {})),
            'call_duration': time.time() - call_info.get('start_ts', time.time()),
            'from_number': call_info.get('from'),
            'to_number': call_info.get('to')
        }
    
    def cleanup_call(self, call_sid: str) -> None:
        """Clean up all data for a call"""
        self.dialog_states.pop(call_sid, None)
        self.call_info_store.pop(call_sid, None)
        self.duplicate_tracking.pop(call_sid, None)
        self.clarification_attempts.pop(call_sid, None)
        self.repeated_utterances.pop(call_sid, None)
        logger.info(f"🧹 Cleaned up all data for {call_sid}")
    
    def get_active_calls(self) -> List[str]:
        """Get list of active call SIDs"""
        return list(self.dialog_states.keys())
    
    def get_call_count(self) -> int:
        """Get total number of active calls"""
        return len(self.dialog_states) 