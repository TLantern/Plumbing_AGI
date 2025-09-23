import { ChevronLeft, ChevronRight, Plus, X, Trash2 } from "lucide-react";
import { useMemo, useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useAppointments, type CalendarAppointment } from "@/hooks/useAppointments";
import { useAuth } from "@/hooks/useAuth";

type Day = {
  date: Date;
  inCurrentMonth: boolean;
  isToday: boolean;
  events?: CalendarEvent[];
};

// Use the CalendarAppointment type from the hook
type CalendarEvent = CalendarAppointment;

type AppointmentForm = {
  customerName: string;
  jobType: string;
  technician: string;
  time: string;
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
  const { isAuthenticated } = useAuth();
  const { appointments, loading, error, addAppointment, deleteAppointment } = useAppointments();
  const [current, setCurrent] = useState<Date>(new Date());
  const [hoveredDate, setHoveredDate] = useState<Date | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [selectedDate, setSelectedDate] = useState<Date | null>(null);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [eventToDelete, setEventToDelete] = useState<CalendarEvent | null>(null);
  const [redHighlightedEvents, setRedHighlightedEvents] = useState<Set<string>>(new Set());
  const [formData, setFormData] = useState<AppointmentForm>({
    customerName: '',
    jobType: '',
    technician: '',
    time: ''
  });

  // Use appointments from Supabase instead of mock data

  const weeks = useMemo(() => {
    const start = startOfWeek(startOfMonth(current));
    const end = endOfMonth(current);
    const days: Day[] = [];
    let cursor = new Date(start);
    while (true) {
      const inCurrentMonth = cursor.getMonth() === current.getMonth();
      const dayEvents = appointments.filter(event => 
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
  }, [current, appointments]);

  const goPrev = () => setCurrent(new Date(current.getFullYear(), current.getMonth() - 1, 1));
  const goNext = () => setCurrent(new Date(current.getFullYear(), current.getMonth() + 1, 1));
  const goToday = () => setCurrent(new Date());

  const handleDateClick = (date: Date) => {
    setSelectedDate(date);
    setShowModal(true);
    setFormData({
      customerName: '',
      jobType: '',
      technician: '',
      time: ''
    });
  };

  const handleSubmitAppointment = async () => {
    if (!selectedDate || !formData.customerName || !formData.jobType || !formData.technician || !formData.time) {
      return;
    }

    if (!isAuthenticated) {
      alert('Please log in to add appointments');
      return;
    }

    try {
      await addAppointment({
        customerName: formData.customerName,
        jobType: formData.jobType,
        technician: formData.technician,
        time: formData.time,
        date: selectedDate
      });
      
      setShowModal(false);
      setSelectedDate(null);
    } catch (err) {
      console.error('Error adding appointment:', err);
      alert('Failed to add appointment. Please try again.');
    }
  };

  const closeModal = () => {
    setShowModal(false);
    setSelectedDate(null);
  };

  const handleDeleteClick = (event: CalendarEvent, e: React.MouseEvent) => {
    e.stopPropagation();
    setEventToDelete(event);
    setRedHighlightedEvents(prev => new Set(prev).add(event.id));
    setShowDeleteModal(true);
  };

  const confirmDelete = async () => {
    if (eventToDelete) {
      try {
        await deleteAppointment(eventToDelete.id);
        setRedHighlightedEvents(prev => {
          const newSet = new Set(prev);
          newSet.delete(eventToDelete.id);
          return newSet;
        });
      } catch (err) {
        console.error('Error deleting appointment:', err);
        alert('Failed to delete appointment. Please try again.');
      }
    }
    setShowDeleteModal(false);
    setEventToDelete(null);
  };

  const cancelDelete = () => {
    if (eventToDelete) {
      setRedHighlightedEvents(prev => {
        const newSet = new Set(prev);
        newSet.delete(eventToDelete.id);
        return newSet;
      });
    }
    setShowDeleteModal(false);
    setEventToDelete(null);
  };

  // Show loading state
  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-4"></div>
          <p className="text-muted-foreground">Loading appointments...</p>
        </div>
      </div>
    );
  }

  // Show error state
  if (error) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <p className="text-destructive mb-2">Error loading appointments</p>
          <p className="text-muted-foreground">{error}</p>
        </div>
      </div>
    );
  }

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
        {!isAuthenticated && (
          <div className="ml-auto text-sm text-muted-foreground">
            Please log in to manage appointments
          </div>
        )}
      </div>

      <div className="grid grid-cols-7 text-xs text-muted-foreground mb-2">
        {weekdayLabels.map((w) => (
          <div key={w} className="py-2 text-center">{w}</div>
        ))}
      </div>

      <div className="grid grid-cols-7 gap-px rounded-md overflow-hidden bg-border">
        {weeks.flat().map((day, idx) => {
          const isHovered = hoveredDate && isSameDay(hoveredDate, day.date);
          return (
            <div
              key={idx}
              className={
                "aspect-square p-1 bg-background relative group cursor-pointer transition-all duration-200 " +
                (day.inCurrentMonth ? "" : "opacity-40 ") +
                (day.isToday ? " bg-orange-100/60 " : "") +
                (isHovered ? "bg-muted/50" : "")
              }
              onMouseEnter={() => setHoveredDate(day.date)}
              onMouseLeave={() => setHoveredDate(null)}
              onClick={() => handleDateClick(day.date)}
            >
              <div className="text-right text-sm mb-1">{day.date.getDate()}</div>
              {day.events && day.events.length > 0 && (
                <div className="space-y-0.5">
                  {day.events.slice(0, 2).map((event) => {
                    const isRedHighlighted = redHighlightedEvents.has(event.id);
                    return (
                      <div
                        key={event.id}
                        className="text-xs p-1 rounded truncate"
                        style={{ 
                          backgroundColor: isRedHighlighted ? "#ef444420" : event.color + "20", 
                          color: isRedHighlighted ? "#ef4444" : event.color 
                        }}
                      >
                        {event.title}
                      </div>
                    );
                  })}
                  {day.events.length > 2 && (
                    <div className="text-xs text-muted-foreground">
                      +{day.events.length - 2} more
                    </div>
                  )}
                </div>
              )}
              
              {/* Hover Buttons */}
              {isHovered && day.inCurrentMonth && (
                <div className="absolute inset-0 bg-background/80 flex items-center justify-center">
                  <div className="flex flex-col gap-2">
                    <Button
                      size="sm"
                      className="bg-orange-500 hover:bg-orange-600 text-white"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDateClick(day.date);
                      }}
                    >
                      <Plus className="h-4 w-4 mr-1" />
                      Add
                    </Button>
                    {day.events && day.events.length > 0 && (
                      <Button
                        size="sm"
                        variant="destructive"
                        onClick={(e) => {
                          e.stopPropagation();
                          // Show delete options for each event
                          if (day.events && day.events.length === 1) {
                            handleDeleteClick(day.events[0], e);
                          } else {
                            // If multiple events, we could show a list to select which one to delete
                            // For now, delete the first one
                            handleDeleteClick(day.events[0], e);
                          }
                        }}
                      >
                        <Trash2 className="h-4 w-4 mr-1" />
                        Delete
                      </Button>
                    )}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Appointment Modal */}
      {showModal && selectedDate && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-background rounded-lg p-6 w-full max-w-md mx-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">
                Add Appointment - {selectedDate.toLocaleDateString()}
              </h3>
              <Button
                variant="ghost"
                size="sm"
                onClick={closeModal}
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
            
            <div className="space-y-4">
              <div>
                <Label htmlFor="customerName">Customer Name</Label>
                <Input
                  id="customerName"
                  value={formData.customerName}
                  onChange={(e) => setFormData(prev => ({ ...prev, customerName: e.target.value }))}
                  placeholder="Enter customer name"
                />
              </div>
              
              <div>
                <Label htmlFor="jobType">Job Type</Label>
                <Select
                  value={formData.jobType}
                  onValueChange={(value) => setFormData(prev => ({ ...prev, jobType: value }))}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select job type" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="haircut">Haircut</SelectItem>
                    <SelectItem value="coloring">Coloring</SelectItem>
                    <SelectItem value="styling">Styling</SelectItem>
                    <SelectItem value="treatment">Treatment</SelectItem>
                    <SelectItem value="consultation">Consultation</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              
              <div>
                <Label htmlFor="technician">Technician</Label>
                <Select
                  value={formData.technician}
                  onValueChange={(value) => setFormData(prev => ({ ...prev, technician: value }))}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select technician" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="sarah">Sarah Johnson</SelectItem>
                    <SelectItem value="mike">Mike Chen</SelectItem>
                    <SelectItem value="emma">Emma Davis</SelectItem>
                    <SelectItem value="alex">Alex Rodriguez</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              
              <div>
                <Label htmlFor="time">Time</Label>
                <Input
                  id="time"
                  type="time"
                  value={formData.time}
                  onChange={(e) => setFormData(prev => ({ ...prev, time: e.target.value }))}
                />
              </div>
            </div>
            
            <div className="flex gap-2 mt-6">
              <Button
                onClick={handleSubmitAppointment}
                className="flex-1 bg-orange-500 hover:bg-orange-600"
                disabled={!formData.customerName || !formData.jobType || !formData.technician || !formData.time}
              >
                Add Appointment
              </Button>
              <Button variant="outline" onClick={closeModal}>
                Cancel
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {showDeleteModal && eventToDelete && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-background rounded-lg p-6 w-full max-w-md mx-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-destructive">
                Delete Appointment
              </h3>
              <Button
                variant="ghost"
                size="sm"
                onClick={cancelDelete}
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
            
            <div className="space-y-4">
              <p className="text-muted-foreground">
                Are you sure you want to delete this appointment?
              </p>
              
              <div className="bg-muted/50 rounded-lg p-4">
                <div className="font-medium">{eventToDelete.title}</div>
                <div className="text-sm text-muted-foreground mt-1">
                  {eventToDelete.start.toLocaleDateString()} at {eventToDelete.start.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </div>
                {eventToDelete.technician && (
                  <div className="text-sm text-muted-foreground">
                    Technician: {eventToDelete.technician}
                  </div>
                )}
              </div>
            </div>
            
            <div className="flex gap-2 mt-6">
              <Button
                variant="destructive"
                onClick={confirmDelete}
                className="flex-1"
              >
                <Trash2 className="h-4 w-4 mr-2" />
                Delete Appointment
              </Button>
              <Button variant="outline" onClick={cancelDelete}>
                Cancel
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ContentCalendarGrid;


