# Supabase Shop Customization Integration

## 🔄 How Shop Customization Works with Supabase Backend & Frontend

Your salon phone system now supports multiple shops with automatic detection and real-time frontend updates. Here's how all the pieces work together:

## 🏗️ **System Architecture**

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Phone Calls   │    │   Supabase DB   │    │   Frontend      │
│   (Per Shop)    │ ─→ │   (Unified)     │ ─→ │   Dashboard     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
        │                        │                        │
        ▼                        ▼                        ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ Location-       │    │ Real-time       │    │ Shop-Specific   │
│ Specific AI     │    │ Data Updates    │    │ Views & Data    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 📊 **Data Flow Overview**

### 1. **Phone Call → Shop Detection**
```python
# Incoming call to +18084826296
phone_number = "+18084826296"
location_id = get_location_from_phone_number(phone_number)  # Returns: 1

# Call context stored with location
conversation_context[call_sid] = {
    'location_id': 1,
    'phone_number': '+18084826296',
    'caller_number': '+19404656984',
    'messages': []
}
```

### 2. **Shop Data Storage in Supabase**
```sql
-- Main knowledge storage (shop-specific data)
salon_static_data:
  key: 'location_1', 'location_2', etc.
  data: {
    "business_name": "Beauty Salon Downtown",
    "services": [...],
    "professionals": [...],
    "faq_items": [...]
  }

-- Detailed service data (normalized)
scraped_services:
  salon_id: UUID (location reference)
  service_name: "Hair Cut"
  price: "$35"
  duration: "30 minutes"
  
-- Professional data (normalized)  
scraped_professionals:
  salon_id: UUID (location reference)
  name: "Sarah Johnson"
  specialties: ["Color", "Highlights"]
```

### 3. **Real-time Frontend Updates**
```javascript
// Frontend connects to WebSocket
const wsUrl = `wss://your-app.herokuapp.com:5001/ops`

// Receives location-specific data
{
  "type": "metrics",
  "data": {
    "location_id": 1,
    "business_name": "Beauty Salon Downtown",
    "recentCalls": [...],
    "activeBookings": [...]
  }
}
```

## 🔧 **Integration Points**

### **1. Supabase Storage Backend**

Your system uses a unified Supabase backend that handles:

```python
# Shop data storage
await supabase_storage.store_knowledge(
    key="location_2",
    data={
        "business_name": "Spa & Wellness Center",
        "services": scraped_services,
        "professionals": scraped_staff,
        "phone_number": "+1234567890"
    }
)

# Fallback to existing tables
await supabase_storage.insert_scraped_services(services_data, salon_id)
await supabase_storage.insert_salon_info(salon_data)
```

### **2. Phone Service Integration**

Each incoming call automatically detects the shop:

```python
# In salon_phone_service.py
@app.post("/voice")
async def voice_webhook(request: Request):
    to_number = form.get("To")
    location_id = get_location_from_phone_number(to_number)
    
    # Store call context with location
    conversation_context[call_sid] = {
        'location_id': location_id,
        'phone_number': to_number,
        'messages': []
    }
```

### **3. AI Context per Shop**

```python
# Get shop-specific knowledge
location_context = await knowledge_service.get_ai_context_for_location(location_id)

# AI responses customized per shop
system_msg = f"""
You are a friendly assistant for {business_name}.
Services: {', '.join(service_names)}
Staff: {', '.join(staff_names)}
...
"""
```

### **4. WebSocket Data Broadcasting**

```python
# Backend sends location-specific data
@app.websocket("/ops")
async def ops_metrics_ws(ws: WebSocket):
    snapshot = _compute_ops_snapshot()  # Includes location data
    await ws.send_json({
        "type": "metrics", 
        "data": snapshot
    })
    
# Frontend receives and displays per-shop data
useWebSocket(wsUrl, {
    onMessage: (msg) => {
        if (msg.type === 'metrics') {
            // Update dashboard with location-specific data
            setMetrics(msg.data)
        }
    }
})
```

## 🏪 **Shop Setup Process**

### **Step 1: Setup New Shop**
```bash
curl -X POST "https://your-app.herokuapp.com/shop/setup" \
  -H "Content-Type: application/json" \
  -d '{
    "location_id": 2,
    "phone_number": "+1234567890",
    "website_url": "https://beautysalon2.com",
    "business_name": "Beauty Salon Downtown"
  }'
```

This will:
1. Scrape website data
2. Store in Supabase `salon_static_data` table
3. Update phone number mapping
4. Create location-specific knowledge base

### **Step 2: Update Environment**
```bash
# Add to your environment variables
PHONE_TO_LOCATION_MAP='{"+18084826296": 1, "+1234567890": 2}'
```

### **Step 3: Verify Integration**
```bash
# Check shop configuration
curl "https://your-app.herokuapp.com/shop/2/config"

