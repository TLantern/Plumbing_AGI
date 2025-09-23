import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Calendar, Clock, TrendingUp, Users } from 'lucide-react';
import { format, parseISO, isToday, isTomorrow, startOfWeek, endOfWeek, isWithinInterval } from 'date-fns';

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

interface CalendarStatsProps {
  events: CalendarEvent[];
}

export const CalendarStats = ({ events }: CalendarStatsProps) => {
  const now = new Date();
  const weekStart = startOfWeek(now);
  const weekEnd = endOfWeek(now);

  const todayEvents = events.filter(event => isToday(parseISO(event.start)));
  const tomorrowEvents = events.filter(event => isTomorrow(parseISO(event.start)));
  const thisWeekEvents = events.filter(event => 
    isWithinInterval(parseISO(event.start), { start: weekStart, end: weekEnd })
  );

  const totalAttendees = events.reduce((sum, event) => sum + event.attendees, 0);
  const avgAttendeesPerEvent = events.length > 0 ? Math.round(totalAttendees / events.length) : 0;

  const stats = [
    {
      title: "Today's Appointments",
      value: todayEvents.length,
      icon: Calendar,
      description: "Scheduled for today",
      color: "text-blue-600"
    },
    {
      title: "Tomorrow's Appointments", 
      value: tomorrowEvents.length,
      icon: Clock,
      description: "Scheduled for tomorrow",
      color: "text-green-600"
    },
    {
      title: "This Week",
      value: thisWeekEvents.length,
      icon: TrendingUp,
      description: "Total this week",
      color: "text-purple-600"
    },
    {
      title: "Avg. Attendees",
      value: avgAttendeesPerEvent,
      icon: Users,
      description: "Per appointment",
      color: "text-orange-600"
    }
  ];

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      {stats.map((stat) => (
        <Card key={stat.title}>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">
              {stat.title}
            </CardTitle>
            <stat.icon className={`h-4 w-4 ${stat.color}`} />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stat.value}</div>
            <p className="text-xs text-muted-foreground">
              {stat.description}
            </p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
};