"""
Plumbing Services Configuration
Contains all service types, keywords, and related configurations for the phone intent recognition system.
Enhanced with BERT NLP for semantic understanding.
"""

import json
import os
from typing import Dict, List, Any, Tuple

# Handle optional dependencies
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    print("Warning: numpy not available. BERT functionality will be limited.")

try:
    from sentence_transformers import SentenceTransformer
    from sklearn.metrics.pairwise import cosine_similarity
    BERT_AVAILABLE = True
    print("Using sentence-transformers for BERT functionality")
except ImportError:
    print("Warning: sentence-transformers not available. Using keyword-based detection only.")
    BERT_AVAILABLE = False
    SentenceTransformer = None
    cosine_similarity = None

# Initialize BERT model for semantic similarity
BERT_MODEL = None
if BERT_AVAILABLE:
    try:
        BERT_MODEL = SentenceTransformer('all-MiniLM-L6-v2')
    except Exception as e:
        print(f"Warning: Could not initialize BERT model: {e}")
        BERT_AVAILABLE = False

# All available plumbing service types
PLUMBING_SERVICES = [
    # Original general categories
    "leak", "water_heater", "clog", "gas_line", "backflow_test", "sewer_cam", "install",
    
    # Specific clog types
    "clogged_kitchen_sink", "clogged_bathroom_sink", "clogged_shower_tub", "clogged_floor_drain",
    "clogged_toilet", "main_sewer_backup", "drain_snaking", "hydro_jetting",
    
    # Faucet services - now with location specificity
    "leaky_faucet", "faucet_replacement", "faucet_cartridge", "showerhead_replacement",
    "kitchen_faucet_replacement", "bathroom_faucet_replacement", "kitchen_faucet_repair", 
    "bathroom_faucet_repair", "kitchen_faucet_leak", "bathroom_faucet_leak",
    
    # Toilet services
    "toilet_leak", "toilet_replacement", "running_toilet", "toilet_flange", "toilet_seal",
    
    # Leak services
    "leak_detection", "slab_leak_repair", "burst_pipe", "pipe_thawing",
    
    # Re-piping services
    "re_piping", "whole_house_re_piping",
    
    # Water pressure services
    "water_pressure_adjustment", "pressure_reducing_valve", "pressure_relief_valve",
    
    # Water heater services
    "water_heater_repair", "water_heater_install", "tankless_water_heater", 
    "water_heater_expansion", "water_heater_flush",
    
    # Water treatment services
    "water_softener", "water_filtration", "backflow_prevention",
    
    # Pump services
    "sump_pump_install", "sump_pump_repair", "sewage_ejector", "well_pump", "well_pressure_tank",
    
    # Gas line services
    "gas_line_leak", "gas_line_install",
    
    # Appliance hookups
    "dishwasher_hookup", "washing_machine_hookup", "ice_maker_line", "garbage_disposal",
    
    # Outdoor and specialty services
    "hose_bib", "shower_valve", "mixing_valve", "bathtub_install", "faucet_aerator",
    "drain_tile", "trenchless_sewer", "camera_inspection", "grease_trap",
    "commercial_restroom", "commercial_backflow", "emergency_shutoff",
    "emergency_leak", "hydrostatic_test", "water_line"
]

