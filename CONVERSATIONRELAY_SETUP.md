# ConversationRelay + CI Setup Guide

## Overview
The salon phone service has been refactored to use Twilio's modern ConversationRelay + Conversational Intelligence (CI) architecture for low-latency voice AI with post-call analytics.

## Required Environment Variables

Add these to your `.env` file:

```bash
# Twilio credentials
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token_here

# OpenAI for conversational AI
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Public URLs (use your ngrok URL for local development)
PUBLIC_BASE_URL=https://your-ngrok-url.ngrok.io
WSS_PUBLIC_URL=wss://your-ngrok-url.ngrok.io

# Optional: Conversational Intelligence (GA Service SID)
CI_SERVICE_SID=CIxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Optional: ElevenLabs voice selection (used by Twilio TTS)
ELEVENLABS_VOICE_ID=kdmDKE6EkgrWrrykO9Qt
```

## Twilio Console Configuration

### 1. Voice Webhook
- Go to Phone Numbers → Manage → Active Numbers
- Click your phone number
- Set Voice webhook to: `POST https://your-ngrok-url.ngrok.io/voice`

### 2. Conversational Intelligence (Optional)
- Go to Intelligence → Services
- Create a new GA Service
- Set transcript webhook to: `POST https://your-ngrok-url.ngrok.io/intelligence/transcripts`
- Copy the Service SID to `CI_SERVICE_SID` in your `.env`

## Local Development Setup

### 1. Start ngrok
```bash
ngrok http 5001
```

### 2. Update .env with ngrok URLs
```bash
PUBLIC_BASE_URL=https://abc123.ngrok.io
WSS_PUBLIC_URL=wss://abc123.ngrok.io
```

### 3. Run the service
```bash
./scripts/salon_dev.sh
```

## Testing

### 1. Health Check
```bash
curl http://localhost:5001/health
```
Should return:
```json
{
  "ok": true,
  "ci": true,
  "relay": true
}
```

### 2. Test Call
- Call your Twilio number
- You should hear: "Hey, I'm your AI assistant. How can I help?"
- Speak and get real-time AI responses
- Speaking over the AI should interrupt cleanly

### 3. Check Logs
- Look for ConversationRelay WebSocket connections
- CI transcript webhooks (if configured)
- Call analytics and insights

## Architecture Changes

### Before (Old Service)
- TwiML with `<Record transcribe="true">`
- Custom audio processing
- Manual conversation state management
- Post-call transcription only

### After (ConversationRelay + CI)
- TwiML with `<Connect><ConversationRelay>`
- Real-time WebSocket communication
- Streaming AI responses with barge-in
- Live transcription + post-call analytics
- Twilio handles audio processing

## Troubleshooting

### Common Issues

1. **"Invalid Twilio signature"**
   - Ensure `PUBLIC_BASE_URL` matches your ngrok URL exactly
   - Check that URLs use `https://` and `wss://` schemes

2. **WebSocket connection fails**
   - Verify `WSS_PUBLIC_URL` starts with `wss://`
   - Check ngrok is running and accessible

3. **No CI transcripts**
   - Verify `CI_SERVICE_SID` is set correctly
   - Check CI webhook URL in Twilio Console

4. **TTS not working**
   - ElevenLabs voice ID should be set in `ELEVENLABS_VOICE_ID`
   - Twilio will handle TTS using your preferred voice

### Logs to Check
- Service startup messages
- WebSocket connection logs
- CI webhook payloads
- Call analytics and insights

## Benefits

- **Low Latency**: Real-time streaming responses
- **Barge-in**: Interrupt AI speech naturally
- **Better Analytics**: Structured insights from CI
- **Simplified**: No custom audio processing needed
- **Reliable**: Twilio handles voice quality and transcription
