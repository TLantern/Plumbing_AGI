#!/bin/bash

# Deploy Enhanced Google Sheets Integration to Heroku
# This script deploys the salon phone service with enhanced metrics tracking

echo "🚀 Deploying Enhanced Google Sheets Integration to Heroku..."

# Check if we're in the right directory
if [ ! -f "ops_integrations/services/salon_phone_service.py" ]; then
    echo "❌ Error: Please run this script from the project root directory"
    exit 1
fi

# Check if Heroku CLI is installed
if ! command -v heroku &> /dev/null; then
    echo "❌ Error: Heroku CLI is not installed. Please install it first."
    exit 1
fi

# Check if we're logged into Heroku
if ! heroku auth:whoami &> /dev/null; then
    echo "❌ Error: Not logged into Heroku. Please run 'heroku login' first."
    exit 1
fi

echo "📋 Pre-deployment checklist:"
echo "   ✅ Enhanced Google Sheets integration implemented"
echo "   ✅ New metrics: Revenue/call, Response speed, Call duration buckets"
echo "   ✅ Test function created and verified"
echo "   ✅ Salon phone service updated with metrics tracking"

# Deploy to Heroku
echo "🚀 Deploying to Heroku..."
git add .
git commit -m "Add enhanced Google Sheets tracking: revenue/call, response speed, call duration buckets

- Added new columns to Google Sheets: Call Duration Bucket, Response Speed, Revenue per Call
- Implemented call duration bucket classification: Short (<30s), Medium (30s-2min), Long (>2min)
- Added response speed calculation from first speech to first response
- Added revenue per call tracking based on service price and appointment scheduling
- Created test endpoint /test/sheets-integration for verification
- Enhanced salon phone service with comprehensive metrics tracking"

git push heroku main

echo "✅ Deployment completed!"
echo ""
echo "📊 Enhanced metrics now being tracked:"
echo "   • Call Duration Buckets: Short (<30s), Medium (30s-2min), Long (>2min)"
echo "   • Response Speed: Time from first speech to first response (in seconds)"
echo "   • Revenue per Call: Based on service price and appointment scheduling"
echo ""
echo "🧪 Test the integration:"
echo "   curl -X POST https://your-app.herokuapp.com/test/sheets-integration"
echo ""
echo "📈 Check your Google Sheets for the new columns and test data!"