# Keyword mapping for service recognition
SERVICE_KEYWORDS = {
    # Specific clog types - more specific to avoid faucet conflicts
    "clogged_kitchen_sink": ["kitchen sink clogged", "kitchen sink drain clogged", "kitchen sink backed up", "kitchen sink won't drain"],
    "clogged_bathroom_sink": ["bathroom sink clogged", "bathroom sink drain clogged", "bathroom sink backed up", "bathroom sink won't drain"],
    "clogged_shower_tub": ["shower drain", "tub drain", "bathtub drain"],
    "clogged_floor_drain": ["floor drain"],
    "clogged_toilet": ["toilet clog", "toilet backed up", "toilet is clogged", "toilet won't flush", "backed up completely"],
    "main_sewer_backup": ["main sewer", "sewer backup", "sewer line"],
    
    # Drain services
    "drain_snaking": ["snaking", "rooter", "drain snake"],
    "hydro_jetting": ["hydro jet", "hydrojet", "hydro-jet"],
    
    # Faucet services - comprehensive location-specific mappings
    "leaky_faucet": ["leaky faucet", "dripping faucet", "faucet dripping", "faucet is dripping"],
    "faucet_replacement": ["faucet replacement", "replace faucet", "new faucet", "need new faucet"],
    "faucet_cartridge": ["faucet cartridge", "cartridge replacement"],
    "showerhead_replacement": ["showerhead", "shower head"],
    
    # Location-specific faucet services - more specific to avoid sink conflicts
    "kitchen_faucet_replacement": ["kitchen faucet replacement", "replace kitchen faucet", "new kitchen faucet", 
                                  "kitchen faucet install", "replace faucet in kitchen", "kitchen faucet needs replacement",
                                  "replace the kitchen faucet"],
    "bathroom_faucet_replacement": ["bathroom faucet replacement", "replace bathroom faucet", "new bathroom faucet",
                                   "bathroom faucet install", "replace faucet in bathroom", "bathroom faucet needs replacement",
                                   "bathroom sink faucet replacement needed"],
    "kitchen_faucet_repair": ["kitchen faucet repair", "kitchen faucet broken", "kitchen faucet not working",
                              "kitchen faucet needs repair", "kitchen faucet is broken", "kitchen faucet repair needed",
                              "kitchen faucet is not working properly"],
    "bathroom_faucet_repair": ["bathroom faucet repair", "bathroom faucet broken", "bathroom faucet not working",
                               "bathroom faucet needs repair", "bathroom faucet is broken", "bathroom faucet repair needed"],
    "kitchen_faucet_leak": ["kitchen faucet leak", "kitchen faucet leaking", "kitchen faucet is leaking", 
                            "kitchen faucet dripping", "kitchen faucet is dripping", "kitchen sink faucet is leaking"],
    "bathroom_faucet_leak": ["bathroom faucet leak", "bathroom faucet leaking", "bathroom faucet is leaking", 
                             "bathroom faucet dripping", "bathroom faucet is dripping", "bathroom sink faucet is leaking"],
    
    # Toilet services
    "toilet_leak": ["toilet leak", "tank leak"],
    "toilet_replacement": ["toilet replacement", "replace toilet", "replace the entire toilet", "new toilet"],
    "running_toilet": ["running toilet", "toilet running", "toilet is running", "constantly running", "commode", "acting up"],
    "toilet_flange": ["toilet flange"],
    "toilet_seal": ["wax ring", "toilet seal"],
    
    # Leak services
    "leak_detection": ["leak detection", "find leak", "water coming from", "water from ceiling", "water is coming from", "leak somewhere", "can't find where"],
    "slab_leak_repair": ["slab leak", "foundation leak"],
    "burst_pipe": ["burst pipe", "broken pipe", "pipe burst", "pipe just burst", "burst and water"],
    "pipe_thawing": ["frozen pipe", "pipe thaw"],
    
    # Re-piping services
    "re_piping": ["re-piping", "repiping"],
    "whole_house_re_piping": ["whole house", "entire house"],
    
    # Water pressure services
    "water_pressure_adjustment": ["water pressure", "pressure adjustment", "pressure is too high", "pressure needs to be adjusted"],
    "pressure_reducing_valve": ["pressure reducing valve", "prv"],
    "pressure_relief_valve": ["pressure relief valve"],
    
    # Water heater services
    "water_heater_repair": ["water heater repair", "heater repair", "water heater burst", "heater burst", "water heater making noise", "water heater making strange noises"],
    "water_heater_install": ["water heater install", "heater install", "new water heater"],
    "tankless_water_heater": ["tankless", "tankless water heater"],
    "water_heater_expansion": ["expansion tank"],
    "water_heater_flush": ["water heater flush", "heater flush"],
    
    # Water treatment services
    "water_softener": ["water softener", "softener"],
    "water_filtration": ["water filtration", "filtration system"],
    "backflow_prevention": ["backflow", "backflow prevention", "backflow test"],
    
    # Pump services
    "sump_pump_install": ["sump pump install", "sump pump", "sump pump needs to be installed"],
    "sump_pump_repair": ["sump pump repair", "sump pump failed", "sump pump not working"],
    "sewage_ejector": ["sewage ejector", "ejector pump"],
    "well_pump": ["well pump"],
    "well_pressure_tank": ["well pressure tank"],
    
    # Gas line services
    "gas_line_leak": ["gas line leak", "gas leak"],
    "gas_line_install": ["gas line install", "gas installation"],
    
    # Appliance hookups
    "dishwasher_hookup": ["dishwasher hookup", "dishwasher install", "dishwasher won't drain"],
    "washing_machine_hookup": ["washing machine hookup", "washer hookup"],
    "ice_maker_line": ["ice maker", "ice maker line"],
    "garbage_disposal": ["garbage disposal", "disposal"],
    
    # Outdoor and specialty services
    "hose_bib": ["hose bib", "outdoor faucet", "spigot"],
    "shower_valve": ["shower valve", "shower mixing valve"],
    "mixing_valve": ["mixing valve", "anti-scald"],
    "bathtub_install": ["bathtub install", "tub install"],
    "faucet_aerator": ["faucet aerator", "aerator"],
    "drain_tile": ["drain tile", "foundation drain"],
    "trenchless_sewer": ["trenchless sewer", "trenchless"],
    "camera_inspection": ["camera inspection", "sewer camera"],
    "grease_trap": ["grease trap", "grease trap cleaning"],
    "commercial_restroom": ["commercial restroom", "commercial fixture", "restroom fixture"],
    "commercial_backflow": ["commercial backflow"],
    "emergency_shutoff": ["emergency shutoff", "shut-off valve"],
    "emergency_leak": ["emergency leak", "emergency response"],
    "hydrostatic_test": ["hydrostatic test", "hydrostatic pressure"],
    "water_line": ["water line", "main water line"],
    
    # Fallback general categories - made more specific
    "sewer_cam": ["sewer smell", "sewer odor", "sewer inspection"],
    "water_heater": ["hot water heater", "water heater"],
    "leak": ["leak", "drip", "dripping"],
    "clog": ["clog", "clogged", "backed up"],
    "gas_line": ["gas line", "gas inspection", "gas line inspection"],
    "install": ["install", "installation"]
}

