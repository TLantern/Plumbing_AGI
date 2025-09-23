import { useState, useEffect } from 'react';
import { supabase } from '@/integrations/supabase/client';
import { useAdminAuth } from './useAdminAuth';
import { useAdminWebSocket } from './useAdminWebSocket';

export interface SalonOverview {
  salon_id: string;
  salon_name: string;
  phone?: string;
  timezone?: string;
  created_at: string;
  total_calls: number;
  total_appointments: number;
  total_revenue_cents: number;
}

export interface PlatformMetrics {
  total_salons: number;
  total_calls: number;
  total_appointments: number;
  total_revenue_cents: number;
  active_salons: number;
}

export const useAdminData = () => {
  const { isAdmin, isLoading: adminAuthLoading } = useAdminAuth();
  const {
    isConnected,
    metrics,
    allCallEvents,
    allTranscripts,
    allAppointments,
    todaysStats,
    getSalonData
  } = useAdminWebSocket();
  
  const [salons, setSalons] = useState<SalonOverview[]>([]);
  const [platformMetrics, setPlatformMetrics] = useState<PlatformMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchAdminData = async () => {
      if (!isAdmin || adminAuthLoading) {
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        setError(null);

        // Fetch all salons overview
        const { data: salonsData, error: salonsError } = await supabase
          .rpc('get_all_salons_overview');

        if (salonsError) throw salonsError;

        // Fetch platform metrics
        const { data: metricsData, error: metricsError } = await supabase
          .rpc('get_platform_metrics')
          .single();

        if (metricsError) throw metricsError;

        setSalons(salonsData || []);
        setPlatformMetrics(metricsData);
      } catch (err) {
        console.error('Error fetching admin data:', err);
        setError(err instanceof Error ? err.message : 'Failed to fetch admin data');
      } finally {
        setLoading(false);
      }
    };

    fetchAdminData();
  }, [isAdmin, adminAuthLoading]);

  // Enhance platform metrics with live data
  useEffect(() => {
    if (platformMetrics && todaysStats) {
      setPlatformMetrics(prev => prev ? {
        ...prev,
        total_calls: prev.total_calls + todaysStats.calls,
        total_appointments: prev.total_appointments + todaysStats.appointments,
        total_revenue_cents: prev.total_revenue_cents + todaysStats.revenue
      } : null);
    }
  }, [todaysStats, platformMetrics]);

  return {
    salons,
    platformMetrics,
    loading: adminAuthLoading || loading,
    error,
    // Real-time data
    isLiveConnected: isConnected,
    liveMetrics: metrics,
    allCallEvents,
    allTranscripts,
    allAppointments,
    todaysStats,
    getSalonData,
    refetch: () => {
      if (isAdmin) {
        setLoading(true);
        // Trigger useEffect to run again
      }
    }
  };
};