#!/usr/bin/env python3
"""
Simple webhook test script
"""
from flask import Flask, request, jsonify
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route('/webhook/sms', methods=['POST'])
@app.route('/sms', methods=['POST'])
def handle_incoming_sms():
    """Handle incoming SMS webhook"""
    try:
        # Get form data
        from_number = request.form.get('from') or request.form.get('From')
        to_number = request.form.get('originalsenderid') or request.form.get('To')
        message_body = request.form.get('message') or request.form.get('Body', '')
        
        logger.info(f"📨 Incoming SMS from {from_number} to {to_number}: {message_body}")
        
        return jsonify({
            "success": True,
            "message": "SMS processed successfully",
            "from": from_number,
            "to": to_number,
            "body": message_body
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
        "message": "Webhook server is running"
    })

@app.route('/', methods=['GET'])
def home():
    """Home page with instructions."""
    return """
    <h1>🚰 Simple Webhook Test Server</h1>
    <p>This server handles incoming SMS messages for testing.</p>
    <h2>Endpoints:</h2>
    <ul>
        <li><strong>POST /webhook/sms</strong> - Handle incoming SMS messages</li>
        <li><strong>POST /sms</strong> - Handle incoming SMS messages (alternative)</li>
        <li><strong>GET /health</strong> - Health check</li>
    </ul>
    <h2>Test with curl:</h2>
    <pre>
    curl -X POST http://localhost:5001/webhook/sms \\
         -d "from=+1234567890" \\
         -d "message=Hello World"
    </pre>
    """

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    host = os.environ.get('HOST', '0.0.0.0')
    
    print(f"🚀 Starting Simple Webhook Test Server on {host}:{port}")
    print(f"🌐 Webhook URL: http://{host}:{port}/webhook/sms")
    print(f"❤️  Health Check: http://{host}:{port}/health")
    
    app.run(host=host, port=port, debug=True) 