# Add more specific keywords for better detection
SERVICE_KEYWORDS.update({
    "water_heater_repair": [
        "water heater repair", "water heater broken", "water heater not working",
        "water heater making noise", "water heater loud", "water heater banging",
        "water heater leaking", "water heater problem", "water heater issue",
        "water heater is leaking", "water heater needs repair"
    ],
    "water_heater_expansion": [
        "expansion tank", "water heater expansion", "expansion tank replacement",
        "expansion tank broken", "expansion tank needs replacement"
    ],
    "kitchen_faucet_leak": [
        "kitchen faucet leak", "kitchen faucet dripping", "kitchen sink faucet leak",
        "kitchen faucet leaking", "kitchen faucet is dripping"
    ],
    "bathroom_faucet_replacement": [
        "bathroom faucet replacement", "bathroom sink faucet replacement",
        "bathroom faucet needs replacement", "bathroom faucet replacement needed"
    ],
    "sump_pump_repair": [
        "sump pump repair", "sump pump broken", "sump pump not working",
        "sump pump failed", "sump pump failure", "sump pump problem"
    ],
    "tankless_water_heater": [
        "tankless water heater", "tankless water heater installation",
        "tankless water heater install", "tankless heater"
    ],
    "clogged_kitchen_sink": [
        "kitchen sink clogged", "kitchen sink is clogged", "kitchen sink blocked",
        "kitchen sink drain clogged", "kitchen sink won't drain"
    ],
    "toilet_leak": [
        "toilet leak", "toilet is leaking", "toilet tank leak", "toilet leaking",
        "toilet tank is leaking", "toilet base leak"
    ]
})

# Service categories for grouping
SERVICE_CATEGORIES = {
    "clogs": ["clogged_kitchen_sink", "clogged_bathroom_sink", "clogged_shower_tub", "clogged_floor_drain", "clogged_toilet", "main_sewer_backup", "drain_snaking", "hydro_jetting"],
    "leaks": ["leak_detection", "slab_leak_repair", "burst_pipe", "emergency_leak", "toilet_leak", "kitchen_faucet_leak", "bathroom_faucet_leak"],
    "faucets": ["leaky_faucet", "faucet_replacement", "faucet_cartridge", "kitchen_faucet_replacement", "bathroom_faucet_replacement", "kitchen_faucet_repair", "bathroom_faucet_repair", "faucet_aerator"],
    "water_heaters": ["water_heater_repair", "water_heater_install", "tankless_water_heater", "water_heater_expansion", "water_heater_flush"],
    "toilets": ["toilet_replacement", "running_toilet", "toilet_flange", "toilet_seal"],
    "pumps": ["sump_pump_install", "sump_pump_repair", "sewage_ejector", "well_pump", "well_pressure_tank"],
    "gas": ["gas_line_leak", "gas_line_install"],
    "appliances": ["dishwasher_hookup", "washing_machine_hookup", "ice_maker_line", "garbage_disposal"],
    "outdoor": ["hose_bib", "bathtub_install"],
    "valves": ["shower_valve", "mixing_valve", "pressure_reducing_valve", "pressure_relief_valve"],
    "piping": ["re_piping", "whole_house_re_piping", "water_line", "drain_tile"],
    "sewer": ["trenchless_sewer", "camera_inspection", "grease_trap"],
    "commercial": ["commercial_restroom", "commercial_backflow"],
    "emergency": ["emergency_shutoff", "emergency_leak", "hydrostatic_test"],
    "treatment": ["water_softener", "water_filtration", "backflow_prevention"],
    "maintenance": ["pipe_thawing", "showerhead_replacement", "water_pressure_adjustment"]
}

