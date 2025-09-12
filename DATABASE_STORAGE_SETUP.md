# Database Storage for Salon Data

The salon phone service uses PostgreSQL database storage for all static data. This provides persistent, reliable storage that integrates seamlessly with Heroku's PostgreSQL addon.

## 🗄️ **Database Storage Benefits**

- **Integrated**: Uses existing PostgreSQL database
- **Persistent**: Data survives all dyno restarts
- **Reliable**: PostgreSQL's ACID compliance
- **Efficient**: JSONB for fast JSON operations
- **Scalable**: Handles multiple dyno instances
- **No Setup**: Works automatically with Heroku PostgreSQL

## 🔧 **How It Works**

### **Storage Table**
```sql
CREATE TABLE salon_static_data (
    key VARCHAR(255) PRIMARY KEY,
    data JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### **Data Structure**
- **Key**: `location_1`, `location_2`, etc.
- **Data**: Complete JSON structure with services, professionals, FAQ
- **Timestamps**: Track when data was created/updated

## 🚀 **Setup Process**

### **1. Heroku PostgreSQL**
```bash
# Add PostgreSQL addon (automatically sets DATABASE_URL)
heroku addons:create heroku-postgresql:mini
```

### **2. Deploy Service**
```bash
# Deploy with database initialization
git push heroku main
# The release process automatically creates tables
```

### **3. Setup Location Data**
```bash
# One-time setup per location
curl -X POST "https://your-app.herokuapp.com/setup-location/1?website_url=https://salon-website.com"
```

## 📊 **Data Flow**

1. **Scraping**: Website scraper extracts salon data
2. **Storage**: Data stored in PostgreSQL JSONB column
3. **Caching**: Service loads all data into memory at startup
4. **Serving**: Zero-delay responses using cached data

## 🛠️ **Management**

### **Check Status**
```bash
# List all locations
curl "https://your-app.herokuapp.com/locations"

# Check specific location
curl "https://your-app.herokuapp.com/location/1/status"
```

### **Update Data**
```bash
# Update existing location
curl -X POST "https://your-app.herokuapp.com/setup-location/1?website_url=https://updated-salon.com"
```

## 🔍 **Database Queries**

### **View All Data**
```sql
SELECT key, created_at, updated_at 
FROM salon_static_data 
ORDER BY updated_at DESC;
```

### **View Location Data**
```sql
SELECT data->'business_info'->>'name' as business_name,
       data->'stats'->>'services_count' as services,
       data->'stats'->>'professionals_count' as professionals
FROM salon_static_data 
WHERE key = 'location_1';
```

### **Check Data Age**
```sql
SELECT key, 
       updated_at,
       NOW() - updated_at as age
FROM salon_static_data;
```

## 🚨 **Troubleshooting**

### **Database Connection**
```bash
# Check database status
heroku pg:info

# Connect to database
heroku pg:psql
```

### **Storage Issues**
```bash
# Check if table exists
heroku pg:psql -c "\dt salon_static_data"

# View data
heroku pg:psql -c "SELECT key, created_at FROM salon_static_data;"
```

### **Data Recovery**
All salon data is stored in PostgreSQL and can be:
- Backed up with `heroku pg:backups:capture`
- Exported with `heroku pg:psql`
- Restored from backups

## 📈 **Performance**

- **Startup**: ~2-3 seconds to load all location data
- **Runtime**: Zero latency (all data in memory)
- **Storage**: Efficient JSONB compression
- **Queries**: Fast key-based lookups

## 🔒 **Security**

- **Encrypted**: Heroku PostgreSQL uses encryption at rest
- **Access**: Only your app can access the database
- **Backups**: Automatic daily backups
- **Compliance**: SOC 2 Type II certified

This database storage approach provides enterprise-grade reliability with zero additional setup! 🎯
