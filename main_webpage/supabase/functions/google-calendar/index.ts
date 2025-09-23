import { serve } from "https://deno.land/std@0.190.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.57.2";

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
};

const logStep = (step: string, details?: any) => {
  const detailsStr = details ? ` - ${JSON.stringify(details)}` : '';
  console.log(`[GOOGLE-CALENDAR] ${step}${detailsStr}`);
};

serve(async (req) => {
  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    logStep("Function started");

    const supabaseClient = createClient(
      Deno.env.get("SUPABASE_URL") ?? "",
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "",
      { auth: { persistSession: false } }
    );

    const authHeader = req.headers.get("Authorization");
    if (!authHeader) throw new Error("No authorization header provided");

    const token = authHeader.replace("Bearer ", "");
    const { data: userData, error: userError } = await supabaseClient.auth.getUser(token);
    if (userError) throw new Error(`Authentication error: ${userError.message}`);
    const user = userData.user;
    if (!user) throw new Error("User not authenticated");

    logStep("User authenticated", { userId: user.id });

    // Get stored Google tokens using secure function
    const { data: tokenResults, error: tokenError } = await supabaseClient
      .rpc('get_user_google_token', { requesting_user_id: user.id });

    if (tokenError || !tokenResults || tokenResults.length === 0) {
      throw new Error("Google Calendar not connected. Please connect your Google account first.");
    }

    const tokenData = tokenResults[0];
    let accessToken = tokenData.access_token;
    const expiresAt = new Date(tokenData.expires_at);

    // Check if token needs refresh
    if (expiresAt <= new Date()) {
      logStep("Token expired, refreshing");
      
      const refreshResponse = await fetch('https://oauth2.googleapis.com/token', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: new URLSearchParams({
          client_id: Deno.env.get("GOOGLE_CLIENT_ID") || "",
          client_secret: Deno.env.get("GOOGLE_CLIENT_SECRET") || "",
          refresh_token: tokenData.refresh_token,
          grant_type: 'refresh_token',
        }),
      });

      if (!refreshResponse.ok) {
        throw new Error("Failed to refresh Google token");
      }

      const refreshData = await refreshResponse.json();
      accessToken = refreshData.access_token;

      // Update stored token using secure function
      const { error: updateError } = await supabaseClient
        .rpc('store_user_google_token', {
          requesting_user_id: user.id,
          new_access_token: accessToken,
          new_refresh_token: tokenData.refresh_token,
          new_expires_at: new Date(Date.now() + refreshData.expires_in * 1000).toISOString(),
          new_scope: tokenData.scope,
        });

      if (updateError) {
        logStep("Error updating refreshed token", { error: updateError });
        throw new Error(`Failed to update token: ${updateError.message}`);
      }

      logStep("Token refreshed successfully");
    }

    // Fetch calendar events for the next 30 days
    const now = new Date();
    const thirtyDaysFromNow = new Date(now.getTime() + 30 * 24 * 60 * 60 * 1000);

    const calendarResponse = await fetch(
      `https://www.googleapis.com/calendar/v3/calendars/primary/events?` +
      `timeMin=${now.toISOString()}&` +
      `timeMax=${thirtyDaysFromNow.toISOString()}&` +
      `singleEvents=true&` +
      `orderBy=startTime&` +
      `maxResults=50`,
      {
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
        },
      }
    );

    if (!calendarResponse.ok) {
      throw new Error(`Calendar API error: ${calendarResponse.statusText}`);
    }

    const calendarData = await calendarResponse.json();
    logStep("Calendar events fetched", { eventCount: calendarData.items?.length || 0 });

    // Format events for frontend
    const events = (calendarData.items || []).map((event: any) => ({
      id: event.id,
      title: event.summary || 'Untitled Event',
      start: event.start?.dateTime || event.start?.date,
      end: event.end?.dateTime || event.end?.date,
      description: event.description || '',
      location: event.location || '',
      attendees: event.attendees?.length || 0,
      isAllDay: !event.start?.dateTime,
    }));

    return new Response(JSON.stringify({ events }), {
      headers: { ...corsHeaders, "Content-Type": "application/json" },
      status: 200,
    });

  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    logStep("ERROR", { message: errorMessage });
    return new Response(JSON.stringify({ error: errorMessage }), {
      headers: { ...corsHeaders, "Content-Type": "application/json" },
      status: 500,
    });
  }
});