# Exclusion Rules - when specific service is detected, exclude these generic terms
EXCLUSION_RULES = {
    # Clog-related exclusions
    "clogged_kitchen_sink": ["clog", "sewer_cam"],
    "clogged_bathroom_sink": ["clog", "sewer_cam"],
    "clogged_shower_tub": ["clog", "sewer_cam"],
    "clogged_floor_drain": ["clog", "sewer_cam"],
    "clogged_toilet": ["clog", "sewer_cam"],
    "main_sewer_backup": ["clog", "sewer_cam"],
    "drain_snaking": ["clog", "sewer_cam"],
    "hydro_jetting": ["clog", "sewer_cam"],
    
    # Leak-related exclusions
    "leak_detection": ["leak"],
    "slab_leak_repair": ["leak"],
    "burst_pipe": ["leak"],
    "emergency_leak": ["leak"],
    
    # Faucet-related exclusions
    "kitchen_faucet_replacement": ["faucet_replacement", "install", "leaky_faucet"],
    "bathroom_faucet_replacement": ["faucet_replacement", "install", "leaky_faucet"],
    "kitchen_faucet_repair": ["leaky_faucet", "leak", "faucet_replacement"],
    "bathroom_faucet_repair": ["leaky_faucet", "leak", "faucet_replacement"],
    "kitchen_faucet_leak": ["leaky_faucet", "leak"],
    "bathroom_faucet_leak": ["leaky_faucet", "leak"],
    "faucet_replacement": ["install"],
    "leaky_faucet": ["leak"],
    
    # Water heater exclusions
    "water_heater_repair": ["water_heater"],
    "water_heater_install": ["water_heater", "install"],
    "tankless_water_heater": ["water_heater", "install"],
    "water_heater_expansion": ["water_heater", "install"],
    "water_heater_flush": ["water_heater"],
    
    # Toilet exclusions
    "toilet_replacement": ["install"],
    "toilet_leak": ["leak"],
    
    # Gas line exclusions
    "gas_line_leak": ["gas_line", "leak"],
    "gas_line_install": ["gas_line", "install"],
    
    # Pump exclusions
    "sump_pump_install": ["install"],
    "sump_pump_repair": [],
    
    # Appliance exclusions
    "dishwasher_hookup": ["install"],
    "washing_machine_hookup": ["install"],
    
    # Piping exclusions
    "re_piping": ["install"],
    "whole_house_re_piping": ["install"],
    
    # Outdoor exclusions
    "bathtub_install": ["install"],
    
    # Commercial exclusions
    "commercial_backflow": ["backflow_prevention"],
    
    # Installation-related exclusions
    "camera_inspection": ["sewer_cam"],
    "trenchless_sewer": ["sewer_cam"],
}

def get_service_keywords(service_type: str) -> list:
    """Get keywords for a specific service type."""
    return SERVICE_KEYWORDS.get(service_type, [])

def get_all_keywords() -> dict:
    """Get all service keywords."""
    return SERVICE_KEYWORDS

def get_service_categories() -> dict:
    """Get service categories."""
    return SERVICE_CATEGORIES

def calculate_bert_similarity(text: str, keywords: List[str], threshold: float = 0.3) -> Tuple[float, str]:
    """
    Calculate semantic similarity between text and keywords using BERT.
    
    Args:
        text: Input text to analyze
        keywords: List of keywords to compare against
        threshold: Minimum similarity threshold
    
    Returns:
        Tuple of (max_similarity_score, best_matching_keyword)
    """
    if not BERT_AVAILABLE or not BERT_MODEL or not NUMPY_AVAILABLE:
        return 0.0, ""
    
    try:
        # Encode the input text
        text_embedding = BERT_MODEL.encode([text])
        
        # Encode all keywords
        keyword_embeddings = BERT_MODEL.encode(keywords)
        
        # Calculate cosine similarity
        similarities = cosine_similarity(text_embedding, keyword_embeddings)[0]
        
        # Find the best match
        max_similarity = np.max(similarities)
        best_keyword_idx = np.argmax(similarities)
        best_keyword = keywords[best_keyword_idx]
        
        return max_similarity, best_keyword if max_similarity >= threshold else ""
        
    except Exception as e:
        print(f"BERT similarity calculation error: {e}")
        return 0.0, ""

def get_semantic_service_matches(text: str, service_keywords: Dict[str, List[str]], 
                                semantic_threshold: float = 0.4) -> List[Tuple[str, float, str]]:
    """
    Get semantic matches for services using BERT.
    
    Args:
        text: Input text to analyze
        service_keywords: Dictionary of service types to keywords
        semantic_threshold: Minimum semantic similarity threshold
    
    Returns:
        List of tuples (service_type, similarity_score, matched_keyword)
    """
    if not BERT_AVAILABLE:
        return []
    
    semantic_matches = []
    
    for service_type, keywords in service_keywords.items():
        similarity, matched_keyword = calculate_bert_similarity(text, keywords, semantic_threshold)
        if similarity > 0:
            semantic_matches.append((service_type, similarity, matched_keyword))
    
    # Sort by similarity score (highest first)
    semantic_matches.sort(key=lambda x: x[1], reverse=True)
    return semantic_matches

