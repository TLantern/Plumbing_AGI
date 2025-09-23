-- Fix Security Definer Views by recreating them without SECURITY DEFINER and adding RLS

-- Drop existing views
DROP VIEW IF EXISTS public.recent_calls_view;
DROP VIEW IF EXISTS public.revenue_by_service_view;

-- Recreate recent_calls_view without SECURITY DEFINER
CREATE VIEW public.recent_calls_view AS
SELECT 
    id,
    timestamp,
    caller_name_masked,
    intent,
    outcome,
    duration_seconds,
    sentiment,
    salon_id
FROM calls c
WHERE timestamp >= (now() - '7 days'::interval)
ORDER BY timestamp DESC;

-- Recreate revenue_by_service_view without SECURITY DEFINER
CREATE VIEW public.revenue_by_service_view AS
SELECT 
    s.name AS service,
    count(a.*) AS appointment_count,
    sum(a.estimated_revenue_cents) AS revenue_cents,
    s.salon_id
FROM services s
LEFT JOIN appointments a ON (
    s.id = a.service_id 
    AND a.status = ANY (ARRAY['scheduled'::text, 'completed'::text]) 
    AND a.created_at >= (now() - '30 days'::interval)
)
GROUP BY s.id, s.name, s.salon_id
HAVING count(a.*) > 0
ORDER BY sum(a.estimated_revenue_cents) DESC;

-- Enable RLS on both views
ALTER VIEW public.recent_calls_view SET (security_invoker = true);
ALTER VIEW public.revenue_by_service_view SET (security_invoker = true);

-- Add RLS policies for recent_calls_view
CREATE POLICY "Users can view own recent calls" 
ON public.recent_calls_view 
FOR SELECT 
USING (salon_id = auth.uid());

-- Add RLS policies for revenue_by_service_view  
CREATE POLICY "Users can view own revenue by service"
ON public.revenue_by_service_view
FOR SELECT
USING (salon_id = auth.uid());