#!/usr/bin/env python3
"""
Test script to demonstrate transcription cleaning functionality for FEMA.gov references and repeated phrases.
"""

import sys
import os
import re

# Add the parent directory to the path to import the phone module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'adapters'))

def clean_and_filter_transcription(text: str) -> tuple[str, bool]:
    """
    Clean transcription text by removing unwanted patterns and repeated phrases.
    
    Returns:
        tuple: (cleaned_text, should_suppress_entirely)
    """
    if not text:
        return "", True
    
    # Original text for logging
    original_text = text
    
    # Convert to lowercase for pattern matching
    text_lower = text.lower()
    
    # Patterns to completely suppress the entire transcription
    suppression_patterns = [
        # FEMA references
        r'for more information,?\s*visit\s*www\.fema\.gov',
        r'visit\s*www\.fema\.gov',
        r'fema\.gov',
        r'federal emergency management agency',
        # Common transcription artifacts
        r'thank you for watching',
        r'subscribe.*channel',
        r'like.*comment',
        r'video.*description',
        r'pissedconsumer',
        # URLs and domains
        r'https?://[^\s]+',
        r'www\.[^\s]+',
        r'\b[a-z0-9-]+\.[a-z]{2,6}\b',
    ]
    
    # Check if we should suppress the entire transcription
    for pattern in suppression_patterns:
        if re.search(pattern, text_lower):
            print(f"🚫 Suppressing transcription due to pattern '{pattern}': '{original_text}'")
            return "", True
    
    # Clean text by removing unwanted content but keep the rest
    cleaned_text = text
    
    # Remove specific phrases (case-insensitive)
    removal_patterns = [
        r'for more information,?\s*visit\s*www\.fema\.gov',
        r'visit\s*www\.fema\.gov',
        r'fema\.gov',
        r'thank you for watching',
        r'subscribe to.*channel',
        r'like and comment',
        r'check the description',
    ]
    
    for pattern in removal_patterns:
        cleaned_text = re.sub(pattern, '', cleaned_text, flags=re.IGNORECASE)
    
    # Remove excessive repeated words/phrases
    cleaned_text = remove_repeated_phrases(cleaned_text)
    
    # Clean up extra whitespace
    cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
    
    # If cleaning removed too much content, suppress
    if not cleaned_text or len(cleaned_text.strip()) < 3:
        print(f"🚫 Suppressing transcription after cleaning (too little content): '{original_text}' -> '{cleaned_text}'")
        return "", True
    
    # Log if we cleaned anything
    if cleaned_text != original_text:
        print(f"🧹 Cleaned transcription: '{original_text}' -> '{cleaned_text}'")
    
    return cleaned_text, False

def remove_repeated_phrases(text: str) -> str:
    """
    Remove excessive repetition of words and short phrases.
    Examples:
    - "second, second, second, second" -> "second"
    - "the the the problem" -> "the problem"
    - "help me help me help me" -> "help me"
    """
    if not text:
        return text
    
    # Split into words
    words = text.split()
    if len(words) <= 2:
        return text
    
    # Remove consecutive repeated words
    cleaned_words = []
    i = 0
    while i < len(words):
        word = words[i]
        cleaned_words.append(word)
        
        # Count consecutive repetitions of this word
        repetitions = 1
        j = i + 1
        while j < len(words) and words[j].lower().strip('.,!?') == word.lower().strip('.,!?'):
            repetitions += 1
            j += 1
        
        # If we found repetitions, skip them (keep only the first occurrence)
        if repetitions > 1:
            print(f"🔄 Removed {repetitions-1} repetitions of word '{word}'")
            i = j
        else:
            i += 1
    
    # Join back into text
    result = ' '.join(cleaned_words)
    
    # Handle repeated short phrases (2-3 words)
    # Look for patterns like "help me help me" or "can you can you"
    for phrase_length in [2, 3]:
        if len(cleaned_words) >= phrase_length * 2:
            # Check for repeated phrases
            new_words = []
            i = 0
            while i < len(cleaned_words):
                if i + phrase_length * 2 <= len(cleaned_words):
                    # Get current phrase and next phrase
                    current_phrase = cleaned_words[i:i+phrase_length]
                    next_phrase = cleaned_words[i+phrase_length:i+phrase_length*2]
                    
                    # Normalize for comparison (remove punctuation, lowercase)
                    current_normalized = [w.lower().strip('.,!?') for w in current_phrase]
                    next_normalized = [w.lower().strip('.,!?') for w in next_phrase]
                    
                    if current_normalized == next_normalized:
                        # Found repetition, count how many times it repeats
                        phrase_repetitions = 1
                        check_pos = i + phrase_length
                        while check_pos + phrase_length <= len(cleaned_words):
                            check_phrase = cleaned_words[check_pos:check_pos+phrase_length]
                            check_normalized = [w.lower().strip('.,!?') for w in check_phrase]
                            if check_normalized == current_normalized:
                                phrase_repetitions += 1
                                check_pos += phrase_length
                            else:
                                break
                        
                        # Keep only first occurrence
                        if phrase_repetitions > 1:
                            print(f"🔄 Removed {phrase_repetitions-1} repetitions of phrase '{' '.join(current_phrase)}'")
                        new_words.extend(current_phrase)
                        i = check_pos
                    else:
                        new_words.append(cleaned_words[i])
                        i += 1
                else:
                    new_words.append(cleaned_words[i])
                    i += 1
            
            cleaned_words = new_words
            result = ' '.join(cleaned_words)
    
    return result