def infer_job_type_from_text(text: str) -> str:
    """Infer job type from text using keyword matching with first-mentioned priority."""
    # Normalize text - handle tabs, newlines, and extra whitespace
    text_lower = text.lower().replace('\t', ' ').replace('\n', ' ')
    text_lower = ' '.join(text_lower.split())  # Normalize whitespace
    
    # Track all matches with their positions
    matches = []
    
    # Check all services and record match positions
    for service_type, keywords in SERVICE_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text_lower:
                # Find the position of the first occurrence
                position = text_lower.find(keyword)
                matches.append((position, service_type, keyword))
                break  # Only record first match per service type
    
    if not matches:
        return None
    
    # Sort by position (first mentioned first) and then by specificity
    matches.sort(key=lambda x: x[0])
    
    # Get the first mentioned service
    first_position, first_service, first_keyword = matches[0]
    
    # Additional logic: if the first match is a general category, 
    # check if there's a more specific match that comes soon after
    general_categories = {"sewer_cam", "water_heater", "leak", "clog", "gas_line", "install"}
    
    if first_service in general_categories:
        # Look for more specific matches within the first 50 characters
        for position, service, keyword in matches[1:]:
            if position - first_position <= 50 and service not in general_categories:
                return service
    
    # Special handling for "sink" - if it's just "sink" without context, prefer kitchen sink
    if first_service == "clogged_kitchen_sink" and first_keyword == "sink":
        # Check if there are other sink-related matches that might be more specific
        for position, service, keyword in matches[1:]:
            if service in ["clogged_bathroom_sink", "clogged_shower_tub"] and position - first_position <= 30:
                return service
    
    return first_service

