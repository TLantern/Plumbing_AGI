-- Create user roles enum
CREATE TYPE public.app_role AS ENUM ('admin', 'salon_owner');

-- Create user_roles table
CREATE TABLE public.user_roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    role app_role NOT NULL DEFAULT 'salon_owner',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    UNIQUE(user_id, role)
);

-- Enable RLS
ALTER TABLE public.user_roles ENABLE ROW LEVEL SECURITY;

-- Create RLS policies for user_roles
CREATE POLICY "Users can view their own roles" 
ON public.user_roles 
FOR SELECT 
USING (auth.uid() = user_id);

CREATE POLICY "Admins can view all roles" 
ON public.user_roles 
FOR SELECT 
USING (
    EXISTS (
        SELECT 1 FROM public.user_roles ur 
        WHERE ur.user_id = auth.uid() 
        AND ur.role = 'admin'
    )
);

-- Create security definer function to check user roles
CREATE OR REPLACE FUNCTION public.has_role(_user_id UUID, _role app_role)
RETURNS BOOLEAN
LANGUAGE SQL
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM public.user_roles
        WHERE user_id = _user_id
        AND role = _role
    )
$$;

-- Create function to get current user role
CREATE OR REPLACE FUNCTION public.get_current_user_role()
RETURNS app_role
LANGUAGE SQL
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
    SELECT role
    FROM public.user_roles
    WHERE user_id = auth.uid()
    LIMIT 1
$$;

-- Admin functions for dashboard
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
LANGUAGE SQL
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
    SELECT 
        p.id as salon_id,
        p.salon_name,
        p.phone,
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
    ORDER BY p.created_at DESC
$$;

-- Function to get platform-wide metrics
CREATE OR REPLACE FUNCTION public.get_platform_metrics()
RETURNS TABLE(
    total_salons BIGINT,
    total_calls BIGINT,
    total_appointments BIGINT,
    total_revenue_cents BIGINT,
    active_salons BIGINT
)
LANGUAGE SQL
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
    SELECT 
        (SELECT COUNT(*) FROM profiles) as total_salons,
        (SELECT COUNT(*) FROM calls) as total_calls,
        (SELECT COUNT(*) FROM appointments WHERE status IN ('scheduled', 'completed')) as total_appointments,
        (SELECT COALESCE(SUM(estimated_revenue_cents), 0) FROM appointments WHERE status IN ('scheduled', 'completed')) as total_revenue_cents,
        (SELECT COUNT(DISTINCT salon_id) FROM calls WHERE timestamp >= NOW() - INTERVAL '30 days') as active_salons
    WHERE public.has_role(auth.uid(), 'admin')
$$;

-- Insert admin role for the specific user (this will be done after they sign up)
-- We'll create a trigger or manual process for this

-- Create trigger for updating timestamps
CREATE TRIGGER update_user_roles_updated_at
    BEFORE UPDATE ON public.user_roles
    FOR EACH ROW
    EXECUTE FUNCTION public.update_updated_at_column();

-- Update RLS policies on existing tables to allow admin access
CREATE POLICY "Admins can view all profiles"
ON public.profiles
FOR SELECT
USING (public.has_role(auth.uid(), 'admin'));

CREATE POLICY "Admins can view all calls"
ON public.calls
FOR SELECT
USING (public.has_role(auth.uid(), 'admin'));

CREATE POLICY "Admins can view all appointments"
ON public.appointments
FOR SELECT
USING (public.has_role(auth.uid(), 'admin'));