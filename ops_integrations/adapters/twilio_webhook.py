#!/usr/bin/env python3
"""
Twilio Webhook for Phone Calls with Transcription and Intent Recognition
Integrates with the plumbing services intent recognition system.
"""

from flask import Flask, request, jsonify
from twilio.twiml.voice_response import VoiceResponse
from twilio.rest import Client
import os
import json
import logging
from datetime import datetime
import sys
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add the parent directory to the path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# Import the plumbing services intent recognition
from adapters.plumbing_services import infer_multiple_job_types_from_text

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Twilio configuration
TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID', 'your_account_sid_here')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN', 'your_auth_token_here')
TWILIO_PHONE_NUMBER = os.environ.get('TWILIO_FROM_NUMBER', os.environ.get('TWILIO_PHONE_NUMBER', '+1234567890'))

# Initialize Twilio client
client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# Store call data (in production, use a database)
call_data = {}

@app.route('/webhook', methods=['POST'])
def webhook():
    """Main webhook endpoint for incoming calls."""
    try:
        # Get call details from Twilio - try both form data and query params
        call_sid = request.form.get('CallSid') or request.args.get('callSid')
        from_number = request.form.get('From')
        to_number = request.form.get('To')
        
        logger.info(f"New call received - SID: {call_sid}, From: {from_number}, To: {to_number}")
        logger.info(f"Query params: {dict(request.args)}")
        logger.info(f"Form data keys: {list(request.form.keys())}")
        
        # Store call data
        call_data[call_sid] = {
            'call_sid': call_sid,
            'from_number': from_number,
            'to_number': to_number,
            'start_time': datetime.now().isoformat(),
            'transcription': '',
            'intent_results': None,
            'status': 'incoming'
        }
        
        # Create TwiML response
        response = VoiceResponse()
        
        # Greeting message
        response.say("Thank you for calling SafeHarbour Plumbing Services. We're here to help with all your plumbing needs. What can we assist you with today?", voice='alice')
        
        # Add callSid to the transcription callback URL
        transcription_callback_url = f"/transcription-callback?callSid={call_sid}" if call_sid else "/transcription-callback"
        
        # Record the call with transcription
        response.record(
            action='/transcription',
            method='POST',
            maxLength=60,  # 60 seconds max
            transcribe=True,
            transcribeCallback=transcription_callback_url,
            playBeep=True
        )
        
        # If no recording, provide fallback
        response.say("If you didn't record anything, please call back and try again.", voice='alice')
        response.hangup()
        
        return str(response)
        
    except Exception as e:
        logger.error(f"Error in webhook: {e}")
        response = VoiceResponse()
        response.say("Sorry, there was an error processing your call. Please try again.", voice='alice')
        response.hangup()
        return str(response)

@app.route('/voice', methods=['POST'])
def voice_webhook():
    """Voice webhook endpoint - same as /webhook."""
    return webhook()

@app.route('/', methods=['POST'])
def root_webhook():
    """Root webhook endpoint - same as /webhook."""
    return webhook()

@app.route('/', methods=['GET'])
def root_get():
    """Root GET endpoint for health checks."""
    return jsonify({
        'status': 'Plumbing Services Intent Recognition Webhook',
        'endpoints': {
            'webhook': '/webhook (POST)',
            'voice': '/voice (POST)', 
            'transcription': '/transcription (POST)',
            'transcription_callback': '/transcription-callback (POST)',
            'status': '/status (GET)',
            'health': '/health (GET)',
            'test_intent': '/test-intent (POST)'
        },
        'timestamp': datetime.now().isoformat()
    })

@app.route('/transcription', methods=['POST'])
def handle_transcription():
    """Handle the recording and transcription."""
    try:
        call_sid = request.form.get('CallSid')
        recording_url = request.form.get('RecordingUrl')
        
        logger.info(f"Recording received for call {call_sid}: {recording_url}")
        
        if call_sid in call_data:
            call_data[call_sid]['recording_url'] = recording_url
            call_data[call_sid]['status'] = 'recording_received'
        
        # Create response
        response = VoiceResponse()
        response.say("Thank you for your message. I'm processing your request now. "
                    "You'll receive a text message with the analysis results.", voice='alice')
        response.hangup()
        
        return str(response)
        
    except Exception as e:
        logger.error(f"Error in transcription handler: {e}")
        response = VoiceResponse()
        response.say("Sorry, there was an error processing your recording.", voice='alice')
        response.hangup()
        return str(response)

