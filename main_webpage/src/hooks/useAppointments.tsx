import { useState, useEffect } from 'react';
import { supabase } from '@/integrations/supabase/client';
import { useAuth } from './useAuth';
import type { Database } from '@/integrations/supabase/types';

type Appointment = Database['public']['Tables']['appointments']['Row'];
type AppointmentInsert = Database['public']['Tables']['appointments']['Insert'];

export interface CalendarAppointment {
  id: string;
  title: string;
  start: Date;
  end: Date;
  color?: string;
  customerName?: string;
  jobType?: string;
  technician?: string;
  appointmentDate?: string;
  status?: string;
  estimatedRevenueCents?: number;
}

export const useAppointments = () => {
  const { user, isAuthenticated } = useAuth();
  const [appointments, setAppointments] = useState<CalendarAppointment[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load appointments from Supabase
  const loadAppointments = async () => {
    if (!isAuthenticated || !user) {
      setAppointments([]);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const { data, error: fetchError } = await supabase
        .from('appointments')
        .select('*')
        .eq('salon_id', user.id)
        .order('appointment_date', { ascending: true });

      if (fetchError) {
        throw fetchError;
      }

      // Convert Supabase appointments to calendar format
      const calendarAppointments: CalendarAppointment[] = (data || []).map((apt) => ({
        id: apt.id,
        title: `${apt.customer_name || 'Customer'} - ${apt.job_type || 'Service'}`,
        start: new Date(apt.appointment_date || ''),
        end: new Date(new Date(apt.appointment_date || '').getTime() + 60 * 60 * 1000), // 1 hour duration
        color: '#f97316', // Orange color
        customerName: apt.customer_name || '',
        jobType: apt.job_type || '',
        technician: apt.technician || '',
        appointmentDate: apt.appointment_date || '',
        status: apt.status || 'pending',
        estimatedRevenueCents: apt.estimated_revenue_cents || 0
      }));

      setAppointments(calendarAppointments);
    } catch (err) {
      console.error('Error loading appointments:', err);
      setError(err instanceof Error ? err.message : 'Failed to load appointments');
    } finally {
      setLoading(false);
    }
  };

  // Add new appointment
  const addAppointment = async (appointmentData: {
    customerName: string;
    jobType: string;
    technician: string;
    time: string;
    date: Date;
  }) => {
    if (!isAuthenticated || !user) {
      throw new Error('User not authenticated');
    }

    setLoading(true);
    setError(null);

    try {
      const [hours, minutes] = appointmentData.time.split(':');
      const appointmentDate = new Date(appointmentData.date);
      appointmentDate.setHours(parseInt(hours), parseInt(minutes));

      const newAppointment: AppointmentInsert = {
        salon_id: user.id,
        appointment_date: appointmentDate.toISOString(),
        customer_name: appointmentData.customerName,
        job_type: appointmentData.jobType,
        technician: appointmentData.technician,
        status: 'pending',
        estimated_revenue_cents: 0 // Default to 0, can be updated later
      };

      const { data, error: insertError } = await supabase
        .from('appointments')
        .insert(newAppointment)
        .select()
        .single();

      if (insertError) {
        throw insertError;
      }

      // Reload appointments to get the updated list
      await loadAppointments();
      
      return data;
    } catch (err) {
      console.error('Error adding appointment:', err);
      setError(err instanceof Error ? err.message : 'Failed to add appointment');
      throw err;
    } finally {
      setLoading(false);
    }
  };

  // Delete appointment
  const deleteAppointment = async (appointmentId: string) => {
    if (!isAuthenticated || !user) {
      throw new Error('User not authenticated');
    }

    setLoading(true);
    setError(null);

    try {
      const { error: deleteError } = await supabase
        .from('appointments')
        .delete()
        .eq('id', appointmentId)
        .eq('salon_id', user.id); // Ensure user can only delete their own appointments

      if (deleteError) {
        throw deleteError;
      }

      // Reload appointments to get the updated list
      await loadAppointments();
    } catch (err) {
      console.error('Error deleting appointment:', err);
      setError(err instanceof Error ? err.message : 'Failed to delete appointment');
      throw err;
    } finally {
      setLoading(false);
    }
  };

  // Load appointments when user changes
  useEffect(() => {
    loadAppointments();
  }, [user, isAuthenticated]);

  return {
    appointments,
    loading,
    error,
    addAppointment,
    deleteAppointment,
    loadAppointments
  };
};
