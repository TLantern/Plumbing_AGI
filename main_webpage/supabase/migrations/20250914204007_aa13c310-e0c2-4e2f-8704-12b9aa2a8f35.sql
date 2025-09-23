-- Create phone number masking function
CREATE OR REPLACE FUNCTION public.mask_phone_number(phone_number TEXT)
RETURNS TEXT
LANGUAGE SQL
IMMUTABLE
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

-- Create audit log table for sensitive data access
CREATE TABLE public.audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID,
    action TEXT NOT NULL,
    table_name TEXT NOT NULL,
    record_id TEXT,
    sensitive_fields TEXT[],
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- Enable RLS on audit logs
ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;

-- Only admins can view audit logs
CREATE POLICY "Only admins can view audit logs"
ON public.audit_logs
FOR SELECT
USING (public.has_role(auth.uid(), 'admin'));

-- Create function to log sensitive data access
CREATE OR REPLACE FUNCTION public.log_sensitive_access(
    p_action TEXT,
    p_table_name TEXT,
    p_record_id TEXT DEFAULT NULL,
    p_sensitive_fields TEXT[] DEFAULT NULL
)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    INSERT INTO public.audit_logs (
        user_id,
        action,
        table_name,
        record_id,
        sensitive_fields,
        ip_address
    ) VALUES (
        auth.uid(),
        p_action,
        p_table_name,
        p_record_id,
        p_sensitive_fields,
        inet_client_addr()
    );
END;
$$;

-- Update admin function to mask phone numbers and log access
CREATE OR REPLACE FUNCTION public.get_all_salons_overview()
RETURNS TABLE(
    salon_id UUID,
    salon_name TEXT,
    phone TEXT,
    timezone TEXT,
    created_at TIMESTAMP WITH TIME ZONE,
    total_calls BIGINT,
    total_appointments BIGINT,
    total_revenue_cents BIGINT
)
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    -- Only allow admin access
    IF NOT public.has_role(auth.uid(), 'admin') THEN
        RAISE EXCEPTION 'Access denied. Admin privileges required.';
    END IF;
    
    -- Log sensitive data access
    PERFORM public.log_sensitive_access(
        'VIEW_ALL_SALONS',
        'profiles',
        NULL,
        ARRAY['phone', 'salon_name']
    );
    
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

-- Create more restrictive function for basic salon listing (no phone numbers)
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

-- Add more restrictive RLS policy for salon_info to prevent accidental exposure
CREATE POLICY "Prevent cross-salon data access in salon_info"
ON public.salon_info
FOR ALL
USING (
    salon_id = auth.uid() OR 
    public.has_role(auth.uid(), 'admin')
);

-- Update existing RLS policies to be more explicit about phone number access
DROP POLICY IF EXISTS "Admins can view all profiles" ON public.profiles;
CREATE POLICY "Admins can view profiles with logging"
ON public.profiles
FOR SELECT
USING (
    auth.uid() = id OR 
    (public.has_role(auth.uid(), 'admin') AND 
     public.log_sensitive_access('ADMIN_VIEW_PROFILE', 'profiles', id::TEXT, ARRAY['phone']) IS NULL)
);

-- Create function for safe profile viewing (masks sensitive data for non-owners)
CREATE OR REPLACE FUNCTION public.get_profile_safe(profile_id UUID)
RETURNS TABLE(
    id UUID,
    salon_name TEXT,
    phone TEXT,
    timezone TEXT,
    created_at TIMESTAMP WITH TIME ZONE
)
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    -- If viewing own profile, return full data
    IF profile_id = auth.uid() THEN
        RETURN QUERY
        SELECT p.id, p.salon_name, p.phone, p.timezone, p.created_at
        FROM profiles p
        WHERE p.id = profile_id;
    -- If admin viewing other profile, mask phone and log access
    ELSIF public.has_role(auth.uid(), 'admin') THEN
        PERFORM public.log_sensitive_access(
            'ADMIN_VIEW_PROFILE',
            'profiles',
            profile_id::TEXT,
            ARRAY['phone']
        );
        
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