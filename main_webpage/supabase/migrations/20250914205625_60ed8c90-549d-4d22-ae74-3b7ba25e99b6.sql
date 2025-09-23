-- Fix ambiguous column reference in get_all_salons_overview function
CREATE OR REPLACE FUNCTION public.get_all_salons_overview()
RETURNS TABLE(salon_id uuid, salon_name text, phone text, timezone text, created_at timestamp with time zone, total_calls bigint, total_appointments bigint, total_revenue_cents bigint)
LANGUAGE plpgsql
STABLE SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    -- Only allow admin access
    IF NOT public.has_role(auth.uid(), 'admin') THEN
        RAISE EXCEPTION 'Access denied. Admin privileges required.';
    END IF;
    
    -- Try to log sensitive data access, but don't fail if we can't
    BEGIN
        PERFORM public.log_sensitive_access(
            'VIEW_ALL_SALONS',
            'profiles',
            NULL,
            ARRAY['phone', 'salon_name']
        );
    EXCEPTION 
        WHEN OTHERS THEN
            -- Ignore logging errors (e.g., read-only transaction)
            NULL;
    END;
    
    RETURN QUERY
    SELECT 
        p.id as salon_id,
        p.salon_name,
        public.mask_phone_number(p.phone) as phone, -- Mask phone numbers
        p.timezone,
        p.created_at,
        COALESCE(call_stats.total_calls, 0) as total_calls,
        COALESCE(appt_stats.total_appointments, 0) as total_appointments,
        COALESCE(appt_stats.total_revenue_cents, 0) as total_revenue_cents
    FROM profiles p
    LEFT JOIN (
        SELECT c.salon_id, COUNT(*) as total_calls
        FROM calls c
        GROUP BY c.salon_id
    ) call_stats ON p.id = call_stats.salon_id
    LEFT JOIN (
        SELECT a.salon_id, COUNT(*) as total_appointments, SUM(a.estimated_revenue_cents) as total_revenue_cents
        FROM appointments a
        WHERE a.status IN ('scheduled', 'completed')
        GROUP BY a.salon_id
    ) appt_stats ON p.id = appt_stats.salon_id
    ORDER BY p.created_at DESC;
END;
$$;