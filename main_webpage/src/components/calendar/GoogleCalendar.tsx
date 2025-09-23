import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Calendar, Clock, MapPin, Users, ExternalLink } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import { format, parseISO, isToday, isTomorrow, isThisWeek, addDays, addHours } from 'date-fns';
import { GoogleCalendarSecurity } from './GoogleCalendarSecurity';
import { useGoogleOAuth } from '@/hooks/useGoogleOAuth';

// Mock calendar events
const mockCalendarEvents: CalendarEvent[] = [
  {
    id: '1',
    title: 'Sarah M. - Balayage',
    start: addHours(new Date(), 2).toISOString(),
    end: addHours(new Date(), 4).toISOString(),
    description: 'Full balayage service',
    location: 'Salon Studio 1',
    attendees: 1,
    isAllDay: false
  },
  {
    id: '2', 
    title: 'Jennifer K. - Cut & Style',
    start: addHours(new Date(), 5).toISOString(),
    end: addHours(new Date(), 6.5).toISOString(),
    description: 'Haircut and blowout',
    location: 'Main Chair',
    attendees: 1,
    isAllDay: false
  },
  {
    id: '3',
    title: 'Maria L. - Color Touch-up',
    start: addDays(new Date(), 1).toISOString(),
    end: addHours(addDays(new Date(), 1), 2).toISOString(),
    description: 'Root touch-up and gloss',
    location: 'Color Station',
    attendees: 1,
    isAllDay: false
  },
  {
    id: '4',
    title: 'Ashley R. - Highlights',
    start: addDays(new Date(), 2).toISOString(),
    end: addHours(addDays(new Date(), 2), 3).toISOString(),
    description: 'Full highlight service',
    location: 'Salon Studio 2',
    attendees: 1,
    isAllDay: false
  },
  {
    id: '5',
    title: 'Staff Meeting',
    start: addDays(new Date(), 3).toISOString(),
    end: addHours(addDays(new Date(), 3), 1).toISOString(),
    description: 'Weekly team meeting',
    location: 'Conference Room',
    attendees: 5,
    isAllDay: false
  }
];

interface CalendarEvent {
  id: string;
  title: string;
  start: string;
  end: string;
  description: string;
  location: string;
  attendees: number;
  isAllDay: boolean;
}

export const GoogleCalendar = () => {
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const { toast } = useToast();
  const { isConnected, isLoading: connecting, connect, disconnect } = useGoogleOAuth();

  const loadCalendarEvents = async () => {
    if (!isConnected) {
      setEvents([]);
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      // TODO: Replace with actual Google Calendar API call
      // For now, use mock data when connected
      setEvents(mockCalendarEvents);
    } catch (error) {
      console.error('Error loading calendar events:', error);
      setEvents([]);
    } finally {
      setLoading(false);
    }
  };

  const connectGoogleCalendar = async () => {
    try {
      await connect();
      // Events will be loaded in useEffect when isConnected changes
    } catch (error) {
      console.error('Error connecting to Google Calendar:', error);
    }
  };

  const getEventDateLabel = (startDate: string) => {
    const date = parseISO(startDate);
    if (isToday(date)) return 'Today';
    if (isTomorrow(date)) return 'Tomorrow';
    if (isThisWeek(date)) return format(date, 'EEEE');
    return format(date, 'MMM d');
  };

  const formatEventTime = (start: string, end: string, isAllDay: boolean) => {
    if (isAllDay) return 'All day';
    const startTime = format(parseISO(start), 'h:mm a');
    const endTime = format(parseISO(end), 'h:mm a');
    return `${startTime} - ${endTime}`;
  };

  useEffect(() => {
    loadCalendarEvents();
  }, [isConnected]);

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Calendar className="h-5 w-5" />
            Google Calendar
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8">
            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary"></div>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!isConnected) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Calendar className="h-5 w-5" />
            Google Calendar
          </CardTitle>
          <CardDescription>
            Connect your Google Calendar to see upcoming appointments
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="text-center py-6">
            <Calendar className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
            <p className="text-muted-foreground mb-4">
              Connect your Google Calendar to view upcoming appointments and schedule insights
            </p>
            <Button onClick={connectGoogleCalendar} disabled={connecting}>
              {connecting ? (
                <>
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                  Connecting...
                </>
              ) : (
                <>
                  <ExternalLink className="h-4 w-4 mr-2" />
                  Connect Google Calendar
                </>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Calendar className="h-5 w-5" />
            Upcoming Appointments
          </CardTitle>
          <CardDescription>
            Your next {events.length} appointments from Google Calendar
          </CardDescription>
        </CardHeader>
        <CardContent>
          {events.length === 0 ? (
            <div className="text-center py-6">
              <Calendar className="h-8 w-8 text-muted-foreground mx-auto mb-2" />
              <p className="text-muted-foreground">No upcoming appointments</p>
            </div>
          ) : (
            <div className="space-y-3">
              {events.slice(0, 8).map((event) => (
                <div key={event.id} className="flex items-start gap-3 p-3 rounded-lg border bg-card/50">
                  <div className="flex-shrink-0 w-16 text-center">
                    <div className="text-xs font-medium text-muted-foreground uppercase">
                      {getEventDateLabel(event.start)}
                    </div>
                    <div className="text-sm font-semibold">
                      {event.isAllDay ? '' : format(parseISO(event.start), 'd')}
                    </div>
                  </div>
                  <div className="flex-1 min-w-0">
                    <h4 className="font-medium truncate">{event.title}</h4>
                    <div className="flex items-center gap-4 text-sm text-muted-foreground mt-1">
                      <div className="flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        {formatEventTime(event.start, event.end, event.isAllDay)}
                      </div>
                      {event.location && (
                        <div className="flex items-center gap-1">
                          <MapPin className="h-3 w-3" />
                          <span className="truncate max-w-24">{event.location}</span>
                        </div>
                      )}
                      {event.attendees > 0 && (
                        <div className="flex items-center gap-1">
                          <Users className="h-3 w-3" />
                          {event.attendees}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
              {events.length > 8 && (
                <div className="text-center pt-2">
                  <p className="text-sm text-muted-foreground">
                    +{events.length - 8} more appointments
                  </p>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>
      
      <GoogleCalendarSecurity 
        isConnected={isConnected} 
        onConnectionChange={checkConnection}
      />
    </div>
  );
};