-- Add RLS policies for database views to ensure proper access control

-- Enable RLS on views (these should inherit from the underlying tables, but let's be explicit)
ALTER TABLE recent_calls_view ENABLE ROW LEVEL SECURITY;
ALTER TABLE revenue_by_service_view ENABLE ROW LEVEL SECURITY;

-- Add RLS policy for recent_calls_view
CREATE POLICY "Users can view their own recent calls"
ON recent_calls_view
FOR SELECT
USING (salon_id = auth.uid());

-- Add RLS policy for revenue_by_service_view  
CREATE POLICY "Users can view their own revenue by service"
ON revenue_by_service_view
FOR SELECT
USING (salon_id = auth.uid());