-- Enable RLS on tables that don't have it enabled
ALTER TABLE public.salon_info ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.salon_static_data ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.scraped_professionals ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.scraped_services ENABLE ROW LEVEL SECURITY;

-- Create RLS policies for salon_info
-- Allow users to view and manage salon info for their own salon
CREATE POLICY "Users can view salon info for their salon" 
ON public.salon_info 
FOR SELECT 
USING (salon_id = auth.uid());

CREATE POLICY "Users can insert salon info for their salon" 
ON public.salon_info 
FOR INSERT 
WITH CHECK (salon_id = auth.uid());

CREATE POLICY "Users can update salon info for their salon" 
ON public.salon_info 
FOR UPDATE 
USING (salon_id = auth.uid());

CREATE POLICY "Users can delete salon info for their salon" 
ON public.salon_info 
FOR DELETE 
USING (salon_id = auth.uid());

-- Create RLS policies for salon_static_data
-- This table appears to contain reference data, allow read access to authenticated users
-- but only allow system/admin operations for modifications
CREATE POLICY "Authenticated users can view salon static data" 
ON public.salon_static_data 
FOR SELECT 
USING (auth.role() = 'authenticated');

-- Create RLS policies for scraped_professionals
-- Allow users to view and manage professionals for their own salon
CREATE POLICY "Users can view professionals for their salon" 
ON public.scraped_professionals 
FOR SELECT 
USING (salon_id = auth.uid());

CREATE POLICY "Users can insert professionals for their salon" 
ON public.scraped_professionals 
FOR INSERT 
WITH CHECK (salon_id = auth.uid());

CREATE POLICY "Users can update professionals for their salon" 
ON public.scraped_professionals 
FOR UPDATE 
USING (salon_id = auth.uid());

CREATE POLICY "Users can delete professionals for their salon" 
ON public.scraped_professionals 
FOR DELETE 
USING (salon_id = auth.uid());

-- Create RLS policies for scraped_services
-- Allow users to view and manage scraped services for their own salon
CREATE POLICY "Users can view scraped services for their salon" 
ON public.scraped_services 
FOR SELECT 
USING (salon_id = auth.uid());

CREATE POLICY "Users can insert scraped services for their salon" 
ON public.scraped_services 
FOR INSERT 
WITH CHECK (salon_id = auth.uid());

CREATE POLICY "Users can update scraped services for their salon" 
ON public.scraped_services 
FOR UPDATE 
USING (salon_id = auth.uid());

CREATE POLICY "Users can delete scraped services for their salon" 
ON public.scraped_services 
FOR DELETE 
USING (salon_id = auth.uid());

-- Fix the function search path warning by updating existing functions
-- Update the function that was showing search path issues
CREATE OR REPLACE FUNCTION public.get_salon_kpis(p_salon_id uuid, p_days integer DEFAULT 30)
 RETURNS TABLE(revenue_recovered_cents bigint, calls_answered integer, appointments_booked integer, conversion_rate numeric)
 LANGUAGE plpgsql
 SECURITY DEFINER
 STABLE
 SET search_path = 'public'
AS $function$
BEGIN
  RETURN QUERY
  WITH date_range AS (
    SELECT (NOW() - INTERVAL '1 day' * p_days)::DATE as start_date,
           NOW()::DATE as end_date
  ),
  call_stats AS (
    SELECT 
      COUNT(*) FILTER (WHERE outcome = 'booked') as booked_calls,
      COUNT(*) FILTER (WHERE call_type = 'answered') as answered_calls,
      COUNT(*) as total_calls
    FROM calls c, date_range dr
    WHERE c.salon_id = p_salon_id 
      AND c.timestamp::DATE BETWEEN dr.start_date AND dr.end_date
  ),
  revenue_stats AS (
    SELECT COALESCE(SUM(estimated_revenue_cents), 0) as total_revenue
    FROM appointments a, date_range dr
    WHERE a.salon_id = p_salon_id 
      AND a.created_at::DATE BETWEEN dr.start_date AND dr.end_date
      AND a.status IN ('scheduled', 'completed')
  )
  SELECT 
    rs.total_revenue,
    cs.answered_calls,
    cs.booked_calls,
    CASE 
      WHEN cs.total_calls > 0 THEN (cs.booked_calls::DECIMAL / cs.total_calls::DECIMAL)
      ELSE 0::DECIMAL
    END
  FROM call_stats cs, revenue_stats rs;
END;
$function$;

CREATE OR REPLACE FUNCTION public.get_calls_timeseries(p_salon_id uuid, p_days integer DEFAULT 30)
 RETURNS TABLE(date date, answered integer, missed integer, after_hours_captured integer)
 LANGUAGE plpgsql
 SECURITY DEFINER
 STABLE
 SET search_path = 'public'
AS $function$
BEGIN
  RETURN QUERY
  WITH date_range AS (
    SELECT generate_series(
      (NOW() - INTERVAL '1 day' * p_days)::DATE,
      NOW()::DATE,
      '1 day'::INTERVAL
    )::DATE as date
  )
  SELECT 
    dr.date,
    COALESCE(COUNT(*) FILTER (WHERE c.call_type = 'answered'), 0)::INTEGER,
    COALESCE(COUNT(*) FILTER (WHERE c.call_type = 'missed'), 0)::INTEGER,
    COALESCE(COUNT(*) FILTER (WHERE c.call_type = 'after_hours'), 0)::INTEGER
  FROM date_range dr
  LEFT JOIN calls c ON c.salon_id = p_salon_id 
    AND c.timestamp::DATE = dr.date
  GROUP BY dr.date
  ORDER BY dr.date;
END;
$function$;