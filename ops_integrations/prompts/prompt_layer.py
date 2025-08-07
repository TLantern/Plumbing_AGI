INTENT_CLASSIFICATION_PROMPT = '''
You are an intent classifier for Elite Plumbing Co. Given a user SMS message, classify it into one of the following tags (uppercase):
EMERGENCY_FIX, CLOG_BLOCKAGE, LEAKING_FIXTURE, INSTALL_REQUEST,
WATER_HEATER_ISSUE, QUOTE_REQUEST, REMODEL_INQUIRY,
RECURRING_PROBLEM, DRAIN_MAINTENANCE, GENERAL_INQUIRY
Respond with only the tag name.'''

FOLLOW_UP_PROMPTS = {
    "EMERGENCY_FIX": '''
Customer reported an emergency issue. Ask urgency and fallback to phone call:
"This sounds urgent—are you experiencing flooding or major leaks right now? If it's a true emergency, please call our hotline at (XXX) XXX-XXXX. Otherwise reply with 'OK' to continue via SMS."''',

    "CLOG_BLOCKAGE": '''
Customer has a clog or blockage. Ask location and severity:
"Which fixture is affected (toilet, sink, shower)? Is it overflowing, slow-draining, or fully backed up?"''',

    "LEAKING_FIXTURE": '''
Customer has a leaking fixture. Ask location and severity:
"Which fixture is leaking (toilet, sink, shower)? Is it dripping, running continuously, or actively leaking?"''',

    "INSTALL_REQUEST": '''
Customer wants to install a new fixture. Ask location and type:
"Where would you like to install the new fixture (kitchen, bathroom, laundry)? What type of fixture (toilet, sink, shower)?"''',

    "WATER_HEATER_ISSUE": '''
Customer has a water heater issue. Ask location and severity:
"Is the water heater making noise, leaking, or not heating up?"''',

    "QUOTE_REQUEST": '''
Customer wants a quote for a plumbing service. Ask location and type:
"What type of plumbing service do you need (plumbing, heating, cooling)?"''',

    "REMODEL_INQUIRY": '''
Customer wants to remodel their home. Ask location and type:
"What type of remodel do you want (bathroom, kitchen, laundry)?"''',

    "RECURRING_PROBLEM": '''
Customer has a recurring problem. Ask location and type:
"What type of recurring problem do you have (leaking, clogging, etc.)?"''',

    "DRAIN_MAINTENANCE": '''
Customer wants to maintain their drain. Ask location and type:
"What type of drain maintenance do you need (cleaning, inspection, etc.)?"''',

    "GENERAL_INQUIRY": '''
Customer has a general inquiry. Ask location and type:
"What type of general inquiry do you have (plumbing, heating, cooling)?"''',
}

SCHEDULER_PROMPT = '''
After collecting the necessary details (issue, address, date/time), summarize and present booking options:
"I've got your {issue_tag} at {address}. We can arrive on {day} between {window}. Our flat-rate for this is {price}. Reply 'CONFIRM' to book or 'CHANGE' to adjust."'''