import { useState, useEffect, useRef, useCallback } from 'react';
import { useAdminAuth } from './useAdminAuth';
import { SALON_PHONE_CONFIG } from '@/lib/config';

interface WebSocketMessage {
  type: 'metrics' | 'call_started' | 'transcript' | 'shop_updated' | 'appointment_created' | 'keepalive';
  data: any;
}

interface AdminMetrics {
  timestamp: string;
  active_calls: number;
  total_shops: number;
  shops: Array<{
    location_id: number;
    phone_number: string;
    business_name: string;
    active_calls: number;
  }>;
  recent_calls: Array<{
    call_sid: string;
    location_id: number;
    caller_number: string;
    to_number: string;
    message_count: number;
    start_time: string;
  }>;
  system_status: string;
}

interface AdminCallEvent {
  call_sid: string;
  location_id: number;
  caller_number: string;
  to_number: string;
  timestamp: string;
  supabase_logged?: boolean;
  fallback_logged?: boolean;
  error?: string;
}

interface AdminTranscriptEvent {
  call_sid: string;
  location_id: number;
  prompt: string;
  response: string;
  duration: string;
  timestamp: string;
}

interface AdminAppointmentEvent {
  shop_id: string;
  appointment_id: string;
  call_id: string;
  estimated_revenue_cents: number;
  timestamp: string;
}

export const useAdminWebSocket = () => {
  const { isAdmin } = useAdminAuth();
  const [isConnected, setIsConnected] = useState(false);
  const [metrics, setMetrics] = useState<AdminMetrics | null>(null);
  const [allCallEvents, setAllCallEvents] = useState<AdminCallEvent[]>([]);
  const [allTranscripts, setAllTranscripts] = useState<AdminTranscriptEvent[]>([]);
  const [allAppointments, setAllAppointments] = useState<AdminAppointmentEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttempts = useRef(0);
  const maxReconnectAttempts = SALON_PHONE_CONFIG.RECONNECT_ATTEMPTS;

  const connect = useCallback(() => {
    if (!isAdmin) return;

    // Use the salon phone service WebSocket endpoint
    const wsUrl = SALON_PHONE_CONFIG.WEBSOCKET_URL;
    
    try {
      wsRef.current = new WebSocket(wsUrl);
      
      wsRef.current.onopen = () => {
        console.log('🔗 Admin connected to salon phone service WebSocket');
        setIsConnected(true);
        setError(null);
        reconnectAttempts.current = 0;
      };
      
      wsRef.current.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data);
          handleMessage(message);
        } catch (err) {
          console.error('Error parsing WebSocket message:', err);
        }
      };
      
      wsRef.current.onclose = (event) => {
        console.log('🔌 Admin WebSocket connection closed:', event.code, event.reason);
        setIsConnected(false);
        
        // Attempt to reconnect if not a normal closure
        if (event.code !== 1000 && reconnectAttempts.current < maxReconnectAttempts) {
          const delay = Math.min(
            SALON_PHONE_CONFIG.RECONNECT_DELAY * Math.pow(2, reconnectAttempts.current), 
            SALON_PHONE_CONFIG.MAX_RECONNECT_DELAY
          );
          console.log(`🔄 Admin attempting to reconnect in ${delay}ms (attempt ${reconnectAttempts.current + 1})`);
          
          reconnectTimeoutRef.current = setTimeout(() => {
            reconnectAttempts.current++;
            connect();
          }, delay);
        } else if (reconnectAttempts.current >= maxReconnectAttempts) {
          setError('Failed to reconnect to salon phone service after multiple attempts');
        }
      };
      
      wsRef.current.onerror = (error) => {
        console.error('Admin WebSocket error:', error);
        setError('Connection error with salon phone service');
      };
      
    } catch (err) {
      console.error('Error creating admin WebSocket connection:', err);
      setError('Failed to connect to salon phone service');
    }
  }, [isAdmin]);

  const handleMessage = useCallback((message: WebSocketMessage) => {
    switch (message.type) {
      case 'metrics':
        setMetrics(message.data);
        break;
        
      case 'call_started':
        const callEvent: AdminCallEvent = message.data;
        setAllCallEvents(prev => {
          const updated = [callEvent, ...prev].slice(0, 50); // Keep last 50 calls across all salons
          return updated;
        });
        break;
        
      case 'transcript':
        const transcriptEvent: AdminTranscriptEvent = message.data;
        setAllTranscripts(prev => {
          const updated = [transcriptEvent, ...prev].slice(0, 100); // Keep last 100 transcripts
          return updated;
        });
        break;
        
      case 'appointment_created':
        const appointmentEvent: AdminAppointmentEvent = message.data;
        setAllAppointments(prev => {
          const updated = [appointmentEvent, ...prev].slice(0, 50); // Keep last 50 appointments
          return updated;
        });
        break;
        
      case 'keepalive':
        // Just acknowledge the keepalive
        break;
        
      default:
        console.log('Unknown message type:', message.type);
    }
  }, []);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    
    if (wsRef.current) {
      wsRef.current.close(1000, 'Admin component unmounting');
      wsRef.current = null;
    }
    
    setIsConnected(false);
  }, []);

  useEffect(() => {
    if (isAdmin) {
      connect();
    }
    
    return () => {
      disconnect();
    };
  }, [isAdmin, connect, disconnect]);

  // Calculate aggregate metrics for today
  const today = new Date().toDateString();
  const todaysCallEvents = allCallEvents.filter(call => 
    new Date(call.timestamp).toDateString() === today
  );
  const todaysAppointments = allAppointments.filter(apt => 
    new Date(apt.timestamp).toDateString() === today
  );
  const todaysRevenue = todaysAppointments.reduce((total, apt) => 
    total + apt.estimated_revenue_cents, 0
  );

  // Get salon-specific data
  const getSalonData = (salonId: string) => {
    const callEvents = allCallEvents.filter(call => 
      call.location_id.toString() === salonId
    );
    const transcripts = allTranscripts.filter(transcript => 
      transcript.location_id.toString() === salonId
    );
    const appointments = allAppointments.filter(appointment => 
      appointment.shop_id === salonId
    );

    return {
      callEvents,
      transcripts,
      appointments
    };
  };

  return {
    isConnected,
    metrics,
    allCallEvents,
    allTranscripts,
    allAppointments,
    error,
    reconnect: connect,
    // Today's aggregated stats
    todaysStats: {
      calls: todaysCallEvents.length,
      appointments: todaysAppointments.length,
      revenue: todaysRevenue
    },
    // Function to get salon-specific data
    getSalonData
  };
};
