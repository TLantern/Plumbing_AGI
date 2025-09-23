-- Insert sample services for the authenticated user
INSERT INTO public.services (salon_id, name, average_price_cents, is_active) VALUES
(auth.uid(), 'Haircut & Style', 8500, true),
(auth.uid(), 'Hair Color', 15000, true),
(auth.uid(), 'Blowout', 6500, true),
(auth.uid(), 'Highlights', 18000, true),
(auth.uid(), 'Manicure', 4500, true),
(auth.uid(), 'Pedicure', 5500, true);

-- Insert sample call records for the last 30 days
INSERT INTO public.calls (salon_id, timestamp, caller_name_masked, caller_phone_masked, intent, outcome, duration_seconds, sentiment, call_type, hour_of_day) VALUES
-- Recent calls (last 7 days) - using 'up' instead of 'positive'
(auth.uid(), NOW() - INTERVAL '1 day', 'Sarah M.', '***-***-2345', 'Book appointment', 'booked', 180, 'up', 'answered', 10),
(auth.uid(), NOW() - INTERVAL '1 day', 'Jennifer K.', '***-***-6789', 'Reschedule', 'transferred', 95, 'up', 'answered', 14),
(auth.uid(), NOW() - INTERVAL '2 days', 'Maria L.', '***-***-3456', 'Pricing inquiry', 'booked', 240, 'up', 'answered', 9),
(auth.uid(), NOW() - INTERVAL '2 days', 'Unknown', '***-***-9012', 'General inquiry', 'voicemail', 0, 'neutral', 'missed', 16),
(auth.uid(), NOW() - INTERVAL '3 days', 'Ashley R.', '***-***-4567', 'Book color service', 'booked', 320, 'up', 'answered', 11),
(auth.uid(), NOW() - INTERVAL '3 days', 'Lisa W.', '***-***-7890', 'Appointment confirmation', 'transferred', 45, 'up', 'answered', 13),
(auth.uid(), NOW() - INTERVAL '4 days', 'Rachel S.', '***-***-5678', 'Book highlights', 'booked', 280, 'up', 'answered', 10),
(auth.uid(), NOW() - INTERVAL '5 days', 'Michelle D.', '***-***-8901', 'Cancel appointment', 'transferred', 65, 'neutral', 'answered', 15),
(auth.uid(), NOW() - INTERVAL '6 days', 'Amanda P.', '***-***-6789', 'Book manicure', 'booked', 150, 'up', 'answered', 12),
(auth.uid(), NOW() - INTERVAL '7 days', 'Stephanie T.', '***-***-0123', 'Pricing for pedicure', 'booked', 190, 'up', 'answered', 14),

-- Older calls (8-30 days ago)
(auth.uid(), NOW() - INTERVAL '8 days', 'Christina H.', '***-***-1234', 'Book blowout', 'booked', 160, 'up', 'answered', 9),
(auth.uid(), NOW() - INTERVAL '10 days', 'Nicole B.', '***-***-2345', 'Reschedule color', 'transferred', 85, 'up', 'answered', 11),
(auth.uid(), NOW() - INTERVAL '12 days', 'Kimberly J.', '***-***-3456', 'Book cut and style', 'booked', 200, 'up', 'answered', 10),
(auth.uid(), NOW() - INTERVAL '15 days', 'Unknown', '***-***-4567', 'After hours inquiry', 'voicemail', 0, 'neutral', 'after_hours', 19),
(auth.uid(), NOW() - INTERVAL '18 days', 'Danielle F.', '***-***-5678', 'Book highlights', 'booked', 300, 'up', 'answered', 13),
(auth.uid(), NOW() - INTERVAL '20 days', 'Melissa G.', '***-***-6789', 'General pricing', 'transferred', 120, 'up', 'answered', 12),
(auth.uid(), NOW() - INTERVAL '22 days', 'Heather M.', '***-***-7890', 'Book multiple services', 'booked', 380, 'up', 'answered', 14),
(auth.uid(), NOW() - INTERVAL '25 days', 'Unknown', '***-***-8901', 'Missed call', 'voicemail', 0, 'neutral', 'missed', 17),
(auth.uid(), NOW() - INTERVAL '28 days', 'Brittany C.', '***-***-9012', 'Book manicure/pedicure', 'booked', 220, 'up', 'answered', 11),
(auth.uid(), NOW() - INTERVAL '30 days', 'Samantha R.', '***-***-0123', 'Consultation', 'booked', 240, 'up', 'answered', 10);

-- Create sample appointments linked to booked calls
INSERT INTO public.appointments (salon_id, service_id, appointment_date, estimated_revenue_cents, status) 
SELECT 
    auth.uid() as salon_id,
    s.id as service_id,
    c.timestamp + INTERVAL '2 days' as appointment_date,
    s.average_price_cents as estimated_revenue_cents,
    CASE 
        WHEN c.timestamp < NOW() - INTERVAL '1 day' THEN 'completed'
        ELSE 'scheduled'
    END as status
FROM calls c
CROSS JOIN LATERAL (
    SELECT id, average_price_cents FROM services 
    WHERE salon_id = auth.uid() 
    ORDER BY RANDOM() 
    LIMIT 1
) s
WHERE c.salon_id = auth.uid() 
    AND c.outcome = 'booked'
    AND c.timestamp > NOW() - INTERVAL '30 days';