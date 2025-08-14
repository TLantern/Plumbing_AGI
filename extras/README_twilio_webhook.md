# Twilio Webhook for Plumbing Intent Recognition

This project sets up a Twilio webhook that allows you to call a phone number, describe a plumbing issue, and receive an SMS with the analyzed intent and service classification.

## 🎯 Features

- **Phone Call Integration**: Call a Twilio number and describe your plumbing issue
- **Speech-to-Text**: Automatic transcription of your voice message
- **Intent Recognition**: Analysis using the plumbing services classification system
- **SMS Results**: Receive detailed analysis results via text message
- **Real-time Processing**: Immediate analysis and response

## 📋 Prerequisites

1. **Twilio Account**: Sign up at [twilio.com](https://www.twilio.com)
2. **Twilio Phone Number**: Purchase a phone number in your Twilio console
3. **Python 3.7+**: Ensure Python is installed on your system
4. **ngrok** (for testing): Download from [ngrok.com](https://ngrok.com)

## 🚀 Quick Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Run Setup Wizard

```bash
python3 setup_twilio.py
```

This will:
- Prompt for your Twilio credentials
- Create a `.env` file with your configuration
- Test the intent recognition system
- Create a test script

### 3. Start the Flask Server

```bash
python3 twilio_webhook.py
```

The server will start on `http://localhost:5000`

### 4. Set Up Public Access (for Twilio webhooks)

```bash
ngrok http 5000
```

Copy the HTTPS URL (e.g., `https://abc123.ngrok.io`)

### 5. Configure Twilio Webhook

1. Go to [Twilio Console](https://console.twilio.com)
2. Navigate to Phone Numbers > Manage > Active numbers
3. Click on your phone number
4. Set the webhook URL to: `https://your-ngrok-url.ngrok.io/webhook`
5. Set HTTP Method to: `POST`
6. Save the configuration

## 📞 How It Works

### Call Flow

1. **Call the Twilio number**
2. **Greeting**: System welcomes you and asks you to describe your issue
3. **Recording**: Speak for up to 60 seconds about your plumbing problem
4. **Processing**: System transcribes your speech and analyzes the intent
5. **SMS Results**: Receive a text message with the analysis

### Example Call

**You say**: "My kitchen sink is clogged and water is backing up. I need someone to come fix it as soon as possible."

**You receive via SMS**:
```
🔧 PLUMBING INTENT ANALYSIS

📝 Your message: My kitchen sink is clogged and water is backing up. I need someone to come fix it as soon as possible...

🎯 PRIMARY INTENT: Clogged Kitchen Sink
📋 SECONDARY: Emergency Leak

📞 Call back anytime for another analysis!
```

## 🧪 Testing

### Test Without Twilio

```bash
python3 test_webhook.py
```

This will test:
- Intent recognition with sample texts
- Webhook simulation
- API endpoints

### Test Intent Recognition

```bash
curl -X POST http://localhost:5000/test-intent \
  -H "Content-Type: application/json" \
  -d '{"text": "My kitchen sink is clogged and water is backing up"}'
```

### Test Health Check

```bash
curl http://localhost:5000/health
```

## 📊 API Endpoints

### Webhook Endpoints

- `POST /webhook` - Main Twilio webhook endpoint
- `POST /transcription` - Handle call recordings
- `POST /transcription-callback` - Process transcriptions

### Management Endpoints

- `GET /health` - Health check
- `GET /status` - Get all call statuses
- `GET /call/<call_sid>` - Get specific call details
- `POST /test-intent` - Test intent recognition

## 🔧 Configuration

### Environment Variables

Create a `.env` file with:

```env
# Twilio Configuration
TWILIO_ACCOUNT_SID=your_account_sid_here
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_PHONE_NUMBER=+1234567890

# Flask Configuration
FLASK_ENV=development
PORT=5000
```

### Twilio Console Setup

1. **Account SID**: Found in your Twilio Console dashboard
2. **Auth Token**: Found in your Twilio Console dashboard
3. **Phone Number**: Your purchased Twilio phone number

## 📱 SMS Message Format

The SMS includes:
- 🔧 **Header**: Plumbing Intent Analysis
- 📝 **Original Message**: First 100 characters of your description
- 🎯 **Primary Intent**: Main service type detected
- 📋 **Secondary Intents**: Additional services detected
- ℹ️ **Additional Info**: Any relevant details
- 📞 **Call to Action**: Invitation to call back

## 🛠️ Troubleshooting

### Common Issues

1. **"Twilio credentials not configured"**
   - Run `python3 setup_twilio.py` to configure credentials
   - Check your `.env` file exists and has correct values

2. **"Flask server not running"**
   - Start the server: `python3 twilio_webhook.py`
   - Check port 5000 is available

3. **"ngrok not working"**
   - Install ngrok: `brew install ngrok` (macOS)
   - Start tunnel: `ngrok http 5000`
   - Update Twilio webhook URL with new ngrok URL

4. **"SMS not sending"**
   - Verify Twilio credentials are correct
   - Check your phone number is verified in Twilio
   - Ensure you have Twilio credits

### Debug Mode

Run with debug logging:

```bash
export FLASK_ENV=development
python3 twilio_webhook.py
```

### Check Call Status

```bash
curl http://localhost:5000/status
```

## 🔒 Security Considerations

- **Environment Variables**: Never commit `.env` file to version control
- **HTTPS**: Use ngrok HTTPS URL for production
- **Validation**: Validate all incoming webhook data
- **Rate Limiting**: Consider implementing rate limiting for production

## 🚀 Production Deployment

For production deployment:

1. **Use a proper web server** (Gunicorn, uWSGI)
2. **Set up HTTPS** with a proper SSL certificate
3. **Use a database** instead of in-memory storage
4. **Implement logging** and monitoring
5. **Set up error handling** and alerts
6. **Use environment-specific configurations**

## 📈 Monitoring

### Logs

The application logs:
- Incoming calls
- Transcription results
- Intent analysis
- SMS delivery status
- Errors and exceptions

### Metrics

Track:
- Call volume
- Transcription accuracy
- Intent recognition success rate
- SMS delivery rate
- Response times

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License.

## 🆘 Support

For issues and questions:
1. Check the troubleshooting section
2. Review the logs for error messages
3. Test with the provided test scripts
4. Create an issue in the repository

---

**Happy plumbing! 🔧📞** 