def infer_multiple_job_types_from_text(text: str) -> dict:
    """
    Infer multiple job types from text with balanced accuracy improvements.
    
    Features:
    - Service Priority Hierarchy: Specific services suppress generic ones
    - Max 1 Secondary Intent: Reduces over-detection 
    - Improved NLP: Better sentence boundary detection
    - Conservative BERT Semantic Analysis: Only supplements keyword matching with high confidence
    - Simple but effective scoring system
    
    Returns:
        dict: {
            'primary': str,  # Primary job type (most specific and relevant)
            'secondary': list,  # List of secondary job types (max 1)
            'description_suffix': str  # Formatted description of secondary intents
        }
    """
    # Normalize text
    text_lower = text.lower().replace('\t', ' ').replace('\n', ' ')
    text_lower = ' '.join(text_lower.split())
    
    # Define service hierarchy (higher = more specific, will suppress lower levels)
    service_hierarchy = {
        # Level 5: Most specific services - these suppress all lower levels
        "clogged_kitchen_sink": 5, "clogged_bathroom_sink": 5, "clogged_shower_tub": 5,
        "clogged_floor_drain": 5, "clogged_toilet": 5, "main_sewer_backup": 5,
        "leaky_faucet": 5, "faucet_replacement": 5, "faucet_cartridge": 5,
        "kitchen_faucet_replacement": 5, "bathroom_faucet_replacement": 5, "kitchen_faucet_repair": 5,
        "bathroom_faucet_repair": 5, "kitchen_faucet_leak": 5, "bathroom_faucet_leak": 5,
        "toilet_leak": 5, "toilet_replacement": 5, "running_toilet": 5,
        "leak_detection": 5, "slab_leak_repair": 5, "burst_pipe": 5,
        "water_heater_repair": 5, "water_heater_install": 5, "tankless_water_heater": 5,
        "sump_pump_install": 5, "sump_pump_repair": 5, "gas_line_leak": 5,
        "gas_line_install": 5, "dishwasher_hookup": 5, "washing_machine_hookup": 5,
        "hose_bib": 5, "shower_valve": 5, "mixing_valve": 5, "bathtub_install": 5,
        "faucet_aerator": 5, "drain_tile": 5, "trenchless_sewer": 5, "camera_inspection": 5,
        "grease_trap": 5, "commercial_restroom": 5, "commercial_backflow": 5,
        "emergency_shutoff": 5, "emergency_leak": 5, "hydrostatic_test": 5,
        "water_line": 5, "drain_snaking": 5, "hydro_jetting": 5, "showerhead_replacement": 5,
        "toilet_flange": 5, "toilet_seal": 5, "pipe_thawing": 5, "re_piping": 5,
        "whole_house_re_piping": 5, "water_pressure_adjustment": 5, "pressure_reducing_valve": 5,
        "pressure_relief_valve": 5, "water_heater_expansion": 5, "water_heater_flush": 5,
        "water_softener": 5, "water_filtration": 5, "backflow_prevention": 5,
        "sewage_ejector": 5, "well_pump": 5, "well_pressure_tank": 5, "ice_maker_line": 5,
        "garbage_disposal": 5,
        
        # Level 3: Medium specific services
        "water_heater": 3, "sewer_cam": 3,
        
        # Level 2: General categories (suppressed by specific services)
        "leak": 2, "clog": 2, "gas_line": 2,
        
        # Level 1: Most general (heavily suppressed)
        "install": 1
    }
    
    # Use improved sentence boundary detection
    sentences = detect_sentence_boundaries(text_lower)
    
    # Find all matches with position, sentence context, and hierarchy level
    all_matches = []
    
    # First, do keyword-based matching (primary method)
    for sentence_idx, sentence in enumerate(sentences):
        for service_type, keywords in SERVICE_KEYWORDS.items():
            for keyword in keywords:
                if keyword in sentence:
                    position = text_lower.find(keyword)
                    hierarchy_level = service_hierarchy.get(service_type, 2)
                    
                    # Calculate proximity score (keywords closer together = higher relevance)
                    proximity_score = len(sentence) - len(keyword)  # Shorter sentence = higher relevance
                    
                    match_data = {
                        'position': position,
                        'service': service_type,
                        'keyword': keyword,
                        'hierarchy': hierarchy_level,
                        'sentence_idx': sentence_idx,
                        'sentence': sentence,
                        'proximity_score': proximity_score,
                        'match_type': 'keyword',
                        'confidence': 1.0  # High confidence for keyword matches
                    }
                    
                    all_matches.append(match_data)
                    break  # Only record first match per service type
    
    # Only add BERT semantic matches if no keyword matches found (conservative approach)
    if BERT_AVAILABLE and len(all_matches) == 0:
        semantic_matches = get_semantic_service_matches(text_lower, SERVICE_KEYWORDS, semantic_threshold=0.6)  # Higher threshold
        
        for service_type, similarity_score, matched_keyword in semantic_matches:
            # Only add if similarity is very high (conservative)
            if similarity_score >= 0.6:
                match_data = {
                    'position': 0,  # Default position for semantic matches
                    'service': service_type,
                    'keyword': matched_keyword,
                    'hierarchy': service_hierarchy.get(service_type, 2),
                    'sentence_idx': 0,
                    'sentence': text_lower,
                    'proximity_score': similarity_score * 50,  # Scale similarity to proximity score
                    'match_type': 'semantic',
                    'semantic_score': similarity_score,
                    'confidence': similarity_score
                }
                
                all_matches.append(match_data)
    
    if not all_matches:
        return {
            'primary': None,
            'secondary': [],
            'description_suffix': ''
        }
    
    # Apply Service Priority Hierarchy - specific services suppress generic ones
    filtered_matches = []
    services_by_hierarchy = {}
    
    # Group by hierarchy level
    for match in all_matches:
        level = match['hierarchy']
        if level not in services_by_hierarchy:
            services_by_hierarchy[level] = []
        services_by_hierarchy[level].append(match)
    
    # Start with highest hierarchy level and work down
    for level in sorted(services_by_hierarchy.keys(), reverse=True):
        level_matches = services_by_hierarchy[level]
        
        # If we have high-level matches, suppress lower levels in same categories
        if level >= 4:  # Specific services
            for match in level_matches:
                # Check if this specific service should suppress generic ones
                should_add = True
                service_category = None
                
                # Find which category this service belongs to
                for cat_name, cat_services in SERVICE_CATEGORIES.items():
                    if match['service'] in cat_services:
                        service_category = cat_name
                        break
                
                # Remove any lower-level services in the same category
                if service_category:
                    filtered_matches = [m for m in filtered_matches 
                                      if not (m['hierarchy'] < level and 
                                            any(m['service'] in cat_services for cat_services in SERVICE_CATEGORIES.values() 
                                               if match['service'] in cat_services))]
                
                if should_add:
                    filtered_matches.append(match)
        else:
            # For lower-level services, only add if no higher-level service exists
            for match in level_matches:
                conflicts_with_higher = False
                service_category = None
                
                # Find category
                for cat_name, cat_services in SERVICE_CATEGORIES.items():
                    if match['service'] in cat_services:
                        service_category = cat_name
                        break
                
                # Check if higher-level service exists in same category
                if service_category:
                    for existing_match in filtered_matches:
                        if existing_match['hierarchy'] > level:
                            for cat_services in SERVICE_CATEGORIES.values():
                                if (match['service'] in cat_services and 
                                    existing_match['service'] in cat_services):
                                    conflicts_with_higher = True
                                    break
                            if conflicts_with_higher:
                                break
                
                if not conflicts_with_higher:
                    filtered_matches.append(match)
    
    # Apply Exclusion Rules - remove generic services when specific ones are detected
    specific_services_detected = [m['service'] for m in filtered_matches if m['hierarchy'] >= 4]
    
    if specific_services_detected:
        # Build list of services to exclude
        services_to_exclude = set()
        for specific_service in specific_services_detected:
            if specific_service in EXCLUSION_RULES:
                for excluded_service in EXCLUSION_RULES[specific_service]:
                    services_to_exclude.add(excluded_service)
        
        # Filter out excluded services
        filtered_matches = [m for m in filtered_matches if m['service'] not in services_to_exclude]
    
    # Remove duplicates by service name
    unique_matches = {}
    for match in filtered_matches:
        service = match['service']
        if service not in unique_matches:
            unique_matches[service] = match
        else:
            # Keep the one with better position/proximity/semantic score
            existing = unique_matches[service]
            existing_score = existing.get('semantic_score', 0)
            match_score = match.get('semantic_score', 0)
            
            # Prioritize keyword matches over semantic matches
            if (match['match_type'] == 'keyword' and existing['match_type'] == 'semantic'):
                unique_matches[service] = match
            elif (match['match_type'] == 'semantic' and existing['match_type'] == 'keyword'):
                pass  # Keep existing keyword match
            elif (match['hierarchy'] > existing['hierarchy'] or 
                (match['hierarchy'] == existing['hierarchy'] and match_score > existing_score) or
                (match['hierarchy'] == existing['hierarchy'] and match_score == existing_score and match['position'] < existing['position'])):
                unique_matches[service] = match
    
    final_matches = list(unique_matches.values())
    
    # Sort by position and hierarchy for primary selection
    # Prioritize keyword matches over semantic matches
    final_matches.sort(key=lambda x: (x['match_type'] != 'keyword', x['position'], -x['hierarchy'], -x.get('semantic_score', 0)))
    
    # Additional check: if the first match is generic and there's a specific service very close by, prefer the specific one
    if len(final_matches) > 1:
        first_match = final_matches[0]
        if first_match['hierarchy'] <= 2:  # If first is generic
            # Look for more specific matches within 20 characters
            for match in final_matches[1:]:
                if (match['hierarchy'] >= 4 and  # Is specific
                    abs(match['position'] - first_match['position']) <= 20):  # Is close
                    # Swap to prefer specific service
                    final_matches[0], final_matches[final_matches.index(match)] = match, first_match
                    break
    
    if len(final_matches) == 0:
        return {
            'primary': None,
            'secondary': [],
            'description_suffix': ''
        }
    
    # Select primary (first mentioned with highest hierarchy)
    primary_service = final_matches[0]['service']
    
    # Select secondary services (max 1 to reduce over-detection)
    secondary_matches = final_matches[1:]
    
    # Advanced filtering for secondary services using NLP proximity
    filtered_secondary = []
    
    for match in secondary_matches:
        if len(filtered_secondary) >= 1:  # Max 1 secondary intent
            break
            
        # Check if this secondary service is truly distinct from primary
        is_distinct = True
        
        # Check sentence proximity - if in same sentence as primary, might be description of same issue
        primary_sentence = final_matches[0]['sentence_idx']
        if match['sentence_idx'] == primary_sentence and match['hierarchy'] <= 2:
            # If in same sentence and low hierarchy, might be describing same issue
            is_distinct = False
        
        # Check category overlap - don't add if same category as primary unless both high hierarchy
        primary_category = None
        match_category = None
        
        for cat_name, cat_services in SERVICE_CATEGORIES.items():
            if primary_service in cat_services:
                primary_category = cat_name
            if match['service'] in cat_services:
                match_category = cat_name
        
        if (primary_category == match_category and 
            match_category is not None and 
            match['hierarchy'] <= 3):
            is_distinct = False
        
        # Additional exclusion check - don't add if excluded by primary service
        if (primary_service in EXCLUSION_RULES and 
            match['service'] in EXCLUSION_RULES[primary_service]):
            is_distinct = False
        
        # Additional check: if primary and secondary are very similar, don't add secondary
        if (primary_service in ['kitchen_faucet_leak', 'bathroom_faucet_leak'] and 
            match['service'] in ['kitchen_faucet_leak', 'bathroom_faucet_leak']):
            is_distinct = False
        
        if (primary_service in ['kitchen_faucet_repair', 'bathroom_faucet_repair'] and 
            match['service'] in ['kitchen_faucet_repair', 'bathroom_faucet_repair']):
            is_distinct = False
        
        if (primary_service in ['kitchen_faucet_replacement', 'bathroom_faucet_replacement'] and 
            match['service'] in ['kitchen_faucet_replacement', 'bathroom_faucet_replacement']):
            is_distinct = False
        
        # Additional strict filtering for similar services
        if (primary_service in ['water_heater_repair', 'water_heater_expansion'] and 
            match['service'] in ['water_heater_repair', 'water_heater_expansion']):
            is_distinct = False
        
        if (primary_service in ['sump_pump_repair', 'sump_pump_install'] and 
            match['service'] in ['sump_pump_repair', 'sump_pump_install']):
            is_distinct = False
        
        if (primary_service in ['shower_valve', 'mixing_valve'] and 
            match['service'] in ['shower_valve', 'mixing_valve']):
            is_distinct = False
        
        if (primary_service in ['pressure_reducing_valve', 'pressure_relief_valve'] and 
            match['service'] in ['pressure_reducing_valve', 'pressure_relief_valve']):
            is_distinct = False
        
        # Check if the secondary service is too generic compared to primary
        if (match['hierarchy'] <= 2 and primary_service in ['water_heater_repair', 'water_heater_expansion', 
                                                           'kitchen_faucet_leak', 'bathroom_faucet_replacement',
                                                           'sump_pump_repair', 'tankless_water_heater']):
            is_distinct = False
        
        if is_distinct:
            filtered_secondary.append(match['service'])
    
    # Format description suffix
    if len(filtered_secondary) == 0:
        description_suffix = ''
    else:
        description_suffix = f"Also detected: {filtered_secondary[0]}"
    
    return {
        'primary': primary_service,
        'secondary': filtered_secondary,
        'description_suffix': description_suffix
    }

