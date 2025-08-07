import json
import os
from typing import Dict, List, Any

def load_intents() -> Dict[str, Any]:
    """Load intents from intents.json file."""
    current_dir = os.path.dirname(__file__)
    intents_path = os.path.join(current_dir, 'intents.json')
    
    with open(intents_path, 'r') as f:
        return json.load(f)

def get_intent_tags() -> List[str]:
    """Get list of all available intent tags."""
    intents_data = load_intents()
    return [intent['tag'] for intent in intents_data['intents']]

def get_intent_patterns(tag: str) -> List[str]:
    """Get patterns for a specific intent tag."""
    intents_data = load_intents()
    for intent in intents_data['intents']:
        if intent['tag'] == tag:
            return intent['patterns']
    return [] 