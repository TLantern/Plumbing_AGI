import { useCallback, useEffect, useState } from 'react';
import { supabase } from '@/integrations/supabase/client';
import { useToast } from '@/hooks/use-toast';

type UseGoogleOAuthReturn = {
  isConnected: boolean;
  isLoading: boolean;
  connect: () => Promise<void>;
  disconnect: () => Promise<void>;
};

export const useGoogleOAuth = (): UseGoogleOAuthReturn => {
  const { toast } = useToast();
  const [isConnected, setIsConnected] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const refreshConnectionStatus = useCallback(async () => {
    try {
      const session = await supabase.auth.getSession();
      if (!session.data.session) {
        setIsConnected(false);
        return;
      }
      const userRes = await supabase.auth.getUser();
      const userId = userRes.data.user?.id;
      if (!userId) {
        setIsConnected(false);
        return;
      }
      const { data, error } = await supabase.rpc('get_user_google_token', {
        requesting_user_id: userId,
      });
      if (error) {
        setIsConnected(false);
        return;
      }
      setIsConnected(Array.isArray(data) ? data.length > 0 : !!data);
    } catch {
      setIsConnected(false);
    }
  }, []);

  const connect = useCallback(async () => {
    setIsLoading(true);
    try {
      const session = await supabase.auth.getSession();
      if (!session.data.session) throw new Error('Not authenticated');
      const { data, error } = await supabase.functions.invoke('google-oauth', {
        body: { action: 'get_auth_url' },
        headers: { Authorization: `Bearer ${session.data.session.access_token}` },
      });
      if (error) throw error;
      const authUrl = (data as any)?.authUrl;
      if (!authUrl) throw new Error('Missing auth URL');
      window.location.href = authUrl;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const disconnect = useCallback(async () => {
    setIsLoading(true);
    try {
      const userRes = await supabase.auth.getUser();
      const userId = userRes.data.user?.id;
      if (!userId) throw new Error('Not authenticated');
      const { error } = await supabase.rpc('revoke_user_google_tokens', {
        requesting_user_id: userId,
      });
      if (error) throw error;
      await refreshConnectionStatus();
      toast({ title: 'Disconnected', description: 'Google Calendar disconnected.' });
    } catch (err: any) {
      toast({ title: 'Disconnect Failed', description: err?.message || 'Unknown error', variant: 'destructive' });
    } finally {
      setIsLoading(false);
    }
  }, [refreshConnectionStatus, toast]);

  useEffect(() => {
    const handleOAuthCallback = async () => {
      const urlParams = new URLSearchParams(window.location.search);
      const code = urlParams.get('code');
      const state = urlParams.get('state');
      const error = urlParams.get('error');

      if (error) {
        console.error('OAuth error:', error);
        toast({
          title: "Authentication Error",
          description: "Failed to connect to Google Calendar. Please try again.",
          variant: "destructive",
        });
        return;
      }

      if (code && state) {
        try {
          const session = await supabase.auth.getSession();
          if (!session.data.session) return;

          // Exchange the authorization code for tokens
          const { error: exchangeError } = await supabase.functions.invoke('google-oauth', {
            body: { 
              action: 'exchange_code', 
              code: code 
            },
            headers: {
              Authorization: `Bearer ${session.data.session.access_token}`,
            },
          });

          if (exchangeError) {
            throw exchangeError;
          }

          toast({
            title: "Successfully Connected!",
            description: "Your Google Calendar has been connected to your dashboard.",
          });

          // Clean up URL parameters
          const newUrl = window.location.origin + window.location.pathname;
          window.history.replaceState({}, document.title, newUrl);

          // Refresh the page to show calendar data
          await refreshConnectionStatus();

        } catch (error) {
          console.error('Error exchanging OAuth code:', error);
          toast({
            title: "Connection Failed",
            description: "Failed to complete Google Calendar connection. Please try again.",
            variant: "destructive",
          });
        }
      }
    };

    handleOAuthCallback();
    refreshConnectionStatus();
  }, [toast, refreshConnectionStatus]);

  return { isConnected, isLoading, connect, disconnect };
};