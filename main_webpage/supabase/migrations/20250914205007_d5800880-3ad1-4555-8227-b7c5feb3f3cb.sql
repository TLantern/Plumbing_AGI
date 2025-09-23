-- Fix infinite recursion in user_roles RLS policy
-- Drop the problematic policy that causes recursion
DROP POLICY IF EXISTS "Admins can view all roles" ON public.user_roles;

-- Create a new policy using the security definer function to avoid recursion
CREATE POLICY "Admins can view all roles"
ON public.user_roles 
FOR SELECT 
USING (public.has_role(auth.uid(), 'admin'));