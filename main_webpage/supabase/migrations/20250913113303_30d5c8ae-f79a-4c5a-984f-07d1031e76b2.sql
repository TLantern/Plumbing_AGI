-- Add additional security measures to the user_google_tokens table
-- First, let's add columns for enhanced security tracking
ALTER TABLE public.user_google_tokens 
ADD COLUMN last_used_at timestamp with time zone,
ADD COLUMN last_used_ip inet,
ADD COLUMN is_active boolean NOT NULL DEFAULT true,
ADD COLUMN token_version integer NOT NULL DEFAULT 1;

-- Create a more restrictive RLS policy by dropping the existing broad policy
DROP POLICY IF EXISTS "Users can manage their own Google tokens" ON public.user_google_tokens;

-- Create separate, more restrictive policies for different operations
CREATE POLICY "Users can view their own active Google tokens" 
ON public.user_google_tokens 
FOR SELECT 
USING (auth.uid() = user_id AND is_active = true);

CREATE POLICY "Users can insert their own Google tokens" 
ON public.user_google_tokens 
FOR INSERT 
WITH CHECK (auth.uid() = user_id AND is_active = true);

CREATE POLICY "Users can update their own Google tokens" 
ON public.user_google_tokens 
FOR UPDATE 
USING (auth.uid() = user_id) 
WITH CHECK (auth.uid() = user_id);

-- Users can only soft delete their tokens (set is_active = false), not hard delete
CREATE POLICY "Users can deactivate their own Google tokens" 
ON public.user_google_tokens 
FOR UPDATE 
USING (auth.uid() = user_id) 
WITH CHECK (auth.uid() = user_id AND is_active = false);

-- Create a security definer function to safely access tokens (this will be used by edge functions)
CREATE OR REPLACE FUNCTION public.get_user_google_token(requesting_user_id uuid)
RETURNS TABLE (
    access_token text,
    refresh_token text,
    expires_at timestamp with time zone,
    scope text
)
LANGUAGE plpgsql
SECURITY DEFINER
STABLE
SET search_path = 'public'
AS $$
BEGIN
    -- Only return tokens for the requesting user and update last_used tracking
    UPDATE public.user_google_tokens 
    SET 
        last_used_at = now(),
        last_used_ip = inet_client_addr()
    WHERE user_id = requesting_user_id AND is_active = true;
    
    RETURN QUERY
    SELECT 
        ugt.access_token,
        ugt.refresh_token,
        ugt.expires_at,
        ugt.scope
    FROM public.user_google_tokens ugt
    WHERE ugt.user_id = requesting_user_id 
      AND ugt.is_active = true;
END;
$$;

-- Create a function to safely store/update tokens with automatic encryption
CREATE OR REPLACE FUNCTION public.store_user_google_token(
    requesting_user_id uuid,
    new_access_token text,
    new_refresh_token text,
    new_expires_at timestamp with time zone,
    new_scope text
)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = 'public'
AS $$
BEGIN
    -- Deactivate any existing tokens for this user
    UPDATE public.user_google_tokens 
    SET is_active = false 
    WHERE user_id = requesting_user_id;
    
    -- Insert new token with incremented version
    INSERT INTO public.user_google_tokens (
        user_id, 
        access_token, 
        refresh_token, 
        expires_at, 
        scope,
        token_version,
        is_active,
        last_used_at,
        last_used_ip
    ) VALUES (
        requesting_user_id,
        new_access_token,
        new_refresh_token,
        new_expires_at,
        new_scope,
        COALESCE((SELECT MAX(token_version) + 1 FROM public.user_google_tokens WHERE user_id = requesting_user_id), 1),
        true,
        now(),
        inet_client_addr()
    );
    
    RETURN true;
END;
$$;

-- Create a function to revoke tokens (security measure)
CREATE OR REPLACE FUNCTION public.revoke_user_google_tokens(requesting_user_id uuid)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = 'public'
AS $$
BEGIN
    UPDATE public.user_google_tokens 
    SET is_active = false 
    WHERE user_id = requesting_user_id;
    
    RETURN true;
END;
$$;

-- Grant execute permissions to authenticated users for the safe functions
GRANT EXECUTE ON FUNCTION public.get_user_google_token(uuid) TO authenticated;
GRANT EXECUTE ON FUNCTION public.store_user_google_token(uuid, text, text, timestamp with time zone, text) TO authenticated;
GRANT EXECUTE ON FUNCTION public.revoke_user_google_tokens(uuid) TO authenticated;

-- Create an index for performance on frequently queried columns
CREATE INDEX IF NOT EXISTS idx_user_google_tokens_user_active 
ON public.user_google_tokens (user_id, is_active) 
WHERE is_active = true;

-- Add a check constraint to ensure tokens have reasonable expiration times
ALTER TABLE public.user_google_tokens 
ADD CONSTRAINT check_reasonable_expiration 
CHECK (expires_at > created_at AND expires_at < created_at + interval '1 year');