def get_function_definition():
    """Get the function definition for OpenAI function calling."""
    return {
        "type": "function",
        "function": {
            "name": "book_job",
            "description": "Extract plumbing job booking information from customer request",
            "parameters": {
                "type": "object",
                "properties": {
                    "intent": {
                        "type": "string",
                        "enum": ["BOOK_JOB"]
                    },
                    "customer": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "phone": {"type": "string"},
                            "email": {"type": "string"}
                        },
                        "required": ["name", "phone"]
                    },
                    "job": {
                        "type": "object",
                        "properties": {
                            "type": {
                                "type": "string",
                                "enum": PLUMBING_SERVICES
                            },
                            "urgency": {
                                "type": "string",
                                "enum": ["emergency", "same_day", "flex"]
                            },
                            "description": {"type": "string"}
                        },
                        "required": ["type", "urgency"]
                    },
                    "location": {
                        "type": "object",
                        "properties": {
                            "raw_address": {"type": "string"},
                            "validated": {"type": "boolean"},
                            "address_id": {"type": "string"},
                            "lat": {"type": "number"},
                            "lng": {"type": "number"}
                        },
                        "required": ["raw_address"]
                    },
                    "constraints": {
                        "type": "object",
                        "properties": {
                            "window_start": {"type": "string", "format": "date-time"},
                            "window_end": {"type": "string", "format": "date-time"},
                            "preferred_tech": {"type": ["string", "null"]}
                        }
                    },
                    "proposed_slot": {
                        "type": "object",
                        "properties": {
                            "start": {"type": "string", "format": "date-time"},
                            "end": {"type": "string", "format": "date-time"},
                            "eta_minutes": {"type": "integer"}
                        }
                    },
                    "fsm_backend": {
                        "type": "string",
                        "enum": ["servicetitan", "jobber", "housecallpro"]
                    },
                    "confidence": {
                        "type": "object",
                        "properties": {
                            "overall": {"type": "number"},
                            "fields": {
                                "type": "object",
                                "properties": {
                                    "address": {"type": "number"},
                                    "type": {"type": "number"},
                                    "urgency": {"type": "number"}
                                }
                            }
                        }
                    },
                    "handoff_needed": {"type": "boolean"}
                },
                "required": ["intent", "customer", "job", "location", "fsm_backend", "confidence", "handoff_needed"]
            }
        }
    } 

