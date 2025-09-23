-- Fix function search path issues by setting search_path on all functions that need it
CREATE OR REPLACE FUNCTION public.get_salons_basic_info()
RETURNS TABLE(
    salon_id UUID,
    salon_name TEXT,
    timezone TEXT,
    created_at TIMESTAMP WITH TIME ZONE,
    total_calls BIGINT,
    total_appointments BIGINT,
    total_revenue_cents BIGINT
)
LANGUAGE SQL
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
    SELECT 
        p.id as salon_id,
        p.salon_name,
        p.timezone,
        p.created_at,
        COALESCE(call_stats.total_calls, 0) as total_calls,
        COALESCE(appt_stats.total_appointments, 0) as total_appointments,
        COALESCE(appt_stats.total_revenue_cents, 0) as total_revenue_cents
    FROM profiles p
    LEFT JOIN (
        SELECT salon_id, COUNT(*) as total_calls
        FROM calls
        GROUP BY salon_id
    ) call_stats ON p.id = call_stats.salon_id
    LEFT JOIN (
        SELECT salon_id, COUNT(*) as total_appointments, SUM(estimated_revenue_cents) as total_revenue_cents
        FROM appointments
        WHERE status IN ('scheduled', 'completed')
        GROUP BY salon_id
    ) appt_stats ON p.id = appt_stats.salon_id
    WHERE public.has_role(auth.uid(), 'admin')
    ORDER BY p.created_at DESC;
$$;

-- Fix the mask_phone_number function to have proper search_path
CREATE OR REPLACE FUNCTION public.mask_phone_number(phone_number TEXT)
RETURNS TEXT
LANGUAGE SQL
IMMUTABLE
SET search_path = public
AS $$
    SELECT CASE 
        WHEN phone_number IS NULL OR LENGTH(phone_number) < 4 THEN phone_number
        ELSE CONCAT(
            SUBSTRING(phone_number FROM 1 FOR 3),
            REPEAT('*', GREATEST(0, LENGTH(phone_number) - 6)),
            SUBSTRING(phone_number FROM LENGTH(phone_number) - 2)
        )
    END;
$$;