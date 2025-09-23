import { ChevronLeft, ChevronRight } from "lucide-react";
import { useMemo, useState, useEffect } from "react";

type Day = {
  date: Date;
  inCurrentMonth: boolean;
  isToday: boolean;
  events?: CalendarEvent[];
};

type CalendarEvent = {
  id: string;
  title: string;
  start: Date;
  end: Date;
  color?: string;
};

const startOfMonth = (d: Date) => new Date(d.getFullYear(), d.getMonth(), 1);
const endOfMonth = (d: Date) => new Date(d.getFullYear(), d.getMonth() + 1, 0);
const startOfWeek = (d: Date) => {
  const date = new Date(d);
  const day = date.getDay();
  const diff = (day + 6) % 7; // Monday=0
  date.setDate(date.getDate() - diff);
  date.setHours(0, 0, 0, 0);
  return date;
};

const addDays = (d: Date, n: number) => {
  const date = new Date(d);
  date.setDate(date.getDate() + n);
  return date;
};

const isSameDay = (a: Date, b: Date) =>
  a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();

const monthLabel = (d: Date) => d.toLocaleDateString(undefined, { month: "long", year: "numeric" });
const weekdayLabels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export const ContentCalendarGrid = () => {
  const [current, setCurrent] = useState<Date>(new Date());
  const [events, setEvents] = useState<CalendarEvent[]>([]);

  // Mock events for demonstration
  useEffect(() => {
    const mockEvents: CalendarEvent[] = [
      {
        id: "1",
        title: "Team Meeting",
        start: new Date(2024, 11, 15, 10, 0),
        end: new Date(2024, 11, 15, 11, 0),
        color: "#3b82f6"
      },
      {
        id: "2", 
        title: "Client Call",
        start: new Date(2024, 11, 18, 14, 0),
        end: new Date(2024, 11, 18, 15, 0),
        color: "#10b981"
      },
      {
        id: "3",
        title: "Project Review",
        start: new Date(2024, 11, 22, 9, 0),
        end: new Date(2024, 11, 22, 10, 30),
        color: "#f59e0b"
      }
    ];
    setEvents(mockEvents);
  }, []);

  const weeks = useMemo(() => {
    const start = startOfWeek(startOfMonth(current));
    const end = endOfMonth(current);
    const days: Day[] = [];
    let cursor = new Date(start);
    while (true) {
      const inCurrentMonth = cursor.getMonth() === current.getMonth();
      const dayEvents = events.filter(event => 
        isSameDay(event.start, cursor)
      );
      days.push({
        date: new Date(cursor),
        inCurrentMonth,
        isToday: isSameDay(cursor, new Date()),
        events: dayEvents,
      });
      if (cursor >= end && cursor.getDay() === 0) break;
      cursor = addDays(cursor, 1);
    }

    const grid: Day[][] = [];
    for (let i = 0; i < days.length; i += 7) grid.push(days.slice(i, i + 7));
    return grid;
  }, [current, events]);

  const goPrev = () => setCurrent(new Date(current.getFullYear(), current.getMonth() - 1, 1));
  const goNext = () => setCurrent(new Date(current.getFullYear(), current.getMonth() + 1, 1));
  const goToday = () => setCurrent(new Date());

  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <button onClick={goPrev} className="p-2 rounded hover:bg-muted" aria-label="Previous month">
          <ChevronLeft className="h-5 w-5" />
        </button>
        <button onClick={goNext} className="p-2 rounded hover:bg-muted" aria-label="Next month">
          <ChevronRight className="h-5 w-5" />
        </button>
        <button onClick={goToday} className="ml-2 px-3 py-1 rounded border hover:bg-muted text-sm">Today</button>
        <h2 className="ml-4 text-lg font-semibold">{monthLabel(current)}</h2>
      </div>

      <div className="grid grid-cols-7 text-xs text-muted-foreground mb-2">
        {weekdayLabels.map((w) => (
          <div key={w} className="py-2 text-center">{w}</div>
        ))}
      </div>

      <div className="grid grid-cols-7 gap-px rounded-md overflow-hidden bg-border">
        {weeks.flat().map((day, idx) => (
          <div
            key={idx}
            className={
              "aspect-square p-1 bg-background " +
              (day.inCurrentMonth ? "" : "opacity-40 ") +
              (day.isToday ? " bg-orange-100/60 " : "")
            }
          >
            <div className="text-right text-sm mb-1">{day.date.getDate()}</div>
            {day.events && day.events.length > 0 && (
              <div className="space-y-0.5">
                {day.events.slice(0, 2).map((event) => (
                  <div
                    key={event.id}
                    className="text-xs p-1 rounded truncate"
                    style={{ backgroundColor: event.color + "20", color: event.color }}
                  >
                    {event.title}
                  </div>
                ))}
                {day.events.length > 2 && (
                  <div className="text-xs text-muted-foreground">
                    +{day.events.length - 2} more
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

export default ContentCalendarGrid;


