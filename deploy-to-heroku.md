# Deploying to Heroku

This guide will help you deploy both the salon-dashboard (Next.js frontend) and phone (FastAPI backend) applications to Heroku.

## Prerequisites

1. **Heroku CLI** installed
2. **Git** repository initialized
3. **Heroku account** with verified payment method

## Deployment Steps

### 1. Create Heroku Apps

Create two separate Heroku apps for the frontend and backend:

```bash
# Create app for salon-dashboard (frontend)
heroku create your-salon-dashboard-app-name

# Create app for phone service (backend)
heroku create your-phone-service-app-name
```

### 2. Deploy Phone Service (Backend)

The phone service is the FastAPI application that handles Twilio webhooks and phone calls.

```bash
# Navigate to project root
cd /path/to/your/plumbing-agi

# Add Heroku remote for phone service
heroku git:remote -a your-phone-service-app-name

# Set environment variables for phone service
heroku config:set TWILIO_ACCOUNT_SID=your_twilio_account_sid
heroku config:set TWILIO_AUTH_TOKEN=your_twilio_auth_token
heroku config:set TWILIO_FROM_NUMBER=+1234567890
heroku config:set OPENAI_API_KEY=your_openai_api_key
heroku config:set ELEVENLABS_API_KEY=your_elevenlabs_api_key
heroku config:set ELEVENLABS_VOICE_ID=kdmDKE6EkgrWrrykO9Qt

# Deploy phone service
git add .
git commit -m "Deploy phone service to Heroku"
git push heroku main
```

### 3. Deploy Salon Dashboard (Frontend)

The salon dashboard is the Next.js application that displays real-time call analytics.

```bash
# Navigate to frontend directory
cd frontend

# Add Heroku remote for salon dashboard
heroku git:remote -a your-salon-dashboard-app-name

# Set environment variables for frontend
heroku config:set NEXT_PUBLIC_PHONE_API_URL=https://your-phone-service-app-name.herokuapp.com
heroku config:set NEXT_PUBLIC_SALON_API_URL=https://your-phone-service-app-name.herokuapp.com

# Deploy salon dashboard
git add .
git commit -m "Deploy salon dashboard to Heroku"
git push heroku main
```

### 4. Configure Twilio Webhook

After deployment, update your Twilio phone number webhook URL:

1. Go to [Twilio Console > Phone Numbers](https://console.twilio.com/us1/develop/phone-numbers/manage/incoming)
2. Click on your phone number
3. Set the webhook URL to: `https://your-phone-service-app-name.herokuapp.com/voice`
4. Set HTTP Method to: `POST`
5. Save configuration

### 5. Verify Deployment

Check that both applications are running:

```bash
# Check phone service
curl https://your-phone-service-app-name.herokuapp.com/health

# Check salon dashboard
curl https://your-salon-dashboard-app-name.herokuapp.com
```

## Environment Variables

### Phone Service Environment Variables

Set these in your phone service Heroku app:

```bash
heroku config:set TWILIO_ACCOUNT_SID=your_twilio_account_sid
heroku config:set TWILIO_AUTH_TOKEN=your_twilio_auth_token
heroku config:set TWILIO_FROM_NUMBER=+1234567890
heroku config:set OPENAI_API_KEY=your_openai_api_key
heroku config:set ELEVENLABS_API_KEY=your_elevenlabs_api_key
heroku config:set ELEVENLABS_VOICE_ID=kdmDKE6EkgrWrrykO9Qt
heroku config:set EXTERNAL_WEBHOOK_URL=https://your-phone-service-app-name.herokuapp.com
```

### Salon Dashboard Environment Variables

Set these in your salon dashboard Heroku app:

```bash
heroku config:set NEXT_PUBLIC_PHONE_API_URL=https://your-phone-service-app-name.herokuapp.com
heroku config:set NEXT_PUBLIC_SALON_API_URL=https://your-phone-service-app-name.herokuapp.com
```

## Troubleshooting

### Common Issues

1. **Build Failures**: Check Heroku logs with `heroku logs --tail`
2. **Environment Variables**: Ensure all required environment variables are set
3. **Port Configuration**: Both apps use `$PORT` environment variable automatically
4. **CORS Issues**: The phone service has CORS configured to allow all origins

### Checking Logs

```bash
# Phone service logs
heroku logs --tail -a your-phone-service-app-name

# Salon dashboard logs
heroku logs --tail -a your-salon-dashboard-app-name
```

### Scaling

For production use, consider scaling your apps:

```bash
# Scale phone service
heroku ps:scale web=1 -a your-phone-service-app-name

# Scale salon dashboard
heroku ps:scale web=1 -a your-salon-dashboard-app-name
```

## URLs After Deployment

- **Phone Service**: `https://your-phone-service-app-name.herokuapp.com`
- **Salon Dashboard**: `https://your-salon-dashboard-app-name.herokuapp.com`
- **Phone Service Health Check**: `https://your-phone-service-app-name.herokuapp.com/health`
- **Twilio Webhook**: `https://your-phone-service-app-name.herokuapp.com/voice`
