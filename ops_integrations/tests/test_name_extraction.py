#!/usr/bin/env python3
"""
Test name extraction functionality to ensure it doesn't incorrectly extract
common phrases like "thank you" or numbers like "ten" as names.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Add the project root to the path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from ops_integrations.adapters.phone import extract_name_from_text

def test_name_extraction():
    """Test various inputs to ensure proper name extraction"""
    
    # Test cases that should NOT be extracted as names
    non_name_cases = [
        "thank you",
        "thanks",
        "thankyou", 
        "ten",
        "one",
        "two",
        "three",
        "yes",
        "no",
        "okay",
        "ok",
        "sure",
        "hello",
        "hi",
        "hey",
        "good morning",
        "good afternoon",
        "good evening",
        "fine",
        "good",
        "bad",
        "alright",
        "all right",
        "yeah",
        "yep",
        "nope",
        "uh huh",
        "uh-huh",
        "hmm",
        "um",
        "uh",
        "well",
        "so",
        "like",
        "just",
        "very",
        "really",
        "quite",
        "too",
        "also",
        "only",
        "even",
        "still",
        "again",
        "back",
        "up",
        "down",
        "out",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "by",
        "from",
        "into",
        "through",
        "during",
        "before",
        "after",
        "above",
        "below",
        "between",
        "among",
        "within",
        "without",
        "against",
        "toward",
        "towards",
        "upon",
        "across",
        "behind",
        "beneath",
        "beside",
        "beyond",
        "inside",
        "outside",
        "under",
        "over",
        "around",
        "throughout",
        "first",
        "second",
        "third",
        "fourth",
        "fifth",
        "sixth",
        "seventh",
        "eighth",
        "ninth",
        "tenth",
        "eleventh",
        "twelfth",
        "thirteenth",
        "fourteenth",
        "fifteenth",
        "sixteenth",
        "seventeenth",
        "eighteenth",
        "nineteenth",
        "twentieth"
    ]
    
    # Test cases that SHOULD be extracted as names
    name_cases = [
        ("my name is john", "John"),
        ("i'm sarah", "Sarah"),
        ("i am michael", "Michael"),
        ("this is emily", "Emily"),
        ("it's david", "David"),
        ("it is jennifer", "Jennifer"),
        ("call me alex", "Alex"),
        ("john here", "John"),
        ("sarah", "Sarah"),
        ("michael smith", "Michael Smith"),
        ("emily jones", "Emily Jones"),
        ("david wilson", "David Wilson"),
        ("jennifer brown", "Jennifer Brown"),
        ("alexander", "Alexander"),
        ("christopher", "Christopher"),
        ("elizabeth", "Elizabeth"),
        ("katherine", "Katherine"),
        ("nicholas", "Nicholas"),
        ("stephanie", "Stephanie"),
        ("daniel", "Daniel"),
        ("rebecca", "Rebecca"),
        ("matthew", "Matthew"),
        ("amanda", "Amanda"),
        ("joshua", "Joshua"),
        ("melissa", "Melissa"),
        ("andrew", "Andrew"),
        ("nicole", "Nicole"),
        ("kevin", "Kevin"),
        ("ashley", "Ashley"),
        ("brian", "Brian"),
        ("samantha", "Samantha"),
        ("jason", "Jason"),
        ("stephanie", "Stephanie"),
        ("justin", "Justin"),
        ("laura", "Laura"),
        ("ryan", "Ryan"),
        ("heather", "Heather"),
        ("eric", "Eric"),
        ("michelle", "Michelle"),
        ("stephen", "Stephen"),
        ("emily", "Emily"),
        ("jacob", "Jacob"),
        ("kimberly", "Kimberly"),
        ("gary", "Gary"),
        ("lisa", "Lisa"),
        ("nicholas", "Nicholas"),
        ("nancy", "Nancy"),
        ("tyler", "Tyler"),
        ("karen", "Karen"),
        ("adam", "Adam"),
        ("betty", "Betty"),
        ("timothy", "Timothy"),
        ("helen", "Helen"),
        ("ronald", "Ronald"),
        ("sandra", "Sandra"),
        ("keith", "Keith"),
        ("donna", "Donna"),
        ("jeremy", "Jeremy"),
        ("carol", "Carol"),
        ("harold", "Harold"),
        ("ruth", "Ruth"),
        ("douglas", "Douglas"),
        ("sharon", "Sharon"),
        ("henry", "Henry"),
        ("cynthia", "Cynthia"),
        ("arthur", "Arthur"),
        ("amy", "Amy"),
        ("ryan", "Ryan"),
        ("angela", "Angela"),
        ("joe", "Joe"),
        ("anna", "Anna"),
        ("jim", "Jim"),
        ("brenda", "Brenda"),
        ("billy", "Billy"),
        ("pamela", "Pamela"),
        ("bruce", "Bruce"),
        ("emma", "Emma"),
        ("willie", "Willie"),
        ("nicole", "Nicole"),
        ("jesse", "Jesse"),
        ("virginia", "Virginia"),
        ("jordan", "Jordan"),
        ("debra", "Debra"),
        ("bryan", "Bryan"),
        ("janet", "Janet"),
        ("billy", "Billy"),
        ("catherine", "Catherine"),
        ("joe", "Joe"),
        ("maria", "Maria"),
        ("jimmy", "Jimmy"),
        ("heather", "Heather"),
        ("antonio", "Antonio"),
        ("diane", "Diane"),
        ("danny", "Danny"),
        ("julie", "Julie"),
        ("eddie", "Eddie"),
        ("joyce", "Joyce"),
        ("johnny", "Johnny"),
        ("victoria", "Victoria"),
        ("roy", "Roy"),
        ("kelly", "Kelly"),
        ("eugene", "Eugene"),
        ("christina", "Christina"),
        ("tony", "Tony"),
        ("joan", "Joan"),
        ("aaron", "Aaron"),
        ("evelyn", "Evelyn"),
        ("jose", "Jose"),
        ("lauren", "Lauren"),
        ("jimmy", "Jimmy"),
        ("judith", "Judith"),
        ("mario", "Mario"),
        ("megan", "Megan"),
        ("julian", "Julian"),
        ("cheryl", "Cheryl"),
        ("devon", "Devon"),
        ("andrea", "Andrea"),
        ("fernando", "Fernando"),
        ("hannah", "Hannah"),
        ("carl", "Carl"),
        ("jacqueline", "Jacqueline"),
        ("duke", "Duke"),
        ("martha", "Martha"),
        ("king", "King"),
        ("gloria", "Gloria"),
        ("ivan", "Ivan"),
        ("teresa", "Teresa"),
        ("damian", "Damian"),
        ("ann", "Ann"),
        ("ricky", "Ricky"),
        ("sara", "Sara"),
        ("lewis", "Lewis"),
        ("madison", "Madison"),
        ("zachary", "Zachary"),
        ("frances", "Frances"),
        ("corey", "Corey"),
        ("alexandra", "Alexandra"),
        ("herman", "Herman"),
        ("chloe", "Chloe"),
        ("maurice", "Maurice"),
        ("sophia", "Sophia"),
        ("vernon", "Vernon"),
        ("aubrey", "Aubrey"),
        ("roberto", "Roberto"),
        ("isabella", "Isabella"),
        ("clyde", "Clyde"),
        ("natalie", "Natalie"),
        ("glen", "Glen"),
        ("lily", "Lily"),
        ("hector", "Hector"),
        ("grace", "Grace"),
        ("shane", "Shane"),
        ("chloe", "Chloe"),
        ("ricardo", "Ricardo"),
        ("penelope", "Penelope"),
        ("sam", "Sam"),
        ("layla", "Layla"),
        ("rick", "Rick"),
        ("riley", "Riley"),
        ("lester", "Lester"),
        ("zoey", "Zoey"),
        ("brent", "Brent"),
        ("nora", "Nora"),
        ("ramon", "Ramon"),
        ("lillian", "Lillian"),
        ("charlie", "Charlie"),
        ("addison", "Addison"),
        ("tyler", "Tyler"),
        ("eleanor", "Eleanor"),
        ("gilbert", "Gilbert"),
        ("luna", "Luna"),
        ("gene", "Gene"),
        ("savannah", "Savannah"),
        ("marc", "Marc"),
        ("brooklyn", "Brooklyn"),
        ("reginald", "Reginald"),
        ("leah", "Leah"),
        ("ruben", "Ruben"),
        ("zoe", "Zoe"),
        ("brett", "Brett"),
        ("hannah", "Hannah"),
        ("angel", "Angel"),
        ("lucy", "Lucy"),
        ("nathaniel", "Nathaniel"),
        ("eliana", "Eliana"),
        ("rafael", "Rafael"),
        ("ivy", "Ivy"),
        ("leslie", "Leslie"),
        ("trinity", "Trinity"),
        ("edgar", "Edgar"),
        ("sadie", "Sadie"),
        ("milton", "Milton"),
        ("piper", "Piper"),
        ("raul", "Raul"),
        ("lydia", "Lydia"),
        ("ben", "Ben"),
        ("alexa", "Alexa"),
        ("chester", "Chester"),
        ("nora", "Nora"),
        ("cecil", "Cecil"),
        ("claire", "Claire"),
        ("duane", "Duane"),
        ("violet", "Violet"),
        ("franklin", "Franklin"),
        ("skylar", "Skylar"),
        ("andre", "Andre"),
        ("sadie", "Sadie"),
        ("elmer", "Elmer"),
        ("clara", "Clara"),
        ("brad", "Brad"),
        ("aurora", "Aurora"),
    ]
    
    print("Testing name extraction...")
    print("=" * 50)
    
    # Test non-name cases (should return None)
    print("Testing cases that should NOT be extracted as names:")
    failed_non_names = []
    for case in non_name_cases:
        result = extract_name_from_text(case)
        if result is not None:
            failed_non_names.append((case, result))
            print(f"❌ FAILED: '{case}' -> '{result}' (should be None)")
        else:
            print(f"✅ PASSED: '{case}' -> None")
    
    print(f"\nNon-name test results: {len(failed_non_names)} failures out of {len(non_name_cases)} tests")
    
    # Test name cases (should return the expected name)
    print(f"\nTesting cases that SHOULD be extracted as names:")
    failed_names = []
    for input_text, expected_name in name_cases:
        result = extract_name_from_text(input_text)
        if result != expected_name:
            failed_names.append((input_text, expected_name, result))
            print(f"❌ FAILED: '{input_text}' -> '{result}' (expected '{expected_name}')")
        else:
            print(f"✅ PASSED: '{input_text}' -> '{result}'")
    
    print(f"\nName test results: {len(failed_names)} failures out of {len(name_cases)} tests")
    
    # Summary
    total_tests = len(non_name_cases) + len(name_cases)
    total_failures = len(failed_non_names) + len(failed_names)
    
    print(f"\n{'='*50}")
    print(f"SUMMARY:")
    print(f"Total tests: {total_tests}")
    print(f"Total failures: {total_failures}")
    print(f"Success rate: {((total_tests - total_failures) / total_tests * 100):.1f}%")
    
    if failed_non_names:
        print(f"\nFailed non-name cases:")
        for case, result in failed_non_names:
            print(f"  '{case}' -> '{result}'")
    
    if failed_names:
        print(f"\nFailed name cases:")
        for input_text, expected, result in failed_names:
            print(f"  '{input_text}' -> '{result}' (expected '{expected}')")
    
    return total_failures == 0

if __name__ == "__main__":
    success = test_name_extraction()
    sys.exit(0 if success else 1) 