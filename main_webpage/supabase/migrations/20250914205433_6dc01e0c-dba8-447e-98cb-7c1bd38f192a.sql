-- Fix the get_all_salons_overview function to handle read-only transactions
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
    ORDER BY p.created_at DESC;
END;
$$;

-- Also fix the get_profile_safe function similarly
CREATE OR REPLACE FUNCTION public.get_profile_safe(profile_id uuid)
RETURNS TABLE(id uuid, salon_name text, phone text, timezone text, created_at timestamp with time zone)
LANGUAGE plpgsql
STABLE SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    -- If viewing own profile, return full data
    IF profile_id = auth.uid() THEN
        RETURN QUERY
        SELECT p.id, p.salon_name, p.phone, p.timezone, p.created_at
        FROM profiles p
        WHERE p.id = profile_id;
    -- If admin viewing other profile, mask phone and try to log access
    ELSIF public.has_role(auth.uid(), 'admin') THEN
        -- Try to log access, but don't fail if we can't
        BEGIN
            PERFORM public.log_sensitive_access(
                'ADMIN_VIEW_PROFILE',
                'profiles',
                profile_id::TEXT,
                ARRAY['phone']
            );
        EXCEPTION 
            WHEN OTHERS THEN
                -- Ignore logging errors (e.g., read-only transaction)
                NULL;
        END;
        
        RETURN QUERY
        SELECT 
            p.id, 
            p.salon_name, 
            public.mask_phone_number(p.phone) as phone,
            p.timezone, 
            p.created_at
        FROM profiles p
        WHERE p.id = profile_id;
    ELSE
        -- No access for regular users to other profiles
        RAISE EXCEPTION 'Access denied';
    END IF;
END;
$$;