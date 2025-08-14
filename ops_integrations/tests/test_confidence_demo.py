#!/usr/bin/env python3
"""
Confidence Control Demo

This script demonstrates how to control and test both transcription confidence 
and intent matching confidence in the voice assistant system.
"""

import os
import asyncio
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import the voice assistant functions
try:
    from adapters.phone import (
        classify_transcript_intent,
        calculate_pattern_matching_confidence,
        Settings,
        settings
    )
    from flows.intents import load_intents
except ImportError:
    import sys
    sys.path.append(os.path.dirname(__file__))
    from adapters.phone import (
        classify_transcript_intent,
        calculate_pattern_matching_confidence,
        Settings,
        settings
    )
    from flows.intents import load_intents

def demonstrate_confidence_controls():
    """Demonstrate how to configure confidence thresholds"""
    
    print("🎯 Voice Assistant Confidence Control Demo")
    print("=" * 50)
    
    print("\n📊 Current Confidence Settings:")
    print(f"- Transcription Threshold: {settings.TRANSCRIPTION_CONFIDENCE_THRESHOLD}")
    print(f"- Intent Confidence Threshold: {settings.INTENT_CONFIDENCE_THRESHOLD}") 
    print(f"- Overall Confidence Threshold: {settings.OVERALL_CONFIDENCE_THRESHOLD}")
    print(f"- Debug Mode: {settings.CONFIDENCE_DEBUG_MODE}")
    
    print("\n⚙️  How to Configure Confidence Thresholds:")
    print("Add these to your .env file or export as environment variables:")
    print()
    print("# Transcription Confidence (avg_logprob from Whisper)")
    print("TRANSCRIPTION_CONFIDENCE_THRESHOLD=-1.0   # Normal (default)")
    print("TRANSCRIPTION_CONFIDENCE_THRESHOLD=-0.5   # Stricter")
    print("TRANSCRIPTION_CONFIDENCE_THRESHOLD=-1.5   # More lenient")
    print()
    print("# Intent Matching Confidence (0.0-1.0)")
    print("INTENT_CONFIDENCE_THRESHOLD=0.6   # Default")
    print("INTENT_CONFIDENCE_THRESHOLD=0.8   # Stricter intent matching")
    print("INTENT_CONFIDENCE_THRESHOLD=0.4   # More lenient")
    print()
    print("# Overall Confidence for Human Handoff (0.0-1.0)")
    print("OVERALL_CONFIDENCE_THRESHOLD=0.7   # Default")
    print("OVERALL_CONFIDENCE_THRESHOLD=0.8   # Less handoff to humans")
    print("OVERALL_CONFIDENCE_THRESHOLD=0.6   # More handoff to humans")
    print()
    print("# Enable detailed confidence logging")
    print("CONFIDENCE_DEBUG_MODE=true")

async def test_intent_confidence():
    """Test intent confidence with various speech examples"""
    
    print("\n🧪 Testing Intent Confidence Scoring")
    print("=" * 40)
    
    # Load intent patterns
    intents_data = load_intents()
    
    test_phrases = [
        "my pipe just burst and water is everywhere",  # Should match EMERGENCY_FIX with high confidence
        "toilet won't flush properly",                  # Should match CLOG_BLOCKAGE with high confidence
        "faucet is dripping a little bit",            # Should match LEAKING_FIXTURE with medium confidence
        "I need someone to look at my plumbing",      # Should match GENERAL_INQUIRY with low confidence
        "hello there how are you doing",              # Should have very low confidence
        "install new water heater in basement",       # Should match INSTALL_REQUEST with high confidence
        "no hot water this morning",                   # Should match WATER_HEATER_ISSUE with high confidence
        "can you give me a quote for fixing my sink", # Should match QUOTE_REQUEST with high confidence
    ]
    
    for phrase in test_phrases:
        print(f"\n📝 Testing: '{phrase}'")
        
        # Test pattern matching confidence
        pattern_confidence = calculate_pattern_matching_confidence(phrase, intents_data)
        best_intent = max(pattern_confidence, key=pattern_confidence.get) if pattern_confidence else "NONE"
        best_confidence = pattern_confidence.get(best_intent, 0.0)
        
        print(f"   🎯 Best Match: {best_intent} (confidence: {best_confidence:.3f})")
        
        # Test full intent classification with GPT
        try:
            intent, full_confidence = await classify_transcript_intent(phrase)
            print(f"   🤖 GPT Classification: {intent} (confidence: {full_confidence:.3f})")
            
            # Show if this would trigger handoff
            if full_confidence < settings.INTENT_CONFIDENCE_THRESHOLD:
                print(f"   🚨 Would trigger handoff (< {settings.INTENT_CONFIDENCE_THRESHOLD})")
            else:
                print(f"   ✅ Would proceed with automation")
                
        except Exception as e:
            print(f"   ❌ Error in GPT classification: {e}")
        
        # Show top 3 pattern matches
        top_matches = sorted(pattern_confidence.items(), key=lambda x: x[1], reverse=True)[:3]
        if top_matches:
            print("   📊 Top Pattern Matches:")
            for intent_name, conf in top_matches:
                if conf > 0:
                    print(f"      {intent_name}: {conf:.3f}")

def show_confidence_tuning_guide():
    """Show guide for tuning confidence thresholds"""
    
    print("\n🎛️  Confidence Tuning Guide")
    print("=" * 30)
    
    print("\n🎤 TRANSCRIPTION_CONFIDENCE_THRESHOLD:")
    print("  Controls when to accept/reject speech transcription")
    print("  - Based on OpenAI Whisper's avg_logprob score")
    print("  - More negative = lower confidence")
    print("  - Recommended values:")
    print("    • -1.5: Very lenient (accepts unclear speech)")
    print("    • -1.0: Normal (default, balanced)")
    print("    • -0.5: Strict (only clear speech)")
    print("    • -0.3: Very strict (only very clear speech)")
    
    print("\n🎯 INTENT_CONFIDENCE_THRESHOLD:")
    print("  Controls intent matching quality")
    print("  - Based on semantic similarity to intent patterns")
    print("  - Range: 0.0 (accept any) to 1.0 (perfect match only)")
    print("  - Recommended values:")
    print("    • 0.4: Lenient (accepts loose matches)")
    print("    • 0.6: Normal (default, good balance)")
    print("    • 0.8: Strict (only strong matches)")
    print("    • 0.9: Very strict (only near-perfect matches)")
    
    print("\n🤝 OVERALL_CONFIDENCE_THRESHOLD:")
    print("  Controls when to handoff to human")
    print("  - Combined score of all confidence factors")
    print("  - Range: 0.0 (never handoff) to 1.0 (always handoff)")
    print("  - Recommended values:")
    print("    • 0.5: Lenient (rarely handoff)")
    print("    • 0.7: Normal (default, balanced handoff)")
    print("    • 0.8: Conservative (frequent handoff)")
    print("    • 0.9: Very conservative (almost always handoff)")

def main():
    """Main demo function"""
    demonstrate_confidence_controls()
    
    # Run async tests
    asyncio.run(test_intent_confidence())
    
    show_confidence_tuning_guide()
    
    print("\n🏁 Demo Complete!")
    print("\nTo start using these controls:")
    print("1. Set your desired thresholds in .env file")
    print("2. Enable CONFIDENCE_DEBUG_MODE=true for detailed logging")
    print("3. Monitor logs to tune thresholds for your use case")
    print("4. Test with various speech samples to validate settings")

if __name__ == "__main__":
    main() 