def test_transcription_cleaning():
    """Test the transcription cleaning functionality with various examples."""
    
    test_cases = [
        # FEMA.gov suppression cases
        {
            "input": "For more information, visit www.FEMA.gov",
            "description": "FEMA.gov reference (should be completely suppressed)"
        },
        {
            "input": "My toilet is broken. For more information, visit www.FEMA.gov",
            "description": "Plumbing issue with FEMA.gov reference (should remove FEMA part)"
        },
        {
            "input": "I need help with plumbing visit www.fema.gov please",
            "description": "Mixed content with FEMA.gov"
        },
        
        # Repeated phrase cases
        {
            "input": "Second, second, second, second",
            "description": "Repeated word 'second'"
        },
        {
            "input": "The the the problem is in my kitchen",
            "description": "Repeated word 'the'"
        },
        {
            "input": "Help me help me help me with my sink",
            "description": "Repeated phrase 'help me'"
        },
        {
            "input": "Can you can you can you come today?",
            "description": "Repeated phrase 'can you'"
        },
        {
            "input": "My water heater water heater is broken broken broken",
            "description": "Multiple types of repetition"
        },
        
        # Other suppression patterns
        {
            "input": "Thank you for watching this video",
            "description": "Video artifact (should be suppressed)"
        },
        {
            "input": "Visit www.example.com for details",
            "description": "Website reference (should be suppressed)"
        },
        
        # Valid content that should pass through
        {
            "input": "My kitchen sink is clogged and won't drain",
            "description": "Valid plumbing issue (should pass through)"
        },
        {
            "input": "I need a plumber to come today for an emergency",
            "description": "Valid emergency request (should pass through)"
        },
        
        # Mixed cases
        {
            "input": "My sink sink is clogged. For more information visit www.FEMA.gov",
            "description": "Valid issue with repetition and FEMA.gov"
        }
    ]
    
    print("=" * 80)
    print("TRANSCRIPTION CLEANING TEST RESULTS")
    print("=" * 80)
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{i}. {test_case['description']}")
        print(f"   Input:  '{test_case['input']}'")
        
        cleaned_text, should_suppress = clean_and_filter_transcription(test_case['input'])
        
        if should_suppress:
            print(f"   Result: ❌ SUPPRESSED ENTIRELY")
        else:
            print(f"   Result: ✅ CLEANED -> '{cleaned_text}'")
        
        print("-" * 60)
    
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print("✅ = Text was cleaned and allowed through")
    print("❌ = Text was completely suppressed")
    print("🧹 = Text was modified during cleaning")
    print("🔄 = Repetitions were removed")
    print("🚫 = Suppression patterns were detected")

if __name__ == "__main__":
    test_transcription_cleaning() 