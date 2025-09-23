import { useState, useEffect, useRef, useCallback } from 'react';
import { useAuth } from './useAuth';
import { SALON_PHONE_CONFIG } from '@/lib/config';

interface WebSocketMessage {
  type: 'metrics' | 'call_started' | 'transcript' | 'shop_updated' | 'appointment_created' | 'keepalive';
  data: any;
}

interface SalonMetrics {
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

interface CallEvent {
  call_sid: string;
  location_id: number;
  caller_number: string;
  to_number: string;
  timestamp: string;
  supabase_logged?: boolean;
  fallback_logged?: boolean;
  error?: string;
}

interface TranscriptEvent {
  call_sid: string;
  location_id: number;
  prompt: string;
  response: string;
  duration: string;
  timestamp: string;
}

interface AppointmentEvent {
  shop_id: string;
  appointment_id: string;
  call_id: string;
  estimated_revenue_cents: number;
  timestamp: string;
}

export const useSalonWebSocket = () => {
  const { salonId, isAuthenticated } = useAuth();
  const [isConnected, setIsConnected] = useState(false);
  const [metrics, setMetrics] = useState<SalonMetrics | null>(null);
  const [recentCallEvents, setRecentCallEvents] = useState<CallEvent[]>([]);
  const [recentTranscripts, setRecentTranscripts] = useState<TranscriptEvent[]>([]);
  const [recentAppointments, setRecentAppointments] = useState<AppointmentEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttempts = useRef(0);
  const maxReconnectAttempts = SALON_PHONE_CONFIG.RECONNECT_ATTEMPTS;

  const connect = useCallback(() => {
    if (!isAuthenticated || !salonId) return;

    // Use the salon phone service WebSocket endpoint
    const wsUrl = SALON_PHONE_CONFIG.WEBSOCKET_URL;
    
    try {
      wsRef.current = new WebSocket(wsUrl);
      
      wsRef.current.onopen = () => {
        console.log('🔗 Connected to salon phone service WebSocket');
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
        console.log('🔌 WebSocket connection closed:', event.code, event.reason);
        setIsConnected(false);
        
        // Attempt to reconnect if not a normal closure
        if (event.code !== 1000 && reconnectAttempts.current < maxReconnectAttempts) {
          const delay = Math.min(
            SALON_PHONE_CONFIG.RECONNECT_DELAY * Math.pow(2, reconnectAttempts.current), 
            SALON_PHONE_CONFIG.MAX_RECONNECT_DELAY
          );
          console.log(`🔄 Attempting to reconnect in ${delay}ms (attempt ${reconnectAttempts.current + 1})`);
          
          reconnectTimeoutRef.current = setTimeout(() => {
            reconnectAttempts.current++;
            connect();
          }, delay);
        } else if (reconnectAttempts.current >= maxReconnectAttempts) {
          setError('Failed to reconnect to salon phone service after multiple attempts');
        }
      };
      
      wsRef.current.onerror = (error) => {
        console.error('WebSocket error:', error);
        setError('Connection error with salon phone service');
      };
      
    } catch (err) {
      console.error('Error creating WebSocket connection:', err);
      setError('Failed to connect to salon phone service');
    }
  }, [isAuthenticated, salonId]);

  const handleMessage = useCallback((message: WebSocketMessage) => {
    switch (message.type) {
      case 'metrics':
        setMetrics(message.data);
        break;
        
      case 'call_started':
        const callEvent: CallEvent = message.data;
        setRecentCallEvents(prev => {
          const updated = [callEvent, ...prev].slice(0, SALON_PHONE_CONFIG.MAX_CALL_EVENTS);
          return updated;
        });
        break;
        
      case 'transcript':
        const transcriptEvent: TranscriptEvent = message.data;
        setRecentTranscripts(prev => {
          const updated = [transcriptEvent, ...prev].slice(0, SALON_PHONE_CONFIG.MAX_TRANSCRIPTS);
          return updated;
        });
        break;
        
      case 'appointment_created':
        const appointmentEvent: AppointmentEvent = message.data;
        setRecentAppointments(prev => {
          const updated = [appointmentEvent, ...prev].slice(0, SALON_PHONE_CONFIG.MAX_APPOINTMENTS);
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
      wsRef.current.close(1000, 'Component unmounting');
      wsRef.current = null;
    }
    
    setIsConnected(false);
  }, []);

  useEffect(() => {
    if (isAuthenticated && salonId) {
      connect();
    }
    
    return () => {
      disconnect();
    };
  }, [isAuthenticated, salonId, connect, disconnect]);

  // Get salon-specific data
  const salonMetrics = metrics ? {
    ...metrics,
    shops: metrics.shops.filter(shop => shop.location_id.toString() === salonId),
    recent_calls: metrics.recent_calls.filter(call => call.location_id.toString() === salonId)
  } : null;

  const salonCallEvents = recentCallEvents.filter(event => 
    event.location_id.toString() === salonId
  );

  const salonTranscripts = recentTranscripts.filter(transcript => 
    transcript.location_id.toString() === salonId
  );

  const salonAppointments = recentAppointments.filter(appointment => 
    appointment.shop_id === salonId
  );

  return {
    isConnected,
    metrics: salonMetrics,
    recentCallEvents: salonCallEvents,
    recentTranscripts: salonTranscripts,
    recentAppointments: salonAppointments,
    error,
    reconnect: connect
  };
};
