import pytest
import time
from unittest.mock import Mock, patch
from ops_integrations.adapters.conversation_manager import ConversationManager

class TestConversationManager:
    """Unit tests for ConversationManager module"""
    
    @pytest.fixture
    def conversation_manager(self):
        """Create ConversationManager instance for testing"""
        return ConversationManager()
    
    def test_initialization(self, conversation_manager):
        """Test ConversationManager initialization"""
        assert conversation_manager.duplicate_window_seconds == 30
        assert conversation_manager.max_clarification_attempts == 3
        assert conversation_manager.max_repeated_utterances == 3
        assert len(conversation_manager.dialog_states) == 0
        assert len(conversation_manager.call_info_store) == 0
    
    def test_get_dialog_state_empty(self, conversation_manager):
        """Test getting dialog state for non-existent call"""
        call_sid = "test_call_123"
        state = conversation_manager.get_dialog_state(call_sid)
        assert state == {}
    
    def test_set_dialog_state(self, conversation_manager):
        """Test setting dialog state"""
        call_sid = "test_call_123"
        state = {"step": "awaiting_name", "customer_name": "John"}
        
        conversation_manager.set_dialog_state(call_sid, state)
        
        retrieved_state = conversation_manager.get_dialog_state(call_sid)
        assert retrieved_state["step"] == "awaiting_name"
        assert retrieved_state["customer_name"] == "John"
    
    def test_update_dialog_state(self, conversation_manager):
        """Test updating dialog state"""
        call_sid = "test_call_123"
        initial_state = {"step": "awaiting_name"}
        updates = {"customer_name": "John", "step": "name_collected"}
        
        conversation_manager.set_dialog_state(call_sid, initial_state)
        conversation_manager.update_dialog_state(call_sid, updates)
        
        retrieved_state = conversation_manager.get_dialog_state(call_sid)
        assert retrieved_state["step"] == "name_collected"
        assert retrieved_state["customer_name"] == "John"
    
    def test_clear_dialog_state(self, conversation_manager):
        """Test clearing dialog state"""
        call_sid = "test_call_123"
        state = {"step": "awaiting_name"}
        
        conversation_manager.set_dialog_state(call_sid, state)
        conversation_manager.clear_dialog_state(call_sid)
        
        retrieved_state = conversation_manager.get_dialog_state(call_sid)
        assert retrieved_state == {}
    
    def test_call_info_operations(self, conversation_manager):
        """Test call info operations"""
        call_sid = "test_call_123"
        info = {"from": "+1234567890", "to": "+0987654321"}
        
        # Set call info
        conversation_manager.set_call_info(call_sid, info)
        
        # Get call info
        retrieved_info = conversation_manager.get_call_info(call_sid)
        assert retrieved_info["from"] == "+1234567890"
        assert retrieved_info["to"] == "+0987654321"
        
        # Update call info
        updates = {"status": "active"}
        conversation_manager.update_call_info(call_sid, updates)
        
        updated_info = conversation_manager.get_call_info(call_sid)
        assert updated_info["from"] == "+1234567890"
        assert updated_info["status"] == "active"
    
    def test_should_suppress_duplicate_exact_match(self, conversation_manager):
        """Test duplicate suppression with exact match"""
        call_sid = "test_call_123"
        text = "Hello, this is a test"
        
        # First occurrence should not be suppressed
        assert conversation_manager.should_suppress_duplicate(call_sid, text) == False
        
        # Second occurrence within window should be suppressed
        assert conversation_manager.should_suppress_duplicate(call_sid, text) == True
    
    def test_should_suppress_duplicate_similar_text(self, conversation_manager):
        """Test duplicate suppression with similar text"""
        call_sid = "test_call_123"
        text1 = "Hello, this is a test"
        text2 = "Hello, this is a test."  # Different punctuation
        
        # First occurrence
        assert conversation_manager.should_suppress_duplicate(call_sid, text1) == False
        
        # Similar text should be suppressed
        assert conversation_manager.should_suppress_duplicate(call_sid, text2) == True
    
    def test_should_suppress_duplicate_outside_window(self, conversation_manager):
        """Test duplicate suppression outside time window"""
        call_sid = "test_call_123"
        text = "Hello, this is a test"
        
        # First occurrence
        assert conversation_manager.should_suppress_duplicate(call_sid, text) == False
        
        # Simulate time passing
        tracking = conversation_manager.duplicate_tracking[call_sid]
        tracking['last_ts'] = time.time() - 35  # Outside 30-second window
        
        # Should not be suppressed
        assert conversation_manager.should_suppress_duplicate(call_sid, text) == False
    
    def test_should_suppress_repeated_utterance(self, conversation_manager):
        """Test repeated utterance suppression"""
        call_sid = "test_call_123"
        text = "James Brown"
        
        # First occurrence
        assert conversation_manager.should_suppress_repeated_utterance(call_sid, text) == False
        
        # Second occurrence
        assert conversation_manager.should_suppress_repeated_utterance(call_sid, text) == False
        
        # Third occurrence (should be suppressed)
        assert conversation_manager.should_suppress_repeated_utterance(call_sid, text) == True
    
    def test_should_suppress_repeated_utterance_different_texts(self, conversation_manager):
        """Test repeated utterance suppression with different texts"""
        call_sid = "test_call_123"
        text1 = "James Brown"
        text2 = "Hello there"
        
        # Different texts should not be counted together
        assert conversation_manager.should_suppress_repeated_utterance(call_sid, text1) == False
        assert conversation_manager.should_suppress_repeated_utterance(call_sid, text2) == False
        assert conversation_manager.should_suppress_repeated_utterance(call_sid, text1) == False
    
    def test_clarification_attempts_tracking(self, conversation_manager):
        """Test clarification attempts tracking"""
        call_sid = "test_call_123"
        
        # Initial count should be 0
        assert conversation_manager.get_clarification_attempts(call_sid) == 0
        
        # Increment attempts
        count1 = conversation_manager.increment_clarification_attempts(call_sid)
        assert count1 == 1
        assert conversation_manager.get_clarification_attempts(call_sid) == 1
        
        count2 = conversation_manager.increment_clarification_attempts(call_sid)
        assert count2 == 2
        assert conversation_manager.get_clarification_attempts(call_sid) == 2
    
    def test_should_handoff_due_to_clarification_attempts(self, conversation_manager):
        """Test handoff decision based on clarification attempts"""
        call_sid = "test_call_123"
        
        # Should not handoff initially
        assert conversation_manager.should_handoff_due_to_clarification_attempts(call_sid) == False
        
        # Increment to max attempts
        conversation_manager.increment_clarification_attempts(call_sid)  # 1
        conversation_manager.increment_clarification_attempts(call_sid)  # 2
        conversation_manager.increment_clarification_attempts(call_sid)  # 3
        
        # Should handoff now
        assert conversation_manager.should_handoff_due_to_clarification_attempts(call_sid) == True
    
    def test_reset_clarification_attempts(self, conversation_manager):
        """Test resetting clarification attempts"""
        call_sid = "test_call_123"
        
        # Increment attempts
        conversation_manager.increment_clarification_attempts(call_sid)
        conversation_manager.increment_clarification_attempts(call_sid)
        
        # Reset
        conversation_manager.reset_clarification_attempts(call_sid)
        
        # Should be back to 0
        assert conversation_manager.get_clarification_attempts(call_sid) == 0
    
    def test_reset_repeated_utterances(self, conversation_manager):
        """Test resetting repeated utterances"""
        call_sid = "test_call_123"
        text = "James Brown"
        
        # Add some repeated utterances
        conversation_manager.should_suppress_repeated_utterance(call_sid, text)
        conversation_manager.should_suppress_repeated_utterance(call_sid, text)
        
        # Reset
        conversation_manager.reset_repeated_utterances(call_sid)
        
        # Should not be suppressed anymore
        assert conversation_manager.should_suppress_repeated_utterance(call_sid, text) == False
    
    def test_reset_all_counters(self, conversation_manager):
        """Test resetting all counters"""
        call_sid = "test_call_123"
        text = "James Brown"
        
        # Add some data
        conversation_manager.increment_clarification_attempts(call_sid)
        conversation_manager.should_suppress_repeated_utterance(call_sid, text)
        conversation_manager.should_suppress_duplicate(call_sid, text)
        
        # Reset all
        conversation_manager.reset_all_counters(call_sid)
        
        # All should be reset
        assert conversation_manager.get_clarification_attempts(call_sid) == 0
        assert conversation_manager.should_suppress_repeated_utterance(call_sid, text) == False
        assert conversation_manager.should_suppress_duplicate(call_sid, text) == False
    
    def test_get_conversation_summary(self, conversation_manager):
        """Test getting conversation summary"""
        call_sid = "test_call_123"
        
        # Set up some data
        conversation_manager.set_dialog_state(call_sid, {
            "step": "awaiting_name",
            "customer_name": "John"
        })
        conversation_manager.set_call_info(call_sid, {
            "from": "+1234567890",
            "to": "+0987654321",
            "start_ts": time.time() - 60  # 1 minute ago
        })
        conversation_manager.increment_clarification_attempts(call_sid)
        
        summary = conversation_manager.get_conversation_summary(call_sid)
        
        assert summary["call_sid"] == call_sid
        assert summary["dialog_step"] == "awaiting_name"
        assert summary["customer_name"] == "John"
        assert summary["clarification_attempts"] == 1
        assert summary["from_number"] == "+1234567890"
        assert summary["to_number"] == "+0987654321"
        assert summary["call_duration"] > 0
    
    def test_cleanup_call(self, conversation_manager):
        """Test cleaning up call data"""
        call_sid = "test_call_123"
        
        # Add data for the call
        conversation_manager.set_dialog_state(call_sid, {"step": "test"})
        conversation_manager.set_call_info(call_sid, {"from": "+1234567890"})
        conversation_manager.increment_clarification_attempts(call_sid)
        conversation_manager.should_suppress_repeated_utterance(call_sid, "test")
        conversation_manager.should_suppress_duplicate(call_sid, "test")
        
        # Cleanup
        conversation_manager.cleanup_call(call_sid)
        
        # All data should be removed
        assert conversation_manager.get_dialog_state(call_sid) == {}
        assert conversation_manager.get_call_info(call_sid) == {}
        assert conversation_manager.get_clarification_attempts(call_sid) == 0
        assert conversation_manager.should_suppress_repeated_utterance(call_sid, "test") == False
        assert conversation_manager.should_suppress_duplicate(call_sid, "test") == False
    
    def test_get_active_calls(self, conversation_manager):
        """Test getting active calls list"""
        # Initially empty
        assert conversation_manager.get_active_calls() == []
        
        # Add some calls
        conversation_manager.set_dialog_state("call_1", {"step": "test"})
        conversation_manager.set_dialog_state("call_2", {"step": "test"})
        
        active_calls = conversation_manager.get_active_calls()
        assert "call_1" in active_calls
        assert "call_2" in active_calls
        assert len(active_calls) == 2
    
    def test_get_call_count(self, conversation_manager):
        """Test getting call count"""
        # Initially 0
        assert conversation_manager.get_call_count() == 0
        
        # Add some calls
        conversation_manager.set_dialog_state("call_1", {"step": "test"})
        conversation_manager.set_dialog_state("call_2", {"step": "test"})
        
        assert conversation_manager.get_call_count() == 2
        
        # Remove one call
        conversation_manager.clear_dialog_state("call_1")
        assert conversation_manager.get_call_count() == 1
    
    def test_multiple_calls_isolation(self, conversation_manager):
        """Test that multiple calls are isolated"""
        call_sid_1 = "call_1"
        call_sid_2 = "call_2"
        
        # Set different states for different calls
        conversation_manager.set_dialog_state(call_sid_1, {"step": "step1"})
        conversation_manager.set_dialog_state(call_sid_2, {"step": "step2"})
        
        # States should be separate
        state1 = conversation_manager.get_dialog_state(call_sid_1)
        state2 = conversation_manager.get_dialog_state(call_sid_2)
        assert state1["step"] == "step1"
        assert state2["step"] == "step2"
        
        # Clarification attempts should be separate
        conversation_manager.increment_clarification_attempts(call_sid_1)
        assert conversation_manager.get_clarification_attempts(call_sid_1) == 1
        assert conversation_manager.get_clarification_attempts(call_sid_2) == 0
    
    def test_duplicate_suppression_case_insensitive(self, conversation_manager):
        """Test that duplicate suppression is case insensitive"""
        call_sid = "test_call_123"
        text1 = "Hello World"
        text2 = "hello world"
        
        # First occurrence
        assert conversation_manager.should_suppress_duplicate(call_sid, text1) == False
        
        # Case-insensitive duplicate should be suppressed
        assert conversation_manager.should_suppress_duplicate(call_sid, text2) == True
    
    def test_repeated_utterance_normalization(self, conversation_manager):
        """Test that repeated utterance detection normalizes text"""
        call_sid = "test_call_123"
        text1 = "Hello World"
        text2 = "  hello   world  "  # Extra whitespace
        
        # First occurrence
        assert conversation_manager.should_suppress_repeated_utterance(call_sid, text1) == False
        
        # Normalized duplicate should be counted
        assert conversation_manager.should_suppress_repeated_utterance(call_sid, text2) == False
        assert conversation_manager.should_suppress_repeated_utterance(call_sid, text1) == True 