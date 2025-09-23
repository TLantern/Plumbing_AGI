-- Drop the existing insecure views
DROP VIEW IF EXISTS public.recent_calls_view;
DROP VIEW IF EXISTS public.revenue_by_service_view;

-- Recreate recent_calls_view as a security definer function that automatically filters by user
CREATE OR REPLACE FUNCTION public.get_recent_calls_view()
RETURNS TABLE (
    id uuid,
    "timestamp" timestamp with time zone,
    duration_seconds integer,
    salon_id uuid,
    outcome text,
    sentiment text,
    caller_name_masked text,
    intent text
)
LANGUAGE sql
SECURITY DEFINER
STABLE
SET search_path = 'public'
AS $$
    SELECT 
        c.id,
        c."timestamp",
        c.duration_seconds,
        c.salon_id,
        c.outcome,
        c.sentiment,
        c.caller_name_masked,
        c.intent
    FROM calls c 
    WHERE c.salon_id = auth.uid()
    ORDER BY c."timestamp" DESC
    LIMIT 50;
$$;

-- Recreate revenue_by_service_view as a security definer function that automatically filters by user
CREATE OR REPLACE FUNCTION public.get_revenue_by_service_view()
RETURNS TABLE (
    salon_id uuid,
    service text,
    revenue_cents bigint,
    appointment_count bigint
)
LANGUAGE sql
SECURITY DEFINER
STABLE
SET search_path = 'public'
AS $$
    SELECT 
        a.salon_id,
        s.name as service,
        COALESCE(SUM(a.estimated_revenue_cents), 0) as revenue_cents,
        COUNT(a.id) as appointment_count
    FROM appointments a
    JOIN services s ON a.service_id = s.id
    WHERE a.salon_id = auth.uid()
      AND a.status IN ('scheduled', 'completed')
    GROUP BY a.salon_id, s.name
    ORDER BY revenue_cents DESC;
$$;

-- Grant execute permissions to authenticated users
GRANT EXECUTE ON FUNCTION public.get_recent_calls_view() TO authenticated;
GRANT EXECUTE ON FUNCTION public.get_revenue_by_service_view() TO authenticated;