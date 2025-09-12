-- Create missing tables for website scraper and knowledge storage integration

-- 1. Salon Static Data (for knowledge storage)
CREATE TABLE IF NOT EXISTS salon_static_data (
    key VARCHAR(255) PRIMARY KEY,
    data JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. Scraped Services (detailed service info from websites)
CREATE TABLE IF NOT EXISTS scraped_services (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    salon_id UUID REFERENCES profiles(id) ON DELETE CASCADE,
    service_name VARCHAR(255) NOT NULL,
    description TEXT,
    price VARCHAR(100),
    duration VARCHAR(100),
    category VARCHAR(100),
    raw_data JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. Scraped Professionals (staff/tech info from websites)
CREATE TABLE IF NOT EXISTS scraped_professionals (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    salon_id UUID REFERENCES profiles(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    title VARCHAR(255),
    bio TEXT,
    specialties TEXT[],
    experience_years INTEGER,
    certifications TEXT[],
    image_url TEXT,
    raw_data JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 4. Salon Info (detailed salon information from websites)
CREATE TABLE IF NOT EXISTS salon_info (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    salon_id UUID REFERENCES profiles(id) ON DELETE CASCADE,
    business_name VARCHAR(255),
    website_url TEXT,
    address TEXT,
    phone VARCHAR(50),
    hours JSONB,
    faq_items JSONB,
    scraped_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_salon_static_data_key ON salon_static_data(key);
CREATE INDEX IF NOT EXISTS idx_scraped_services_salon_id ON scraped_services(salon_id);
CREATE INDEX IF NOT EXISTS idx_scraped_services_category ON scraped_services(category);
CREATE INDEX IF NOT EXISTS idx_scraped_professionals_salon_id ON scraped_professionals(salon_id);
CREATE INDEX IF NOT EXISTS idx_salon_info_salon_id ON salon_info(salon_id);

-- Create updated_at trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Add updated_at triggers
CREATE TRIGGER update_salon_static_data_updated_at 
    BEFORE UPDATE ON salon_static_data 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_scraped_services_updated_at 
    BEFORE UPDATE ON scraped_services 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_scraped_professionals_updated_at 
    BEFORE UPDATE ON scraped_professionals 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_salon_info_updated_at 
    BEFORE UPDATE ON salon_info 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Grant permissions (adjust as needed for your setup)
-- ALTER TABLE salon_static_data ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE scraped_services ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE scraped_professionals ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE salon_info ENABLE ROW LEVEL SECURITY;
