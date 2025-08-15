import asyncio
import logging
import json
import re
from typing import Dict, Any, Optional, Tuple, List
from openai import OpenAI
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class IntentExtractor:
    """Handles intent extraction and classification from customer text"""
    
    def __init__(self, openai_api_key: str):
        self.openai_client = OpenAI(api_key=openai_api_key)
        
        # Confidence thresholds
        self.intent_confidence_threshold = 0.5
        self.overall_confidence_threshold = 0.6
        
        # Plumbing service keywords
        self.plumbing_keywords = {
            'leak': ['leak', 'leaking', 'drip', 'dripping', 'water', 'pipe'],
            'clog': ['clog', 'clogged', 'blocked', 'drain', 'sink', 'toilet', 'shower'],
            'water_heater': ['water heater', 'hot water', 'heater', 'tank'],
            'toilet': ['toilet', 'flush', 'running', 'overflow'],
            'faucet': ['faucet', 'tap', 'sink', 'handle'],
            'emergency': ['emergency', 'urgent', 'immediately', 'now', 'broken', 'flood'],
            'installation': ['install', 'new', 'replace', 'upgrade', 'put in'],
            'repair': ['repair', 'fix', 'broken', 'not working', 'issue']
        }
        
        # Function definition for OpenAI
        self.functions = [
            {
                "type": "function",
                "function": {
                    "name": "extract_plumbing_intent",
                    "description": "Extract structured information from customer plumbing service requests",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "intent": {
                                "type": "string",
                                "enum": ["BOOK_JOB", "CANCEL_JOB", "MODIFY_JOB", "GENERAL_QUESTION", "TRANSFER"],
                                "description": "Primary intent of the customer"
                            },
                            "customer": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string", "description": "Customer name if provided"},
                                    "phone": {"type": "string", "description": "Phone number if provided"},
                                    "email": {"type": "string", "description": "Email if provided"}
                                }
                            },
                            "job": {
                                "type": "object",
                                "properties": {
                                    "type": {
                                        "type": "string",
                                        "enum": [
                                            "leak", "clog", "water_heater", "toilet", "faucet", 
                                            "drain_cleaning", "sewer_cam", "gas_line", "plumbing_repair",
                                            "plumbing_installation", "plumbing_replacement", "plumbing_maintenance"
                                        ],
                                        "description": "Type of plumbing service needed"
                                    },
                                    "urgency": {
                                        "type": "string",
                                        "enum": ["emergency", "same_day", "flex"],
                                        "description": "Urgency level of the service"
                                    },
                                    "description": {"type": "string", "description": "Detailed description of the issue"}
                                }
                            },
                            "location": {
                                "type": "object",
                                "properties": {
                                    "raw_address": {"type": "string", "description": "Address if provided"},
                                    "validated": {"type": "boolean", "description": "Whether address was validated"}
                                }
                            }
                        },
                        "required": ["intent"]
                    }
                }
            }
        ]
    
    async def extract_intent_from_text(self, text: str, call_sid: str = None) -> Dict[str, Any]:
        """Extract structured intent from customer text"""
        try:
            # Enhanced prompt with better context and examples
            enhanced_prompt = f"""
You are a plumbing service booking assistant. Extract structured information from customer requests.

CUSTOMER REQUEST: "{text}"

INSTRUCTIONS:
1. Identify the specific plumbing job type from the comprehensive list of services
2. Determine urgency: emergency (immediate), same_day (today), flex (anytime)
3. Extract customer name and contact info
4. Parse address information
5. Assess confidence and handoff needs

EXAMPLES:
- "kitchen sink is clogged" → job_type: clog, urgency: flex
- "bathroom sink won't drain" → job_type: clog, urgency: flex
- "toilet is running constantly" → job_type: toilet, urgency: flex
- "water heater burst" → job_type: water_heater, urgency: emergency
- "need new faucet installed" → job_type: faucet, urgency: flex
- "sewer camera inspection" → job_type: sewer_cam, urgency: flex
- "drain smells bad" → job_type: sewer_cam, urgency: flex
- "can come tomorrow" → urgency: flex
- "need today" → urgency: same_day
- "emergency leak" → urgency: emergency

Be precise and extract all available information. Match to the most specific service type available.
"""

            # Send to OpenAI with function calling
            response = await asyncio.to_thread(
                self.openai_client.chat.completions.create,
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": enhanced_prompt}],
                tools=self.functions,
                tool_choice="auto",
                temperature=0.1,
                max_tokens=1000
            )
            
            msg = response.choices[0].message
            if msg.tool_calls:
                tool_call = msg.tool_calls[0]
                args = json.loads(tool_call.function.arguments)
                
                # Post-process and validate the extracted data
                validated_args = self._validate_and_enhance_extraction(args, text, call_sid)
                return validated_args
            
            # Fallback: no function call, return freeform description
            return self._create_fallback_response(text)
            
        except Exception as e:
            logger.error(f"Intent extraction failed for {call_sid}: {e}")
            return self._create_fallback_response(text)
    
    def _validate_and_enhance_extraction(self, args: Dict[str, Any], original_text: str, call_sid: str = None) -> Dict[str, Any]:
        """Validate and enhance extracted data with additional processing"""
        
        # Ensure required fields exist
        if 'intent' not in args:
            args['intent'] = 'BOOK_JOB'
        
        # Calculate intent confidence
        intent_confidence = self._calculate_intent_confidence(original_text, args)
        
        # Enhance job type recognition with keyword matching
        if not args.get('job', {}).get('type'):
            args['job'] = args.get('job', {})
            args['job']['type'] = self._infer_job_type_from_text(original_text)
        
        # Enhance urgency detection
        if not args.get('job', {}).get('urgency'):
            args['job']['urgency'] = self._infer_urgency_from_text(original_text)
        
        # Add confidence scores
        confidence = self._calculate_confidence_scores(args, intent_confidence)
        args['confidence'] = confidence
        
        return args
    
    def _calculate_intent_confidence(self, text: str, args: Dict[str, Any]) -> float:
        """Calculate confidence in intent classification"""
        text_lower = text.lower()
        
        # Check for clear plumbing keywords
        plumbing_keywords_found = 0
        for category, keywords in self.plumbing_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                plumbing_keywords_found += 1
        
        # Base confidence on keyword presence
        if plumbing_keywords_found > 0:
            return min(0.9, 0.5 + (plumbing_keywords_found * 0.1))
        
        # Check for general service indicators
        service_indicators = ['help', 'service', 'problem', 'issue', 'broken', 'fix']
        if any(indicator in text_lower for indicator in service_indicators):
            return 0.6
        
        return 0.3
    
    def _infer_job_type_from_text(self, text: str) -> Optional[str]:
        """Infer job type from text using keyword matching"""
        text_lower = text.lower()
        
        # Check each category
        for job_type, keywords in self.plumbing_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                return job_type
        
        return None
    
    def _infer_urgency_from_text(self, text: str) -> str:
        """Infer urgency from text"""
        text_lower = text.lower()
        
        emergency_keywords = ['emergency', 'urgent', 'immediately', 'now', 'broken', 'flood', 'burst']
        if any(keyword in text_lower for keyword in emergency_keywords):
            return 'emergency'
        
        today_keywords = ['today', 'tonight', 'asap', 'soon']
        if any(keyword in text_lower for keyword in today_keywords):
            return 'same_day'
        
        return 'flex'
    
    def _calculate_confidence_scores(self, args: Dict[str, Any], intent_confidence: float) -> Dict[str, Any]:
        """Calculate confidence scores for different aspects"""
        confidence = {
            "overall": 0.0,
            "intent": intent_confidence,
            "fields": {}
        }
        
        # Job type confidence
        job_type = args.get('job', {}).get('type')
        if job_type:
            confidence["fields"]["type"] = 0.9 if job_type in self.plumbing_keywords else 0.7
        else:
            confidence["fields"]["type"] = 0.0
        
        # Urgency confidence
        urgency = args.get('job', {}).get('urgency')
        if urgency:
            confidence["fields"]["urgency"] = 0.8 if urgency in ['emergency', 'same_day', 'flex'] else 0.5
        else:
            confidence["fields"]["urgency"] = 0.0
        
        # Overall confidence (average of all scores)
        field_scores = list(confidence["fields"].values())
        field_scores.append(intent_confidence)
        if field_scores:
            confidence["overall"] = sum(field_scores) / len(field_scores)
        
        return confidence
    
    def _create_fallback_response(self, text: str) -> Dict[str, Any]:
        """Create a fallback response when function calling fails"""
        return {
            "intent": "BOOK_JOB",
            "customer": {"name": None, "phone": None, "email": None},
            "job": {"type": None, "urgency": None, "description": text},
            "location": {"raw_address": None, "validated": False},
            "confidence": {"overall": 0.0, "intent": 0.3, "fields": {}}
        }
    
    def should_handoff_to_human(self, args: Dict[str, Any], call_sid: str = None) -> bool:
        """Determine if human handoff is needed"""
        confidence = args.get('confidence', {})
        overall_confidence = confidence.get("overall", 0.0)
        intent_confidence = confidence.get("intent", 0.0)
        
        # Check single-instance thresholds
        if overall_confidence < self.overall_confidence_threshold:
            return True
        
        if intent_confidence < self.intent_confidence_threshold:
            return True
        
        # Check for missing critical fields
        required_fields = ['job.type', 'job.urgency']
        missing_fields = 0
        
        for field in required_fields:
            field_parts = field.split('.')
            value = args
            for part in field_parts:
                value = value.get(part, {}) if isinstance(value, dict) else None
                if value is None:
                    break
            
            if not value:
                missing_fields += 1
        
        if missing_fields >= 2:
            return True
        
        return False
    
    async def classify_transcript_intent(self, text: str) -> Tuple[str, float]:
        """Classify the intent of a transcript and return confidence"""
        try:
            # Simple keyword-based classification
            text_lower = text.lower()
            
            # Check for specific intents
            if any(word in text_lower for word in ['cancel', 'stop', 'never mind']):
                return 'CANCEL_JOB', 0.8
            
            if any(word in text_lower for word in ['transfer', 'human', 'person', 'operator']):
                return 'TRANSFER', 0.9
            
            if any(word in text_lower for word in ['question', 'ask', 'wonder']):
                return 'GENERAL_QUESTION', 0.7
            
            # Default to booking
            return 'BOOK_JOB', 0.6
            
        except Exception as e:
            logger.error(f"Intent classification failed: {e}")
            return 'BOOK_JOB', 0.3 