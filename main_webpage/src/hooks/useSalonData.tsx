import { useState, useEffect } from 'react';
import { useAuth } from './useAuth';
import { useSalonWebSocket } from './useSalonWebSocket';
import { supabase } from '@/integrations/supabase/client';
import type { 
  KPIs, 
  CallsTimeseriesPoint, 
  RevenueByService, 
  RecentCall, 
  TopService 
} from '@/types/salon';

export const useSalonData = (dateRange: string = "30") => {
  const { salonId, isAuthenticated } = useAuth();
  const { 
    isConnected, 
    metrics, 
    recentCallEvents, 
    recentTranscripts, 
    recentAppointments 
  } = useSalonWebSocket();
  
  const [kpis, setKpis] = useState<KPIs | null>(null);
  const [callsTimeseries, setCallsTimeseries] = useState<CallsTimeseriesPoint[]>([]);
  const [revenueByService, setRevenueByService] = useState<RevenueByService>([]);
  const [recentCalls, setRecentCalls] = useState<RecentCall[]>([]);
  const [topServices, setTopServices] = useState<TopService[]>([]);
  const [peakHours, setPeakHours] = useState<number[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const days = parseInt(dateRange);

  useEffect(() => {
    if (!isAuthenticated || !salonId) {
      setLoading(false);
      return;
    }

    const fetchSalonData = async () => {
      setLoading(true);
      setError(null);

      try {
        // Fetch KPIs
        const { data: kpiData, error: kpiError } = await supabase
          .rpc('get_salon_kpis', { p_salon_id: salonId, p_days: days });

        if (kpiError) throw kpiError;

        // Fetch calls timeseries
        const { data: timeseriesData, error: timeseriesError } = await supabase
          .rpc('get_calls_timeseries', { p_salon_id: salonId, p_days: days });

        if (timeseriesError) throw timeseriesError;

        // Fetch revenue by service
        const { data: revenueData, error: revenueError } = await supabase
          .rpc('get_revenue_by_service_view');

        if (revenueError) throw revenueError;

        // Fetch recent calls
        const { data: callsData, error: callsError } = await supabase
          .rpc('get_recent_calls_view');

        if (callsError) throw callsError;

        // Process KPIs data
        if (kpiData && kpiData.length > 0) {
          const kpi = kpiData[0];
          setKpis({
            revenueRecovered: kpi.revenue_recovered_cents || 0,
            callsAnswered: kpi.calls_answered || 0,
            appointmentsBooked: kpi.appointments_booked || 0,
            conversionRate: kpi.conversion_rate || 0
          });
        }

        // Process timeseries data
        if (timeseriesData) {
          const formattedTimeseries = timeseriesData.map((row: any) => ({
            date: row.date,
            answered: row.answered,
            missed: row.missed,
            afterHoursCaptured: row.after_hours_captured
          }));
          setCallsTimeseries(formattedTimeseries);
        }

        // Process revenue by service data
        if (revenueData) {
          const formattedRevenue = revenueData.map((row: any) => ({
            service: row.service,
            revenueCents: row.revenue_cents
          }));
          setRevenueByService(formattedRevenue);

          // Calculate top services from revenue data
          const topServicesData = revenueData.map((row: any) => ({
            service: row.service,
            count: row.appointment_count || 0,
            avgPriceCents: Math.round((row.revenue_cents || 0) / Math.max(row.appointment_count || 1, 1))
          })).sort((a, b) => b.count - a.count).slice(0, 5);
          setTopServices(topServicesData);
        }

        // Process recent calls data
        if (callsData) {
          const formattedCalls = callsData.map((call: any) => ({
            id: call.id,
            timestamp: call.timestamp,
            callerNameMasked: call.caller_name_masked || 'Unknown',
            intent: call.intent || 'General inquiry',
            outcome: call.outcome,
            durationSec: call.duration_seconds,
            sentiment: call.sentiment || 'neutral'
          }));
          setRecentCalls(formattedCalls);

          // Calculate peak hours from calls data
          const hourCounts = new Array(24).fill(0);
          callsData.forEach((call: any) => {
            if (call.timestamp) {
              const hour = new Date(call.timestamp).getHours();
              hourCounts[hour]++;
            }
          });
          setPeakHours(hourCounts);
        }

      } catch (err) {
        console.error('Error fetching salon data:', err);
        setError(err instanceof Error ? err.message : 'Failed to fetch salon data');
      } finally {
        setLoading(false);
      }
    };

    fetchSalonData();
  }, [isAuthenticated, salonId, days]);

  // Enhance KPIs with real-time data
  useEffect(() => {
    if (kpis && recentCallEvents.length > 0) {
      const liveCallsToday = recentCallEvents.filter(call => {
        const callDate = new Date(call.timestamp);
        const today = new Date();
        return callDate.toDateString() === today.toDateString();
      }).length;

      // Update KPIs with live call count
      setKpis(prev => prev ? {
        ...prev,
        callsAnswered: prev.callsAnswered + liveCallsToday
      } : null);
    }
  }, [recentCallEvents, kpis]);

  // Enhance recent calls with live data
  useEffect(() => {
    if (recentCallEvents.length > 0) {
      const liveCallsFormatted: RecentCall[] = recentCallEvents.map((call, index) => ({
        id: `live-${index}`,
        timestamp: call.timestamp,
        callerNameMasked: call.caller_number.replace(/(\d{3})(\d{3})(\d{4})/, '***-***-$4'),
        intent: 'Live Call',
        outcome: call.supabase_logged ? 'answered' : 'in_progress',
        durationSec: 0, // Will be updated when call ends
        sentiment: 'neutral'
      }));

      setRecentCalls(prev => {
        // Merge live calls with existing calls, remove duplicates
        const merged = [...liveCallsFormatted, ...prev];
        const unique = merged.filter((call, index, self) => 
          index === self.findIndex(c => c.timestamp === call.timestamp)
        );
        return unique.slice(0, 10); // Keep only latest 10
      });
    }
  }, [recentCallEvents]);

  // Enhance revenue with live appointments
  useEffect(() => {
    if (recentAppointments.length > 0 && kpis) {
      const liveRevenue = recentAppointments.reduce((total, apt) => 
        total + apt.estimated_revenue_cents, 0
      );

      setKpis(prev => prev ? {
        ...prev,
        revenueRecovered: prev.revenueRecovered + liveRevenue,
        appointmentsBooked: prev.appointmentsBooked + recentAppointments.length
      } : null);
    }
  }, [recentAppointments, kpis]);

  // Update peak hours with live call data
  useEffect(() => {
    if (recentCallEvents.length > 0) {
      const liveHourCounts = new Array(24).fill(0);
      recentCallEvents.forEach(call => {
        const hour = new Date(call.timestamp).getHours();
        liveHourCounts[hour]++;
      });

      setPeakHours(prev => 
        prev.map((count, hour) => count + liveHourCounts[hour])
      );
    }
  }, [recentCallEvents]);

  return {
    kpis,
    callsTimeseries,
    revenueByService,
    recentCalls,
    topServices,
    peakHours,
    loading,
    error,
    // Include real-time connection status
    isLiveConnected: isConnected,
    liveMetrics: metrics,
    liveCallEvents: recentCallEvents,
    liveTranscripts: recentTranscripts,
    liveAppointments: recentAppointments
  };
};