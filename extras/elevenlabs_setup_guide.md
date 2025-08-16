# ElevenLabs TTS Integration Setup Guide

This guide will help you set up ElevenLabs text-to-speech integration for your SafeHarbor Plumbing Services phone system.

## What is ElevenLabs?

ElevenLabs is a leading AI voice technology platform that provides high-quality, natural-sounding text-to-speech voices. It offers more natural and expressive voices compared to standard TTS services.

## Voice Selection

The system is configured to use the voice with ID `kdmDKE6EkgrWrrykO9Qt` from the ElevenLabs voice library. You can view this voice at:
https://elevenlabs.io/app/voice-library?voiceId=kdmDKE6EkgrWrrykO9Qt

## Setup Steps

### 1. Get ElevenLabs API Key

1. Go to [ElevenLabs](https://elevenlabs.io/) and create an account
2. Navigate to your [API Key page](https://elevenlabs.io/app/api-key)
3. Copy your API key

### 2. Configure Environment Variables

Add the following to your `.env` file:

```bash
# ElevenLabs Configuration (for text-to-speech)
ELEVENLABS_API_KEY=your_actual_api_key_here
ELEVENLABS_VOICE_ID=kdmDKE6EkgrWrrykO9Qt
ELEVENLABS_MODEL_ID=eleven_multilingual_v2
```

### 3. Test the Integration

Run the test script to verify everything is working:

```bash
python3 test_elevenlabs_tts.py
```

This will:
- Test direct ElevenLabs API integration
- Test the phone service integration
- Generate test audio files for verification

### 4. Restart Your Services

After configuring the environment variables, restart your phone service:

```bash
# If using the dev script
./scripts/dev.sh

# Or restart individual services as needed
```

## How It Works

The system uses a fallback approach:

1. **Primary**: ElevenLabs TTS (if configured)
2. **Fallback**: OpenAI TTS (if ElevenLabs fails or is not configured)

This ensures your phone system continues to work even if ElevenLabs is temporarily unavailable.

## Configuration Options

### Voice ID
- **Current**: `kdmDKE6EkgrWrrykO9Qt` (the voice you selected)
- **Change**: You can use any voice ID from your ElevenLabs voice library

### Model ID
- **Default**: `eleven_multilingual_v2` (supports multiple languages)
- **Alternatives**: 
  - `eleven_monolingual_v1` (English only, faster)
  - `eleven_turbo_v2` (faster generation)

### API Key Security
- Store your API key securely in the `.env` file
- Never commit API keys to version control
- The `.env` file is already in `.gitignore`

## Troubleshooting

### Common Issues

1. **"ELEVENLABS_API_KEY not found"**
   - Make sure you've added the API key to your `.env` file
   - Restart your services after adding the key

2. **"ElevenLabs TTS failed"**
   - Check your API key is correct
   - Verify you have sufficient credits in your ElevenLabs account
   - Check your internet connection

3. **"Voice ID not found"**
   - Verify the voice ID exists in your ElevenLabs account
   - Make sure you have access to the voice (some voices require subscription)

### Testing

Use the test script to verify your setup:

```bash
python3 test_elevenlabs_tts.py
```

This will generate test audio files that you can listen to verify the voice quality.

## Benefits

- **More Natural Sounding**: ElevenLabs voices sound more human-like
- **Better Expressiveness**: Voices can convey emotion and tone
- **Professional Quality**: Higher quality than standard TTS services
- **Fallback Support**: System continues working if ElevenLabs is unavailable

## Cost Considerations

- ElevenLabs offers free tier with limited usage
- Check [ElevenLabs pricing](https://elevenlabs.io/pricing) for your usage needs
- The system falls back to OpenAI TTS if you run out of ElevenLabs credits

## Support

If you encounter issues:
1. Check the logs for error messages
2. Run the test script to isolate the problem
3. Verify your API key and voice ID are correct
4. Check your ElevenLabs account status and credits 