# List all shops
curl "https://your-app.herokuapp.com/shops"
```

## 📱 **Frontend Integration**

### **Dashboard Views per Shop**

The frontend automatically displays shop-specific data:

```typescript
// Frontend receives WebSocket data
interface MetricsSnapshot {
  location_id: number;
  business_name: string;
  recentCalls: RecentCall[];
  activeBookings: Booking[];
  services: Service[];
  professionals: Professional[];
}

// Dashboard updates in real-time
function SalonDashboard() {
  const [metrics, setMetrics] = useState<MetricsSnapshot>()
  
  useWebSocket(wsUrl, {
    onMessage: (msg) => {
      if (msg.type === 'metrics') {
        setMetrics(msg.data)  // Shop-specific data
      }
    }
  })
  
  return (
    <div>
      <h1>{metrics?.business_name}</h1>
      <ServicesList services={metrics?.services} />
      <CallsList calls={metrics?.recentCalls} />
    </div>
  )
}
```

### **Multi-Shop Dashboard**

For managing multiple shops:

```typescript
// Shop selector component
function ShopSelector() {
  const [shops, setShops] = useState([])
  
  useEffect(() => {
    fetch('/shops')
      .then(res => res.json())
      .then(data => setShops(data.shops))
  }, [])
  
  return (
    <select onChange={(e) => selectShop(e.target.value)}>
      {shops.map(shop => (
        <option key={shop.location_id} value={shop.location_id}>
          {shop.business_name} - {shop.phone_number}
        </option>
      ))}
    </select>
  )
}
```

## 📊 **Database Schema Integration**

### **Existing Supabase Tables**
```sql
-- Core tables (already exists)
profiles (salons)
services 
professionals
bookings
customer_interactions

-- New tables for shop customization
salon_static_data (shop knowledge)
scraped_services (website data)
scraped_professionals (staff data)
salon_info (shop details)
```

### **Data Relationships**
```sql
-- Each shop has its own data
salon_static_data.key = 'location_1', 'location_2'...
scraped_services.salon_id → profiles.id
scraped_professionals.salon_id → profiles.id
salon_info.salon_id → profiles.id
```

## 🔄 **Real-time Updates**

### **Call Events → Database → Frontend**

1. **Call Starts**
   ```python
   # Phone service detects location
   location_id = get_location_from_phone_number(to_number)
   
   # Store call with location context
   await supabase.table('customer_interactions').insert({
       'salon_id': location_id,
       'phone_number': caller_number,
       'call_sid': call_sid
   })
   ```

2. **AI Response Generated**
   ```python
   # Use location-specific knowledge
   knowledge = await knowledge_service.get_location_knowledge(location_id)
   ai_response = generate_response(prompt, knowledge)
   ```

3. **Frontend Updates**
   ```python
   # Broadcast to WebSocket clients
   await broadcast_update({
       'type': 'transcript',
       'data': {
           'location_id': location_id,
           'call_sid': call_sid,
           'text': ai_response
       }
   })
   ```

4. **Dashboard Displays**
   ```typescript
   // Frontend receives and displays
   onMessage: (msg) => {
     if (msg.type === 'transcript') {
       setTranscripts(prev => [...prev, msg.data])
     }
   }
   ```

## 🎯 **Benefits of Integration**

### **For Shop Owners**
- **Shop-Specific Dashboard**: Each location has its own view
- **Real-time Monitoring**: Live call tracking per shop
- **Custom Knowledge**: AI knows each shop's services and staff
- **Booking Management**: Location-specific appointments

### **For Operators**
- **Multi-Shop View**: Monitor all locations from one dashboard
- **Location Context**: Know which shop is being called
- **Shop-Specific Actions**: Handle calls with location knowledge
- **Unified Data**: All shops in one Supabase database

### **For Developers**
- **Scalable Architecture**: Add unlimited shops
- **Unified Backend**: Single Supabase database
- **Real-time Updates**: WebSocket integration
- **Easy Management**: Simple API endpoints

## 🚀 **Scaling Considerations**

### **Database Performance**
```sql
-- Indexes for performance
CREATE INDEX idx_salon_static_data_key ON salon_static_data(key);
CREATE INDEX idx_scraped_services_salon_id ON scraped_services(salon_id);
CREATE INDEX idx_customer_interactions_salon_id ON customer_interactions(salon_id);
```

### **WebSocket Efficiency**
```python
# Location-specific broadcasting
async def broadcast_to_location(location_id: int, message: dict):
    for client in location_clients.get(location_id, []):
        await client.send_json(message)
```

### **Caching Strategy**
```python
# Pre-load shop knowledge at startup
for location_id in all_locations:
    knowledge = await load_location_knowledge(location_id)
    knowledge_cache[location_id] = knowledge
```

## 📈 **Next Steps**

1. **Deploy Shop Setup**: Use `/shop/setup` endpoint for each location
2. **Update Environment**: Set `PHONE_TO_LOCATION_MAP` 
3. **Test Integration**: Verify calls route to correct shops
4. **Monitor Dashboard**: Check real-time updates per shop
5. **Scale**: Add more locations as needed

The system is now fully integrated with Supabase and supports unlimited shops with real-time frontend updates!
