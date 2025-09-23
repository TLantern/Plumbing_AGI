-- Fix remaining function search path issues for security hardening
CREATE OR REPLACE FUNCTION public.extract_call_hour()
 RETURNS trigger
 LANGUAGE plpgsql
 STABLE
 SET search_path = 'public'
AS $function$
BEGIN
  NEW.hour_of_day = EXTRACT(HOUR FROM NEW.timestamp);
  RETURN NEW;
END;
$function$;

CREATE OR REPLACE FUNCTION public.handle_new_user()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path = 'public'
AS $function$
BEGIN
  INSERT INTO public.profiles (id, salon_name, phone, timezone)
  VALUES (
    NEW.id, 
    COALESCE(NEW.raw_user_meta_data->>'salon_name', 'My Salon'),
    COALESCE(NEW.raw_user_meta_data->>'phone', NULL),
    COALESCE(NEW.raw_user_meta_data->>'timezone', 'America/New_York')
  );
  RETURN NEW;
END;
$function$;

CREATE OR REPLACE FUNCTION public.update_updated_at_column()
 RETURNS trigger
 LANGUAGE plpgsql
 STABLE
 SET search_path = 'public'
AS $function$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$function$;