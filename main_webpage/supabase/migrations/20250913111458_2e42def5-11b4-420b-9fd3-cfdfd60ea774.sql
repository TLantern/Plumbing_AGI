-- Enable RLS on the business analytics views that are exposing sensitive data
ALTER TABLE public.recent_calls_view ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.revenue_by_service_view ENABLE ROW LEVEL SECURITY;

-- Create RLS policies for recent_calls_view
-- Only allow salon owners to see their own call data
CREATE POLICY "Salon owners can view their own recent calls" 
ON public.recent_calls_view 
FOR SELECT 
USING (salon_id = auth.uid());

-- Create RLS policies for revenue_by_service_view  
-- Only allow salon owners to see their own revenue data
CREATE POLICY "Salon owners can view their own revenue by service" 
ON public.revenue_by_service_view 
FOR SELECT 
USING (salon_id = auth.uid());