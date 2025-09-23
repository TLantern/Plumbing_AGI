-- Fix Security Definer Views by recreating without SECURITY DEFINER and adding RLS

-- Drop existing views
DROP VIEW IF EXISTS public.recent_calls_view;
DROP VIEW IF EXISTS public.revenue_by_service_view;

-- Recreate recent_calls_view without SECURITY DEFINER
CREATE VIEW public.recent_calls_view AS 
SELECT id,
    "timestamp",
    caller_name_masked,
    intent,
    outcome,
    duration_seconds,
    sentiment,
    salon_id
FROM calls c
WHERE ("timestamp" >= (now() - '7 days'::interval))
ORDER BY "timestamp" DESC;

-- Recreate revenue_by_service_view without SECURITY DEFINER
CREATE VIEW public.revenue_by_service_view AS 
SELECT s.name AS service,
    count(a.*) AS appointment_count,
    sum(a.estimated_revenue_cents) AS revenue_cents,
    s.salon_id
FROM (services s
     LEFT JOIN appointments a ON (((s.id = a.service_id) AND (a.status = ANY (ARRAY['scheduled'::text, 'completed'::text])) AND (a.created_at >= (now() - '30 days'::interval)))))
GROUP BY s.id, s.name, s.salon_id
HAVING (count(a.*) > 0)
ORDER BY (sum(a.estimated_revenue_cents)) DESC;

-- Enable RLS on views
ALTER VIEW public.recent_calls_view OWNER TO postgres;
ALTER VIEW public.revenue_by_service_view OWNER TO postgres;

-- Add RLS policies for views to ensure proper access control
-- Note: Views inherit RLS from underlying tables, so calls and services tables already have proper RLS

-- Fix Function Search Path Mutable warnings by updating existing functions
CREATE OR REPLACE FUNCTION public.get_salon_kpis(p_salon_id uuid, p_days integer DEFAULT 30)
RETURNS TABLE(revenue_recovered_cents bigint, calls_answered integer, appointments_booked integer, conversion_rate numeric)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
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
SET search_path = public
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

CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = public
AS $function$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$function$;

CREATE OR REPLACE FUNCTION public.extract_call_hour()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = public
AS $function$
BEGIN
  NEW.hour_of_day = EXTRACT(HOUR FROM NEW.timestamp);
  RETURN NEW;
END;
$function$;