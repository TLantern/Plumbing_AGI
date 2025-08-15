import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from ops_integrations.adapters.intent_extractor import IntentExtractor

class TestIntentExtractor:
    """Unit tests for IntentExtractor module"""
    
    @pytest.fixture
    def intent_extractor(self):
        """Create IntentExtractor instance for testing"""
        return IntentExtractor(openai_api_key="test_key")
    
    def test_initialization(self, intent_extractor):
        """Test IntentExtractor initialization"""
        assert intent_extractor.intent_confidence_threshold == 0.5
        assert intent_extractor.overall_confidence_threshold == 0.6
        assert 'leak' in intent_extractor.plumbing_keywords
        assert 'clog' in intent_extractor.plumbing_keywords
        assert 'water_heater' in intent_extractor.plumbing_keywords
        assert len(intent_extractor.functions) == 1
    
    def test_plumbing_keywords_structure(self, intent_extractor):
        """Test plumbing keywords structure"""
        keywords = intent_extractor.plumbing_keywords
        
        # Check that all expected categories exist
        expected_categories = ['leak', 'clog', 'water_heater', 'toilet', 'faucet', 'emergency', 'installation', 'repair']
        for category in expected_categories:
            assert category in keywords
            assert isinstance(keywords[category], list)
            assert len(keywords[category]) > 0
    
    def test_infer_job_type_from_text_leak(self, intent_extractor):
        """Test job type inference for leak-related text"""
        text = "There's a water leak in my kitchen"
        job_type = intent_extractor._infer_job_type_from_text(text)
        assert job_type == 'leak'
    
    def test_infer_job_type_from_text_clog(self, intent_extractor):
        """Test job type inference for clog-related text"""
        text = "My bathroom sink is clogged"
        job_type = intent_extractor._infer_job_type_from_text(text)
        assert job_type == 'clog'
    
    def test_infer_job_type_from_text_water_heater(self, intent_extractor):
        """Test job type inference for water heater text"""
        text = "My heater tank is not working"
        job_type = intent_extractor._infer_job_type_from_text(text)
        assert job_type == 'water_heater'
    
    def test_infer_job_type_from_text_no_match(self, intent_extractor):
        """Test job type inference with no matching keywords"""
        text = "Hello, how are you today?"
        job_type = intent_extractor._infer_job_type_from_text(text)
        assert job_type is None
    
    def test_infer_urgency_emergency(self, intent_extractor):
        """Test urgency inference for emergency text"""
        emergency_texts = [
            "This is an emergency",
            "I need help urgently",
            "My pipe burst immediately",
            "There's a flood now"
        ]
        
        for text in emergency_texts:
            urgency = intent_extractor._infer_urgency_from_text(text)
            assert urgency == 'emergency'
    
    def test_infer_urgency_same_day(self, intent_extractor):
        """Test urgency inference for same-day text"""
        same_day_texts = [
            "I need this done today",
            "Can you come tonight",
            "I need this asap",
            "Please come soon"
        ]
        
        for text in same_day_texts:
            urgency = intent_extractor._infer_urgency_from_text(text)
            assert urgency == 'same_day'
    
    def test_infer_urgency_flex(self, intent_extractor):
        """Test urgency inference for flexible text"""
        flex_texts = [
            "I need a plumber",
            "Can you help me",
            "I have a problem",
            "When can you come"
        ]
        
        for text in flex_texts:
            urgency = intent_extractor._infer_urgency_from_text(text)
            assert urgency == 'flex'
    
    def test_calculate_intent_confidence_with_keywords(self, intent_extractor):
        """Test intent confidence calculation with plumbing keywords"""
        text = "I have a leak and a clog in my bathroom"
        args = {'intent': 'BOOK_JOB'}
        
        confidence = intent_extractor._calculate_intent_confidence(text, args)
        
        # Should have high confidence due to multiple keywords
        assert confidence > 0.6
        assert confidence <= 0.9
    
    def test_calculate_intent_confidence_with_service_indicators(self, intent_extractor):
        """Test intent confidence calculation with service indicators"""
        text = "I need help with a problem"
        args = {'intent': 'BOOK_JOB'}
        
        confidence = intent_extractor._calculate_intent_confidence(text, args)
        assert confidence == 0.6
    
    def test_calculate_intent_confidence_no_indicators(self, intent_extractor):
        """Test intent confidence calculation with no indicators"""
        text = "Hello, how are you?"
        args = {'intent': 'BOOK_JOB'}
        
        confidence = intent_extractor._calculate_intent_confidence(text, args)
        assert confidence == 0.3
    
    def test_calculate_confidence_scores_with_job_type(self, intent_extractor):
        """Test confidence score calculation with job type"""
        args = {
            'intent': 'BOOK_JOB',
            'job': {
                'type': 'leak',
                'urgency': 'emergency'
            }
        }
        intent_confidence = 0.7
        
        confidence = intent_extractor._calculate_confidence_scores(args, intent_confidence)
        
        assert confidence['intent'] == 0.7
        assert confidence['fields']['type'] == 0.9  # Known job type
        assert confidence['fields']['urgency'] == 0.8  # Known urgency
        assert confidence['overall'] > 0.7  # Average should be high
    
    def test_calculate_confidence_scores_missing_fields(self, intent_extractor):
        """Test confidence score calculation with missing fields"""
        args = {
            'intent': 'BOOK_JOB',
            'job': {}
        }
        intent_confidence = 0.5
        
        confidence = intent_extractor._calculate_confidence_scores(args, intent_confidence)
        
        assert confidence['intent'] == 0.5
        assert confidence['fields']['type'] == 0.0  # Missing job type
        assert confidence['fields']['urgency'] == 0.0  # Missing urgency
        # Overall is average of all scores: (0.5 + 0.0 + 0.0) / 3 = 0.167
        assert abs(confidence['overall'] - 0.167) < 0.001
    
    def test_create_fallback_response(self, intent_extractor):
        """Test fallback response creation"""
        text = "I need help"
        response = intent_extractor._create_fallback_response(text)
        
        assert response['intent'] == 'BOOK_JOB'
        assert response['customer']['name'] is None
        assert response['job']['description'] == text
        assert response['confidence']['overall'] == 0.0
    
    def test_should_handoff_to_human_low_overall_confidence(self, intent_extractor):
        """Test handoff decision with low overall confidence"""
        args = {
            'confidence': {
                'overall': 0.4,  # Below threshold
                'intent': 0.7
            }
        }
        
        assert intent_extractor.should_handoff_to_human(args) == True
    
    def test_should_handoff_to_human_low_intent_confidence(self, intent_extractor):
        """Test handoff decision with low intent confidence"""
        args = {
            'confidence': {
                'overall': 0.7,
                'intent': 0.3  # Below threshold
            }
        }
        
        assert intent_extractor.should_handoff_to_human(args) == True
    
    def test_should_handoff_to_human_missing_fields(self, intent_extractor):
        """Test handoff decision with missing critical fields"""
        args = {
            'confidence': {
                'overall': 0.7,
                'intent': 0.7
            },
            'job': {}  # Missing type and urgency
        }
        
        assert intent_extractor.should_handoff_to_human(args) == True
    
    def test_should_handoff_to_human_acceptable(self, intent_extractor):
        """Test handoff decision with acceptable confidence"""
        args = {
            'confidence': {
                'overall': 0.7,
                'intent': 0.7
            },
            'job': {
                'type': 'leak',
                'urgency': 'emergency'
            }
        }
        
        assert intent_extractor.should_handoff_to_human(args) == False
    
    @pytest.mark.asyncio
    async def test_classify_transcript_intent_cancel(self, intent_extractor):
        """Test transcript intent classification for cancel"""
        text = "I want to cancel my appointment"
        intent, confidence = await intent_extractor.classify_transcript_intent(text)
        
        assert intent == 'CANCEL_JOB'
        assert confidence == 0.8
    
    @pytest.mark.asyncio
    async def test_classify_transcript_intent_transfer(self, intent_extractor):
        """Test transcript intent classification for transfer"""
        text = "I want to speak to a human"
        intent, confidence = await intent_extractor.classify_transcript_intent(text)
        
        assert intent == 'TRANSFER'
        assert confidence == 0.9
    
    @pytest.mark.asyncio
    async def test_classify_transcript_intent_question(self, intent_extractor):
        """Test transcript intent classification for question"""
        text = "I have a question about your services"
        intent, confidence = await intent_extractor.classify_transcript_intent(text)
        
        assert intent == 'GENERAL_QUESTION'
        assert confidence == 0.7
    
    @pytest.mark.asyncio
    async def test_classify_transcript_intent_default(self, intent_extractor):
        """Test transcript intent classification default"""
        text = "Hello, I need plumbing help"
        intent, confidence = await intent_extractor.classify_transcript_intent(text)
        
        assert intent == 'BOOK_JOB'
        assert confidence == 0.6
    
    @pytest.mark.asyncio
    async def test_extract_intent_from_text_success(self, intent_extractor):
        """Test successful intent extraction"""
        text = "I have a leak in my kitchen"
        
        with patch.object(intent_extractor.openai_client.chat.completions, 'create') as mock_create:
            # Mock OpenAI response with function call
            mock_response = Mock()
            mock_choice = Mock()
            mock_message = Mock()
            mock_tool_call = Mock()
            mock_function = Mock()
            
            mock_function.arguments = '{"intent": "BOOK_JOB", "job": {"type": "leak", "urgency": "flex"}}'
            mock_tool_call.function = mock_function
            mock_message.tool_calls = [mock_tool_call]
            mock_choice.message = mock_message
            mock_response.choices = [mock_choice]
            mock_create.return_value = mock_response
            
            result = await intent_extractor.extract_intent_from_text(text)
            
            assert result['intent'] == 'BOOK_JOB'
            assert result['job']['type'] == 'leak'
            assert result['job']['urgency'] == 'flex'
            assert 'confidence' in result
    
    @pytest.mark.asyncio
    async def test_extract_intent_from_text_fallback(self, intent_extractor):
        """Test intent extraction fallback when no function call"""
        text = "I need help"
        
        with patch.object(intent_extractor.openai_client.chat.completions, 'create') as mock_create:
            # Mock OpenAI response without function call
            mock_response = Mock()
            mock_choice = Mock()
            mock_message = Mock()
            mock_message.tool_calls = None
            mock_choice.message = mock_message
            mock_response.choices = [mock_choice]
            mock_create.return_value = mock_response
            
            result = await intent_extractor.extract_intent_from_text(text)
            
            assert result['intent'] == 'BOOK_JOB'
            assert result['job']['description'] == text
            assert result['confidence']['overall'] == 0.0
    
    @pytest.mark.asyncio
    async def test_extract_intent_from_text_exception(self, intent_extractor):
        """Test intent extraction with exception"""
        text = "I need help"
        
        with patch.object(intent_extractor.openai_client.chat.completions, 'create') as mock_create:
            mock_create.side_effect = Exception("API error")
            
            result = await intent_extractor.extract_intent_from_text(text)
            
            assert result['intent'] == 'BOOK_JOB'
            assert result['job']['description'] == text
            assert result['confidence']['overall'] == 0.0
    
    def test_validate_and_enhance_extraction(self, intent_extractor):
        """Test validation and enhancement of extracted data"""
        args = {
            'intent': 'BOOK_JOB',
            'job': {}
        }
        original_text = "I have a leak in my kitchen"
        
        result = intent_extractor._validate_and_enhance_extraction(args, original_text)
        
        assert result['intent'] == 'BOOK_JOB'
        assert result['job']['type'] == 'leak'  # Should be inferred
        assert result['job']['urgency'] == 'flex'  # Should be inferred
        assert 'confidence' in result
        assert result['confidence']['intent'] > 0.5  # Should have reasonable confidence 