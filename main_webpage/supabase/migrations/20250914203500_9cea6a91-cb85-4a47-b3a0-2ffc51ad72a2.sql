-- Function to automatically assign admin role to specific email
CREATE OR REPLACE FUNCTION public.assign_admin_role()
RETURNS TRIGGER AS $$
BEGIN
  -- Check if this is the admin email
  IF NEW.email = 'teniowojori@gmail.com' THEN
    INSERT INTO public.user_roles (user_id, role)
    VALUES (NEW.id, 'admin')
    ON CONFLICT (user_id, role) DO NOTHING;
  ELSE
    -- Assign default salon_owner role to other users
    INSERT INTO public.user_roles (user_id, role)
    VALUES (NEW.id, 'salon_owner')
    ON CONFLICT (user_id, role) DO NOTHING;
  END IF;
  
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

-- Create trigger to assign roles on user creation
DROP TRIGGER IF EXISTS assign_user_role_trigger ON auth.users;
CREATE TRIGGER assign_user_role_trigger
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.assign_admin_role();

-- For existing users, if the admin user already exists, assign admin role
DO $$
BEGIN
  -- Check if the admin user exists and assign admin role
  IF EXISTS (SELECT 1 FROM auth.users WHERE email = 'teniowojori@gmail.com') THEN
    INSERT INTO public.user_roles (user_id, role)
    SELECT id, 'admin'
    FROM auth.users 
    WHERE email = 'teniowojori@gmail.com'
    ON CONFLICT (user_id, role) DO NOTHING;
  END IF;
  
  -- Assign salon_owner role to existing users who don't have any role
  INSERT INTO public.user_roles (user_id, role)
  SELECT u.id, 'salon_owner'
  FROM auth.users u
  LEFT JOIN public.user_roles ur ON u.id = ur.user_id
  WHERE ur.user_id IS NULL
  ON CONFLICT (user_id, role) DO NOTHING;
END $$;