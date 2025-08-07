#!/usr/bin/env python3
"""
Flask webhook server for handling incoming SMS messages from Twilio
"""
from flask import Flask, request, jsonify
import os
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv('../.env')

# Import our SMS adapter
from adapters.sms import SMSAdapter

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Initialize SMS adapter
sms_adapter = SMSAdapter()

@app.route('/webhook/sms', methods=['POST'])
@app.route('/sms', methods=['POST'])
def handle_incoming_sms():
    """Handle incoming SMS webhook from Twilio."""
    try:
        # Get the incoming message data from Twilio
        from_number = request.form.get('From')
        to_number = request.form.get('To')
        message_body = request.form.get('Body', '')
        
        logger.info(f"📨 Incoming SMS from {from_number} to {to_number}: {message_body}")
        
        # Process the message using our SMS adapter
        result = sms_adapter.handle_incoming_message(from_number, message_body)
        
        logger.info(f"📤 Response result: {result}")
        
        # Return a TwiML response (optional - Twilio will still send the SMS)
        return jsonify({
            "success": True,
            "message": "SMS processed successfully",
            "result": result
        })
        
    except Exception as e:
        logger.error(f"❌ Error processing incoming SMS: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "sms_enabled": sms_adapter.enabled,
        "from_number": sms_adapter.from_number
    })

@app.route('/', methods=['GET'])
def home():
    """Home page with instructions."""
    return """
    <h1>🚰 Plumbing AGI SMS Webhook Server</h1>
    <p>This server handles incoming SMS messages from Twilio.</p>
    <h2>Endpoints:</h2>
    <ul>
        <li><strong>POST /webhook/sms</strong> - Handle incoming SMS messages (primary)</li>
        <li><strong>POST /sms</strong> - Handle incoming SMS messages (alternative)</li>
        <li><strong>GET /health</strong> - Health check</li>
    </ul>
    <h2>Setup Instructions:</h2>
    <ol>
        <li>Make this server publicly accessible (ngrok, etc.)</li>
        <li>Set the webhook URL in Twilio Console</li>
        <li>Send SMS to your Twilio number to test</li>
    </ol>
    <p><strong>Current Status:</strong> SMS Adapter Enabled: {}</p>
    <p><strong>From Number:</strong> {}</p>
    """.format(sms_adapter.enabled, sms_adapter.from_number)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    host = os.environ.get('HOST', '0.0.0.0')
    
    print(f"🚀 Starting SMS Webhook Server on {host}:{port}")
    print(f"📱 SMS Adapter Enabled: {sms_adapter.enabled}")
    print(f"📞 From Number: {sms_adapter.from_number}")
    print(f"🌐 Webhook URL: http://{host}:{port}/webhook/sms")
    print(f"❤️  Health Check: http://{host}:{port}/health")
    
    app.run(host=host, port=port, debug=True) 