@app.route('/transcription-callback', methods=['POST'])
def transcription_callback():
    """Handle transcription callback from Twilio."""
    try:
        # Get callSid from both form data and query params
        call_sid = request.form.get('CallSid') or request.args.get('callSid')
        transcription_text = request.form.get('TranscriptionText', '')
        transcription_status = request.form.get('TranscriptionStatus', '')
        
        logger.info(f"Transcription callback for call {call_sid}: {transcription_status}")
        logger.info(f"Query params: {dict(request.args)}")
        logger.info(f"Form data keys: {list(request.form.keys())}")
        logger.info(f"Transcription text: {transcription_text}")
        
        if call_sid in call_data:
            call_data[call_sid]['transcription'] = transcription_text
            call_data[call_sid]['transcription_status'] = transcription_status
            call_data[call_sid]['status'] = 'transcription_received'
            
            # Analyze intent using plumbing services
            if transcription_text:
                intent_results = infer_multiple_job_types_from_text(transcription_text)
                call_data[call_sid]['intent_results'] = intent_results
                call_data[call_sid]['status'] = 'analysis_complete'
                
                # Send SMS with results
                send_results_sms(call_sid, transcription_text, intent_results)
        
        return jsonify({'status': 'success'})
        
    except Exception as e:
        logger.error(f"Error in transcription callback: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

def send_results_sms(call_sid, transcription, intent_results):
    """Send SMS with analysis results."""
    try:
        if call_sid not in call_data:
            logger.error(f"Call data not found for {call_sid}")
            return
        
        from_number = call_data[call_sid]['from_number']
        
        # Format the results message
        message = format_results_message(transcription, intent_results)
        
        # Send SMS
        message_sent = client.messages.create(
            body=message,
            from_=TWILIO_PHONE_NUMBER,
            to=from_number
        )
        
        logger.info(f"SMS sent to {from_number}: {message_sent.sid}")
        
        # Store SMS info
        call_data[call_sid]['sms_sent'] = True
        call_data[call_sid]['sms_sid'] = message_sent.sid
        
    except Exception as e:
        logger.error(f"Error sending SMS: {e}")

def format_results_message(transcription, intent_results):
    """Format the results message for SMS."""
    message = "🔧 PLUMBING INTENT ANALYSIS\n\n"
    message += f"📝 Your message: {transcription[:100]}...\n\n"
    
    if intent_results and intent_results.get('primary'):
        primary = intent_results['primary']
        secondary = intent_results.get('secondary', [])
        
        message += f"🎯 PRIMARY INTENT: {primary.replace('_', ' ').title()}\n"
        
        if secondary:
            message += f"📋 SECONDARY: {', '.join([s.replace('_', ' ').title() for s in secondary])}\n"
        
        if intent_results.get('description_suffix'):
            message += f"ℹ️ {intent_results['description_suffix']}\n"
    else:
        message += "❓ No specific plumbing intent detected\n"
    
    message += "\n📞 Call back anytime for another analysis!"
    
    return message

@app.route('/status', methods=['GET'])
def get_status():
    """Get status of all calls."""
    return jsonify({
        'total_calls': len(call_data),
        'calls': call_data
    })

@app.route('/call/<call_sid>', methods=['GET'])
def get_call_details(call_sid):
    """Get details of a specific call."""
    if call_sid in call_data:
        return jsonify(call_data[call_sid])
    else:
        return jsonify({'error': 'Call not found'}), 404

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'twilio_configured': bool(TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN)
    })

@app.route('/test-intent', methods=['POST'])
def test_intent():
    """Test endpoint for intent recognition without Twilio."""
    try:
        data = request.get_json()
        text = data.get('text', '')
        
        if not text:
            return jsonify({'error': 'No text provided'}), 400
        
        intent_results = infer_multiple_job_types_from_text(text)
        
        return jsonify({
            'input_text': text,
            'intent_results': intent_results,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error in test intent: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Check if Twilio credentials are configured
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN or not TWILIO_PHONE_NUMBER:
        logger.warning("Twilio credentials not found in environment variables.")
        logger.warning("Please ensure .env file contains: TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER")
        logger.info("Running in test mode - webhook endpoints will work but SMS won't be sent")
    else:
        logger.info("Twilio credentials loaded successfully")
    
    # Run the Flask app
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=True) 