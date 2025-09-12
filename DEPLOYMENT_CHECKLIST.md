# 🚀 Heroku Deployment Checklist

## ✅ Pre-Deployment Checklist

### **Code Quality**
- ✅ No linting errors
- ✅ Circular import issues fixed
- ✅ All imports working correctly
- ✅ Service imports successfully

### **Data Setup**
- ✅ SoHo Salon Denton data in Supabase
  - 37 services stored
  - 1 salon info record
  - 1 professional record
  - 1 knowledge base record
- ✅ Local data backup in `ops_integrations/data/location_1.json`
- ✅ Environment variables configured

### **Configuration**
- ✅ Phone mapping: `+18084826296` → Location 1
- ✅ Supabase credentials set
- ✅ Voice ID configured: `kdmDKE6EkgrWrrykO9Qt`
- ✅ Profile linked: `c8b447d7-90ed-42e7-858c-2a667989a52a`

### **Files Ready**
- ✅ `requirements.txt` updated with Supabase
- ✅ `Procfile` configured for salon phone service
- ✅ All setup scripts created and tested

## 🚀 Deployment Steps

### **1. Set Heroku Environment Variables**
```bash
heroku config:set SUPABASE_URL="https://yzoalegdsogecfiqzfbp.supabase.co"
heroku config:set SUPABASE_ANON_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inl6b2FsZWdkc29nZWNmaXF6ZmJwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTc2NTMyNzIsImV4cCI6MjA3MzIyOTI3Mn0.rZe11f29kVYP9_oI3ER6NAHPrYs5r6U4ksasV272HGw"
heroku config:set PHONE_TO_LOCATION_MAP='{"+18084826296": 1}'
heroku config:set DEFAULT_LOCATION_ID=1
heroku config:set ELEVENLABS_VOICE_ID=kdmDKE6EkgrWrrykO9Qt
```

### **2. Deploy to Heroku**
```bash
git add .
git commit -m "Add SoHo Salon Denton with Supabase integration"
git push heroku main
```

### **3. Verify Deployment**
```bash
# Check logs
heroku logs --tail

# Test endpoints
curl https://your-app.herokuapp.com/shop/1/config
curl https://your-app.herokuapp.com/shops
curl https://your-app.herokuapp.com/metrics
```

### **4. Test Phone System**
- Call `+18084826296` (SoHo Salon Denton)
- Verify location detection works
- Test AI responses with salon-specific knowledge
- Check real-time dashboard updates

## 🧪 Testing Checklist

### **API Endpoints**
- [ ] `/shop/1/config` - Returns SoHo Salon configuration
- [ ] `/shops` - Lists all shops (should show SoHo Salon)
- [ ] `/metrics` - Returns real-time metrics
- [ ] `/setup-location/1` - Can update salon data

### **Phone System**
- [ ] Incoming calls to `+18084826296` detected as Location 1
- [ ] AI responses include SoHo Salon services and pricing
- [ ] FAQ responses work correctly
- [ ] Booking suggestions are appropriate

### **Supabase Integration**
- [ ] Data loads from Supabase on startup
- [ ] Real-time updates work
- [ ] Frontend dashboard receives data
- [ ] No fallback to local storage warnings

### **Performance**
- [ ] Service starts within 30 seconds
- [ ] AI responses under 3 seconds
- [ ] WebSocket connections stable
- [ ] No memory leaks

## 🎯 Success Criteria

- ✅ SoHo Salon Denton fully operational
- ✅ 37 services available to AI
- ✅ Real-time frontend updates
- ✅ Persistent Supabase storage
- ✅ Phone system working end-to-end
- ✅ No critical errors in logs

## 🔧 Troubleshooting

### **If Supabase connection fails:**
- Check environment variables
- Verify Supabase project is active
- Check network connectivity

### **If phone system doesn't work:**
- Verify Twilio webhook URLs
- Check phone number mapping
- Test with curl endpoints first

### **If AI responses are generic:**
- Verify knowledge data loaded
- Check location detection
- Test with `/shop/1/config` endpoint

## 📊 Post-Deployment Monitoring

- Monitor Heroku logs for errors
- Check Supabase usage and performance
- Track call volume and success rates
- Monitor AI response times
- Watch for any service interruptions
