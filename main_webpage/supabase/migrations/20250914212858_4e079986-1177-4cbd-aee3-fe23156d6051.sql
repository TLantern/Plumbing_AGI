-- Fix the get_salon_kpis function return type structure
DROP FUNCTION IF EXISTS public.get_salon_kpis(uuid, integer);

CREATE OR REPLACE FUNCTION public.get_salon_kpis(p_salon_id uuid, p_days integer DEFAULT 30)
RETURNS TABLE(
  revenue_recovered_cents bigint, 
  calls_answered bigint, 
  appointments_booked bigint, 
  conversion_rate numeric
)
LANGUAGE plpgsql
STABLE SECURITY DEFINER
SET search_path TO 'public'
AS $$
BEGIN
  RETURN QUERY
  WITH date_range AS (
    SELECT (NOW() - INTERVAL '1 day' * p_days)::DATE as start_date,
           NOW()::DATE as end_date
  ),
  call_stats AS (
    SELECT 
      COUNT(*) FILTER (WHERE c.outcome = 'booked') as booked_calls,
      COUNT(*) FILTER (WHERE c.call_type = 'answered') as answered_calls,
      COUNT(*) as total_calls
    FROM calls c, date_range dr
    WHERE c.salon_id = p_salon_id 
      AND c.timestamp::DATE BETWEEN dr.start_date AND dr.end_date
  ),
  revenue_stats AS (
    SELECT COALESCE(SUM(a.estimated_revenue_cents), 0) as total_revenue
    FROM appointments a, date_range dr
    WHERE a.salon_id = p_salon_id 
      AND a.created_at::DATE BETWEEN dr.start_date AND dr.end_date
      AND a.status IN ('scheduled', 'completed')
  )
  SELECT 
    rs.total_revenue::bigint,
    cs.answered_calls::bigint,
    cs.booked_calls::bigint,
    CASE 
      WHEN cs.total_calls > 0 THEN (cs.booked_calls::DECIMAL / cs.total_calls::DECIMAL)
      ELSE 0::DECIMAL
    END as conversion_rate
  FROM call_stats cs, revenue_stats rs;
END;
$$;

-- Also fix the get_calls_timeseries function return types
DROP FUNCTION IF EXISTS public.get_calls_timeseries(uuid, integer);

CREATE OR REPLACE FUNCTION public.get_calls_timeseries(p_salon_id uuid, p_days integer DEFAULT 30)
RETURNS TABLE(
  date date, 
  answered bigint, 
  missed bigint, 
  after_hours_captured bigint
)
LANGUAGE plpgsql
STABLE SECURITY DEFINER
SET search_path TO 'public'
AS $$
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
    COALESCE(COUNT(*) FILTER (WHERE c.call_type = 'answered'), 0)::bigint,
    COALESCE(COUNT(*) FILTER (WHERE c.call_type = 'missed'), 0)::bigint,
    COALESCE(COUNT(*) FILTER (WHERE c.call_type = 'after_hours'), 0)::bigint
  FROM date_range dr
  LEFT JOIN calls c ON c.salon_id = p_salon_id 
    AND c.timestamp::DATE = dr.date
  GROUP BY dr.date
  ORDER BY dr.date;
END;
$$;

-- Add some sample data for testing
INSERT INTO calls (salon_id, timestamp, call_type, outcome, intent, caller_name_masked, duration_seconds, sentiment)
VALUES 
  (auth.uid(), NOW() - INTERVAL '1 day', 'answered', 'booked', 'Haircut appointment', 'J*** D***', 180, 'up'),
  (auth.uid(), NOW() - INTERVAL '2 days', 'answered', 'booked', 'Color treatment', 'M*** S***', 240, 'up'),
  (auth.uid(), NOW() - INTERVAL '3 days', 'missed', 'voicemail', 'General inquiry', 'A*** L***', 0, 'neutral'),
  (auth.uid(), NOW() - INTERVAL '4 days', 'after_hours', 'booked', 'Balayage', 'K*** P***', 300, 'up'),
  (auth.uid(), NOW() - INTERVAL '5 days', 'answered', 'transferred', 'Pricing question', 'R*** T***', 120, 'neutral')
ON CONFLICT DO NOTHING;

INSERT INTO appointments (salon_id, created_at, status, estimated_revenue_cents, appointment_date)
VALUES 
  (auth.uid(), NOW() - INTERVAL '1 day', 'scheduled', 8000, NOW() + INTERVAL '3 days'),
  (auth.uid(), NOW() - INTERVAL '2 days', 'completed', 12000, NOW() - INTERVAL '1 day'),
  (auth.uid(), NOW() - INTERVAL '4 days', 'scheduled', 15000, NOW() + INTERVAL '5 days'),
  (auth.uid(), NOW() - INTERVAL '5 days', 'completed', 6000, NOW() - INTERVAL '3 days')
ON CONFLICT DO NOTHING;

INSERT INTO services (salon_id, name, average_price_cents, is_active)
VALUES 
  (auth.uid(), 'Haircut & Style', 8000, true),
  (auth.uid(), 'Color Treatment', 12000, true),
  (auth.uid(), 'Balayage', 15000, true),
  (auth.uid(), 'Highlights', 10000, true),
  (auth.uid(), 'Deep Conditioning', 6000, true)
ON CONFLICT DO NOTHING;