def calculate_context_score(text: str, keyword: str, position: int, window_size: int = 50) -> float:
    """
    Calculate context relevance score based on surrounding text.
    
    Args:
        text: Full input text
        keyword: Matched keyword
        position: Position of keyword in text
        window_size: Size of context window around keyword
    
    Returns:
        Context relevance score (0.0 to 1.0)
    """
    start = max(0, position - window_size)
    end = min(len(text), position + len(keyword) + window_size)
    context = text[start:end].lower()
    
    # Boost score for context words that indicate urgency or specificity
    urgency_words = ['emergency', 'urgent', 'immediately', 'broken', 'leaking', 'flooding', 'burst']
    specificity_words = ['kitchen', 'bathroom', 'basement', 'outdoor', 'commercial', 'residential']
    action_words = ['replace', 'repair', 'install', 'fix', 'clean', 'unclog']
    
    context_score = 0.0
    for word in urgency_words + specificity_words + action_words:
        if word in context:
            context_score += 0.1
    
    return min(1.0, context_score)

def detect_sentence_boundaries(text: str) -> List[str]:
    """
    Improved sentence boundary detection with better handling of plumbing terminology.
    
    Args:
        text: Input text to split into sentences
    
    Returns:
        List of sentences
    """
    # Replace common plumbing separators with sentence boundaries
    text = text.replace(' and ', ' | ')
    text = text.replace(' plus ', ' | ')
    text = text.replace(' also ', ' | ')
    text = text.replace(' as well as ', ' | ')
    text = text.replace(' along with ', ' | ')
    text = text.replace(' in addition to ', ' | ')
    
    # Handle common plumbing conjunctions
    text = text.replace(' but ', ' | ')
    text = text.replace(' however ', ' | ')
    text = text.replace(' while ', ' | ')
    
    # Split by multiple delimiters
    sentences = []
    for part in text.split('|'):
        # Further split by punctuation
        for sentence in part.replace('.', ' | ').replace(',', ' | ').replace(';', ' | ').split('|'):
            sentence = sentence.strip()
            if sentence and len(sentence) > 3:  # Filter out very short fragments
                # Clean up the sentence
                sentence = ' '.join(sentence.split())  # Remove extra whitespace
                sentences.append(sentence)
    
    # If no sentences found, return the original text as one sentence
    if not sentences:
        sentences = [text]
    
    return sentences 