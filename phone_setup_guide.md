# Phone.py Setup Guide - Real-Time Speech Recognition

This guide helps you set up `phone.py` for real-time speech recognition with Twilio WebSocket streaming.

## Prerequisites

1. **Twilio Account** with phone number
2. **OpenAI API Key** for Whisper transcription
3. **ngrok** for local development tunnel
4. **Environment variables** configured

## Setup Steps

### 1. Install Dependencies

```bash
pip install fastapi uvicorn twilio openai python-dotenv
```

### 2. Install ngrok

```bash
# macOS
brew install ngrok

# Or download from https://ngrok.com/download
```

### 3. Create Environment File

Copy the template and fill in your actual values:

```bash
cp env_local.txt .env
```

Edit `.env` with your credentials:

```bash
# Twilio Configuration
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_twilio_auth_token_here
TWILIO_FROM_NUMBER=+1234567890

# OpenAI Configuration
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# External URL (will be set after starting ngrok)
EXTERNAL_WEBHOOK_URL=https://your-ngrok-url.ngrok.io
```

### 4. Start ngrok Tunnel

```bash
ngrok http 5001
```

Copy the HTTPS URL (e.g., `https://abc123.ngrok.io`) and update your `.env`:

```bash
EXTERNAL_WEBHOOK_URL=https://abc123.ngrok.io
```

### 5. Configure Twilio Webhook

1. Go to [Twilio Console > Phone Numbers](https://console.twilio.com/us1/develop/phone-numbers/manage/incoming)
2. Click on your phone number
3. Set the webhook URL to: `https://your-ngrok-url.ngrok.io/voice`
4. Set HTTP Method to: `POST`
5. Save configuration

### 6. Start the Phone Service

```bash
python ops_integrations/adapters/phone.py
```

### 7. Test the System

1. Call your Twilio phone number
2. Wait for the greeting message
3. Speak your plumbing request
4. The system should:
   - Transcribe your speech in real-time (every 3 seconds)
   - Extract plumbing intents
   - Respond with booking information

## Troubleshooting

### Speech Not Being Recognized

1. **Check WebSocket URL**: Ensure `EXTERNAL_WEBHOOK_URL` in `.env` matches your ngrok URL
2. **Verify ngrok**: Make sure ngrok is running and accessible
3. **Check Logs**: Look for WebSocket connection errors in the console
4. **Test Audio Format**: Verify PCM audio is being received properly

### Common Issues

#### 1. "Missing CallSid in webhook payload"
- Check that Twilio webhook URL is configured correctly
- Ensure the endpoint is `/voice` not `/webhook`

#### 2. "WebSocket connection failed"
- Verify ngrok URL is correct and accessible
- Check that ngrok tunnel is still active
- Ensure no firewall blocking WebSocket connections

#### 3. "Whisper ASR error"
- Verify OpenAI API key is correct
- Check that audio buffering is working properly
- Look for audio format conversion issues

#### 4. "Invalid JSON in media packet"
- This usually indicates WebSocket connection issues
- Check ngrok tunnel and external URL configuration

### Differences from twilio_webhook.py

| Feature | twilio_webhook.py | phone.py |
|---------|------------------|----------|
| **Transcription** | Twilio's built-in service | OpenAI Whisper real-time |
| **Response Time** | After call ends | Real-time (3-second chunks) |
| **Setup Complexity** | Simple HTTP endpoints | Requires WebSocket + ngrok |
| **Accuracy** | Good | Excellent (Whisper) |
| **Real-time** | No | Yes |

### Performance Tuning

- **Chunk Duration**: Adjust `CHUNK_DURATION_SEC` in phone.py (1-5 seconds)
- **Audio Quality**: Twilio streams 16kHz mono PCM (good quality)
- **Response Time**: ~3 seconds for transcription + intent processing

## Next Steps

Once phone.py is working:

1. **Test Intent Recognition**: Try various plumbing requests
2. **Test Job Booking**: Verify emergency vs scheduled booking works
3. **Calendar Integration**: Ensure Google Calendar booking works
4. **Production Deployment**: Replace ngrok with permanent webhook URL

## Support

If you continue having issues:

1. Check the console logs for detailed error messages
2. Test with `twilio_webhook.py` first to verify basic setup
3. Use the `/test-intent` endpoint to test intent recognition separately
4. Verify all environment variables are loaded correctly 