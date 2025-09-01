import { useEffect, useMemo, useState, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Table, THead, TBody, TR, TH, TD } from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { useWebSocket } from '@/hooks/useWebSocket';
import { useIsMounted } from '@/hooks/useIsMounted';
import { cn } from '@/lib/utils';
import FullCalendar from '@fullcalendar/react';
import dayGridPlugin from '@fullcalendar/daygrid';
import interactionPlugin from '@fullcalendar/interaction';

interface SlaPoint { date: string; value: number; }
interface CsatPoint { name: string; value: number; }
interface RecentCall {
  call_sid: string;
  from?: string;
  to?: string;
  start_ts: number;
  end_ts: number;
  duration_sec: number;
  answered: boolean;
  answer_time_sec?: number | null;
}

interface CalendarEvent {
  id: string;
  title: string;
  start: string;
  end: string;
  customer_name: string;
  service_type: string;
  address: string;
  phone: string;
  call_sid: string;
  backgroundColor: string;
  borderColor: string;
  textColor: string;
}
interface MetricsSnapshot {
  activeCalls: number;
  totalCalls: number;
  answeredCalls: number;
  abandonedCalls: number;
  ahtSec: number;
  avgWaitSec: number;
  abandonRate: number;
  sla: SlaPoint[];
  csat: CsatPoint[];
  agents: any[];
  recentCalls: RecentCall[];
  timestamp: string;
  aht: string;
  avgWait: string;
}

const defaultMetrics: MetricsSnapshot = {
  activeCalls: 0,
  totalCalls: 0,
  answeredCalls: 0,
  abandonedCalls: 0,
  ahtSec: 0,
  avgWaitSec: 0,
  abandonRate: 0,
  sla: [],
  csat: [],
  agents: [],
  recentCalls: [],
  timestamp: new Date().toISOString(),
  aht: '00:00',
  avgWait: '00:00',
};

function formatTime(sec: number) {
  const s = Math.max(0, Math.floor(sec));
  const m = Math.floor(s / 60);
  const rem = s % 60;
  return `${String(m).padStart(2, '0')}:${String(rem).padStart(2, '0')}`;
}

function useSlaClock(activeCalls: number) {
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (activeCalls > 0 && !startedAt) setStartedAt(Date.now());
    if (activeCalls === 0) {
      setStartedAt(null);
      setElapsed(0);
    }
  }, [activeCalls, startedAt]);

  useEffect(() => {
    if (!startedAt) return;
    const id = setInterval(() => setElapsed(Math.floor((Date.now() - startedAt) / 1000)), 500);
    return () => clearInterval(id);
  }, [startedAt]);

  return { running: Boolean(startedAt), elapsedSec: elapsed };
}

function FullCalendarComponent({ 
  date = new Date(), 
  onSelect,
  events = []
}: { 
  date?: Date; 
  onSelect?: (d: Date) => void;
  events?: CalendarEvent[];
}) {
  const calendarRef = useRef<any>(null);
  
  const handleDateClick = (arg: any) => {
    onSelect?.(arg.date);
  };

  const handleEventClick = (arg: any) => {
    const event = arg.event;
    // Show event details in a simple alert for now
    alert(`Appointment Details:
Customer: ${event.extendedProps.customer_name}
Service: ${event.extendedProps.service_type}
Address: ${event.extendedProps.address}
Phone: ${event.extendedProps.phone}
Time: ${new Date(event.start).toLocaleString()}`);
  };

  const goToDate = (newDate: Date) => {
    const calendarApi = calendarRef.current?.getApi();
    if (calendarApi) {
      calendarApi.gotoDate(newDate);
    }
  };

  // Update calendar when date prop changes
  useEffect(() => {
    if (date) {
      goToDate(date);
    }
  }, [date]);

  return (
    <div className="space-y-2">
      <div className="fullcalendar-container bg-white rounded-lg p-4">
        <FullCalendar
          ref={calendarRef}
          plugins={[dayGridPlugin, interactionPlugin]}
          initialView="dayGridMonth"
          initialDate={date}
          dateClick={handleDateClick}
          eventClick={handleEventClick}
          height="auto"
          headerToolbar={{
            left: 'prev,next today',
            center: 'title',
            right: 'dayGridMonth'
          }}
          dayMaxEvents={true}
          moreLinkClick="popover"
          fixedWeekCount={false}
          showNonCurrentDates={true}
          aspectRatio={1.35}
          selectable={true}
          selectMirror={true}
          dayHeaders={true}
          weekends={true}
          navLinks={true}
          editable={false}
          eventDisplay="block"
          events={events}
        />
      </div>
    </div>
  );
}



export default function SalonOpsDashboard() {
  const mounted = useIsMounted();
  const [metrics, setMetrics] = useState<MetricsSnapshot>(defaultMetrics);
  const [wsProblem, setWsProblem] = useState<string | null>(null);

  const [leftTab, setLeftTab] = useState<'live' | 'inbox'>('live');
  const [rightTab, setRightTab] = useState<'details' | 'notes'>('details');
  const [selectedCall, setSelectedCall] = useState<RecentCall | null>(null);
  const [selectedDate, setSelectedDate] = useState<Date | null>(new Date());

  const transcriptRef = useRef<HTMLDivElement | null>(null);
  const [transcripts, setTranscripts] = useState<Array<{ callSid: string; text: string; intent?: string; ts: string }>>([]);
  const [activeCallSids, setActiveCallSids] = useState<string[]>([]);
  const [crmToast, setCrmToast] = useState(false);

  // Real-time log monitoring state
  const [recentCallEvents, setRecentCallEvents] = useState<any[]>([]);
  const [logActivity, setLogActivity] = useState(false);
  const [lastLogUpdate, setLastLogUpdate] = useState<string>('');

  const wsUrl = useMemo(() => {
    if (typeof window === 'undefined') return null;
    const env = process.env.NEXT_PUBLIC_BACKEND_WS as string | undefined;
    if (env) return env;
    const host = window.location.hostname;
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
    return `${proto}://${host}:5001/ops`;
  }, []);

  const [drawerOpen, setDrawerOpen] = useState(false);
  const [jobDesc, setJobDesc] = useState<{
    callSid?: string;
    customer_phone: string;
    customer_name: string;
    service_type: string;
    appointment_time: string;
    address?: string;
    notes?: string;
  } | null>(null);
  const [highlightActions, setHighlightActions] = useState(false);
  const [overrideMode, setOverrideMode] = useState(false);
  const [overrideDate, setOverrideDate] = useState<Date | null>(null);

  // Action Audit State
  interface SystemAction {
    id: string;
    timestamp: string;
    action: string;
    description: string;
    status: 'completed' | 'in_progress' | 'pending';
  }
  const [systemActions, setSystemActions] = useState<SystemAction[]>([]);
  const [calendarEvents, setCalendarEvents] = useState<CalendarEvent[]>([]);

  // Helper function to add system actions
  const addSystemAction = (action: string, description: string, status: 'completed' | 'in_progress' | 'pending' = 'completed') => {
    const newAction: SystemAction = {
      id: Date.now().toString(),
      timestamp: new Date().toISOString(),
      action,
      description,
      status
    };
    setSystemActions(prev => [newAction, ...prev.slice(0, 9)]); // Keep last 10 actions
  };

  // Helper functions for salon service intent display
  const getIntentColor = (intent: string): string => {
    const colors: Record<string, string> = {
      HAIRCUT: 'bg-pink-400/30 text-pink-200 border border-pink-400/50',
      STYLING: 'bg-purple-400/30 text-purple-200 border border-purple-400/50',
      COLORING: 'bg-rose-400/30 text-rose-200 border border-rose-400/50',
      HIGHLIGHTS: 'bg-amber-400/30 text-amber-200 border border-amber-400/50',
      MANICURE: 'bg-emerald-400/30 text-emerald-200 border border-emerald-400/50',
      PEDICURE: 'bg-cyan-400/30 text-cyan-200 border border-cyan-400/50',
      FACIAL: 'bg-indigo-400/30 text-indigo-200 border border-indigo-400/50',
      MASSAGE: 'bg-violet-400/30 text-violet-200 border border-violet-400/50',
      EYEBROWS: 'bg-fuchsia-400/30 text-fuchsia-200 border border-fuchsia-400/50',
      CONSULTATION: 'bg-teal-400/30 text-teal-200 border border-teal-400/50',
      GENERAL_INQUIRY: 'bg-slate-400/30 text-slate-200 border border-slate-400/50',
    };
    return colors[intent] || colors.GENERAL_INQUIRY;
  };

  const formatIntentTag = (intent: string): string => {
    return intent
      .toLowerCase()
      .split('_')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  };

  useWebSocket<{ type: string; data?: any }>(wsUrl, {
    onOpen: () => setWsProblem(null),
    onError: () => setWsProblem('WebSocket connection issue'),
    onMessage: (msg) => {
      if (msg?.type === 'metrics' && msg.data) {
        setMetrics((prev) => ({ ...prev, ...msg.data }));
        const recents = msg.data?.recentCalls || [];
        const active = new Set<string>();
        recents.forEach((c: any) => { if (c.answered && !c.end_ts) active.add(c.call_sid); });
        const newActiveCalls = Array.from(active);
        
        // Track call activity changes
        if (newActiveCalls.length > activeCallSids.length) {
          addSystemAction('Call Received', 'New incoming call is being processed and analyzed', 'in_progress');
        } else if (newActiveCalls.length < activeCallSids.length) {
          addSystemAction('Call Ended', 'Call completed and being processed for follow-up actions', 'completed');
        }
        
        setActiveCallSids(newActiveCalls);
        // Note: Don't clear transcripts here - only clear when full conversation ends
        // Individual call ends don't mean the full conversation is over
      }
      if (msg?.type === 'transcript' && msg.data) {
        setTranscripts((prev) => [...prev.slice(-199), msg.data]);
        if (msg.data.intent) {
          addSystemAction('Intent Detected', `Identified customer needs: ${formatIntentTag(msg.data.intent)}`, 'completed');
        } else {
          addSystemAction('Speech Analyzed', 'Converting speech to text and analyzing customer conversation', 'completed');
        }
      }
      if (msg?.type === 'conversation_ended' && msg.data?.callSid) {
        // Clear transcripts only when full conversation ends
        setTranscripts((prev) => prev.filter(t => t.callSid !== msg.data.callSid));
        addSystemAction('Conversation Complete', 'Customer conversation ended and all data has been processed', 'completed');
      }
      if (msg?.type === 'job_description' && msg.data) {
        const jd = msg.data.job || {};
        setJobDesc({
          callSid: msg.data.callSid,
          customer_phone: jd.customer_phone,
          customer_name: jd.customer_name,
          service_type: jd.service_type,
          appointment_time: jd.appointment_time,
          address: jd.address,
          notes: jd.notes,
        });
        // Auto-select this call in inbox to enable Approve/Override actions
        setSelectedCall({
          call_sid: msg.data.callSid,
          from: jd.customer_phone,
          to: '',
          start_ts: Math.floor(Date.now() / 1000),
          end_ts: 0,
          duration_sec: 0,
          answered: true,
          answer_time_sec: 0,
        });
        setDrawerOpen(true);
        setHighlightActions(true);
        // Reset override mode when new job comes in
        setOverrideMode(false);
        setOverrideDate(null);
        
        addSystemAction('Job Created', `Generated job ticket for ${jd.service_type || 'service request'} - ready for your review`, 'pending');
      }
      if (msg?.type === 'appointment_confirmed' && msg.data) {
        const event = msg.data.event;
        setCalendarEvents((prev) => {
          // Remove any existing event with the same ID and add the new one
          const filtered = prev.filter(e => e.id !== event.id);
          return [...filtered, event];
        });
        addSystemAction('Appointment Confirmed', `Added ${event.customer_name}'s ${event.service_type} appointment to calendar`, 'completed');
      }
    },
    enabled: mounted,
  });

  // Auto-scroll transcripts panel to bottom on update
  useEffect(() => {
    transcriptRef.current?.scrollTo({ top: transcriptRef.current.scrollHeight, behavior: 'smooth' });
  }, [transcripts.length]);

  // Initial fetch + periodic polling fallback
  useEffect(() => {
    if (!mounted) return;
    
    // Add initial demo actions to show the feature working
    addSystemAction('Dashboard Started', 'Live operations dashboard is ready and monitoring all systems', 'completed');
    addSystemAction('WebSocket Connected', 'Real-time connection established for live updates', 'completed');
    
    const fetchMetrics = async () => {
      try {
        const res = await fetch('/api/live-metrics');
        if (res.ok) {
          const data = await res.json();
          setMetrics((prev) => ({ ...prev, ...data }));
        }
      } catch (_e) {}
    };
    fetchMetrics();
    const id = setInterval(fetchMetrics, 15000);
    return () => clearInterval(id);
  }, [mounted]);

  // Real-time log monitoring
  useEffect(() => {
    if (!mounted) return;
    
    const fetchLogs = async () => {
      try {
        const res = await fetch('/api/salon-dashboard');
        if (res.ok) {
          const data = await res.json();
          if (data.real_time) {
            setRecentCallEvents(data.real_time.recent_call_events || []);
            setLogActivity(data.real_time.log_activity || false);
            setLastLogUpdate(data.real_time.last_updated || '');
          }
        }
      } catch (_e) {}
    };
    
    fetchLogs();
    const logInterval = setInterval(fetchLogs, 5000); // Check logs every 5 seconds
    return () => clearInterval(logInterval);
  }, [mounted]);

  const { running: slaRunning, elapsedSec } = useSlaClock(metrics.activeCalls);
  const slaTarget = 20; // seconds target for SLA visual

  if (!mounted) {
    return (
      <div className="min-h-screen bg-background text-white p-6 space-y-6">
        <h1 className="text-xl font-semibold">Bold Wings Salon Dashboard</h1>
      </div>
    );
  }


  const latestSlaPct = metrics.sla && metrics.sla.length ? metrics.sla[metrics.sla.length - 1].value : null;

  const backendBase = process.env.NEXT_PUBLIC_BACKEND_HTTP || 'http://localhost:5001';
  const actionHeaders: HeadersInit = {};
  if (process.env.NEXT_PUBLIC_OPERATOR_API_KEY) {
    actionHeaders['x-api-key'] = process.env.NEXT_PUBLIC_OPERATOR_API_KEY;
  }

  async function callAction(path: string, body: any) {
    const res = await fetch(`${backendBase}${path}`, {
      method: 'POST',
      headers: { 'content-type': 'application/json', ...actionHeaders },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`${path} failed: ${res.status}`);
    return res.json().catch(() => ({}));
  }

  async function onApprove() {
    if (!selectedCall) return;
    
    addSystemAction('Approval Started', 'Processing your approval and scheduling appointment', 'in_progress');
    
    // Use job description time by default, or scheduler selection if in override mode
    let appointment_iso: string | undefined;
    
    if (overrideMode && overrideDate) {
      // Override mode: use operator-selected date (default to 9 AM)
      appointment_iso = new Date(
        Date.UTC(
          overrideDate.getFullYear(),
          overrideDate.getMonth(),
          overrideDate.getDate(),
          9, // Default to 9 AM
          0,
          0,
          0
        )
      ).toISOString();
    } else if (jobDesc?.appointment_time) {
      // Default: use the time from the job description
      appointment_iso = jobDesc.appointment_time;
    } else if (selectedDate) {
      // Fallback: use scheduler selection (default to 9 AM)
      appointment_iso = new Date(
        Date.UTC(
          selectedDate.getFullYear(),
          selectedDate.getMonth(),
          selectedDate.getDate(),
          9, // Default to 9 AM
          0,
          0,
          0
        )
      ).toISOString();
    }
    
    await callAction('/ops/action/approve', {
      call_sid: selectedCall.call_sid,
      appointment_iso,
      note: '',
    });
    
    addSystemAction('Job Approved', 'Appointment scheduled and customer will be notified automatically', 'completed');
    
    // Show CRM sync toast (Sheets mock/live runs server-side on approval)
    addSystemAction('CRM Sync', 'Customer information and appointment details saved to your CRM system', 'completed');
    setCrmToast(true);
    setTimeout(() => setCrmToast(false), 4000);
    
    setHighlightActions(false);
    setOverrideMode(false);
    setDrawerOpen(false);
  }

  async function onOverride() {
    if (!selectedCall) return;
    
    addSystemAction('Override Initiated', 'You are now customizing the appointment time', 'in_progress');
    
    // Mark as override in backend
    await callAction('/ops/action/override', {
      call_sid: selectedCall.call_sid,
      reason: 'operator override',
    });
    
    // Enable override mode to show date picker
    setOverrideMode(true);
    setOverrideDate(new Date()); // Default to today
    setHighlightActions(true);
  }

  async function onHandoff() {
    if (!selectedCall) return;
    addSystemAction('Handoff Requested', 'Transferring call to human operator for personal assistance', 'completed');
    await callAction('/ops/action/handoff', {
      call_sid: selectedCall.call_sid,
      reason: 'handoff to human',
    });
    setHighlightActions(false);
  }

  async function onDismiss() {
    // Simply close the drawer and clear the job description
    setDrawerOpen(false);
    setJobDesc(null);
    setHighlightActions(false);
    setOverrideMode(false);
    setOverrideDate(null);
  }

  const liveTranscripts = transcripts.filter(t => !selectedCall || t.callSid === selectedCall.call_sid);

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-900 via-pink-900 to-rose-900 text-white p-6 pb-28 space-y-4">
      {/* CRM Synced Toast */}
      <div
        className={cn(
          'fixed inset-0 z-50 flex items-center justify-center transition-all duration-300',
          crmToast ? 'opacity-100 scale-100' : 'opacity-0 scale-95 pointer-events-none'
        )}
      >
        <div className="pointer-events-auto flex items-center gap-3 rounded-md border border-emerald-400/40 bg-emerald-500/15 px-4 py-3 shadow-2xl backdrop-blur">
          <span className="text-emerald-300 text-lg">✅</span>
          <span className="text-sm font-semibold text-emerald-200">Synced to CRM</span>
        </div>
      </div>

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="text-3xl">💇‍♀️</div>
          <h1 className="text-2xl font-bold bg-gradient-to-r from-pink-300 via-purple-300 to-rose-300 bg-clip-text text-transparent">
            Bold Wings Salon Dashboard
          </h1>
        </div>
        <div className="flex items-center gap-2">
          <Badge className={wsProblem ? 'bg-red-400/30 text-red-200 border border-red-400/50' : 'bg-emerald-400/30 text-emerald-200 border border-emerald-400/50'}>
            {wsProblem ? '🔴 Disconnected' : '🟢 Live'}
          </Badge>
          <span className="text-xs text-pink-200/70">{new Date(metrics.timestamp).toLocaleTimeString()}</span>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-12 gap-4">
        {/* Left: Live Call / Inbox */}
        <div className="xl:col-span-3 space-y-4">
          <Card className="bg-gradient-to-br from-pink-500/10 to-purple-500/10 border-pink-300/20 backdrop-blur-sm">
            <CardHeader className="flex items-center justify-between">
              <CardTitle className="text-pink-200 flex items-center gap-2">
                📞 Live Call Panel
              </CardTitle>
              <div className="flex rounded-md overflow-hidden border border-pink-300/30">
                <button
                  className={`px-3 py-1 text-xs transition-colors ${leftTab === 'live' ? 'bg-pink-400/30 text-pink-200' : 'bg-transparent hover:bg-pink-400/20 text-pink-300'}`}
                  onClick={() => setLeftTab('live')}
                >
                  Live Call
                </button>
                <button
                  className={`px-3 py-1 text-xs transition-colors ${leftTab === 'inbox' ? 'bg-pink-400/30 text-pink-200' : 'bg-transparent hover:bg-pink-400/20 text-pink-300'}`}
                  onClick={() => setLeftTab('inbox')}
                >
                  Inbox
                </button>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              {leftTab === 'live' ? (
                <div className="space-y-3">
                  <div className="flex items-center justify-between text-sm text-white/70">
                    <div>Active Calls</div>
                    <div className="font-semibold text-white">{metrics.activeCalls}</div>
                  </div>
                  <div ref={transcriptRef} className="h-64 rounded border border-white/10 bg-black/20 p-3 overflow-y-auto scrollbar-hide text-sm space-y-2">
                    {liveTranscripts.length === 0 ? (
                      <div className="text-white/50">Waiting for real-time transcriptions…</div>
                    ) : (
                      liveTranscripts.map((t, idx) => (
                        <div key={idx} className="flex items-start gap-2">
                          <span className="text-xs text-white/50">[{new Date(t.ts).toLocaleTimeString()}]</span>
                          {t.intent && (
                            <span className={`text-xs px-2 py-1 rounded-full font-medium ${getIntentColor(t.intent)}`}>
                              {formatIntentTag(t.intent)}
                            </span>
                          )}
                          <span className="text-white/90 flex-1">{t.text}</span>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              ) : (
                <div className="space-y-3">
                  <div className="text-sm text-white/70">Conversations Inbox</div>
                  <div className="h-64 overflow-y-auto scrollbar-hide">
                    <Table>
                      <THead>
                        <TR>
                          <TH>Call SID</TH>
                          <TH>From</TH>
                          <TH>To</TH>
                          <TH>Answered</TH>
                        </TR>
                      </THead>
                      <TBody>
                        {metrics.recentCalls?.map((c) => (
                          <TR key={c.call_sid} className="cursor-pointer" onClick={() => setSelectedCall(c)}>
                            <TD className="truncate max-w-[10rem]" title={c.call_sid}>{c.call_sid}</TD>
                            <TD>{c.from || '-'}</TD>
                            <TD>{c.to || '-'}</TD>
                            <TD>{c.answered ? 'Yes' : 'No'}</TD>
                          </TR>
                        ))}
                      </TBody>
                    </Table>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Center: Scheduler */}
        <div className="xl:col-span-6 space-y-4">
          <Card className="bg-gradient-to-br from-purple-500/10 to-rose-500/10 border-purple-300/20 backdrop-blur-sm">
            <CardHeader>
              <CardTitle className="text-purple-200 flex items-center gap-2">
                📅 Appointment Scheduler
              </CardTitle>
            </CardHeader>
            <CardContent>
              <FullCalendarComponent 
                date={selectedDate ?? undefined} 
                onSelect={(d) => { setSelectedDate(d); }} 
                events={calendarEvents}
              />
            </CardContent>
          </Card>
        </div>

        {/* Right: Job Ticket */}
        <div className="xl:col-span-3 space-y-4">
          <Card className="bg-gradient-to-br from-rose-500/10 to-pink-500/10 border-rose-300/20 backdrop-blur-sm">
            <CardHeader className="flex items-center justify-between">
              <CardTitle className="text-rose-200 flex items-center gap-2">
                ✨ Service Ticket
              </CardTitle>
              <div className="flex rounded-md overflow-hidden border border-rose-300/30">
                <button
                  className={`px-3 py-1 text-xs transition-colors ${rightTab === 'details' ? 'bg-rose-400/30 text-rose-200' : 'bg-transparent hover:bg-rose-400/20 text-rose-300'}`}
                  onClick={() => setRightTab('details')}
                >
                  Details
                </button>
                <button
                  className={`px-3 py-1 text-xs transition-colors ${rightTab === 'notes' ? 'bg-rose-400/30 text-rose-200' : 'bg-transparent hover:bg-rose-400/20 text-rose-300'}`}
                  onClick={() => setRightTab('notes')}
                >
                  Notes
                </button>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              {rightTab === 'details' ? (
                <div className="space-y-3 text-sm">
                  {selectedCall ? (
                    <>
                      <div className="flex items-center justify-between"><div className="text-white/70">Call SID</div><div className="text-white/90 truncate max-w-[10rem]" title={selectedCall.call_sid}>{selectedCall.call_sid}</div></div>
                      <div className="flex items-center justify-between"><div className="text-white/70">From</div><div className="text-white/90">{selectedCall.from || '-'}</div></div>
                      <div className="flex items-center justify-between"><div className="text-white/70">To</div><div className="text-white/90">{selectedCall.to || '-'}</div></div>
                      <div className="flex items-center justify-between"><div className="text-white/70">Start</div><div className="text-white/90">{new Date(selectedCall.start_ts * 1000).toLocaleString()}</div></div>
                      <div className="flex items-center justify-between"><div className="text-white/70">End</div><div className="text-white/90">{new Date(selectedCall.end_ts * 1000).toLocaleString()}</div></div>
                      <div className="flex items-center justify-between"><div className="text-white/70">Duration</div><div className="text-white/90">{formatTime(selectedCall.duration_sec)}</div></div>
                      {selectedDate && (
                        <div className="flex items-center justify-between"><div className="text-white/70">Scheduled</div><div className="text-white/90">{selectedDate.toDateString()} @ 9:00 AM</div></div>
                      )}
                    </>
                  ) : (
                    <div className="text-white/60">Select a conversation from Inbox to populate ticket.</div>
                  )}
                </div>
              ) : (
                <div className="space-y-2">
                  <div className="text-sm text-white/70">Notes</div>
                  <div className="h-40 rounded border border-white/10 bg-black/20 p-3 text-sm text-white/80">
                    Add operator notes here.
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
          
          {/* Action Audit */}
          <Card className="bg-gradient-to-br from-violet-500/10 to-fuchsia-500/10 border-violet-300/20 backdrop-blur-sm">
            <CardHeader>
              <CardTitle className="text-sm text-violet-200 flex items-center gap-2">
                📋 Activity Log
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <div className="h-48 overflow-y-auto scrollbar-hide space-y-2">
                {systemActions.length === 0 ? (
                  <div className="text-xs text-white/50 text-center py-4">
                    System actions will appear here as they happen
                  </div>
                ) : (
                  systemActions.map((action) => (
                    <div key={action.id} className="flex items-start gap-2 text-xs">
                      <div className="flex-shrink-0 mt-0.5">
                        {action.status === 'completed' && <span className="text-green-400">✓</span>}
                        {action.status === 'in_progress' && <span className="text-yellow-400">⏳</span>}
                        {action.status === 'pending' && <span className="text-blue-400">⏸</span>}
                      </div>
                      <div className="flex-1 space-y-0.5">
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-white/90">{action.action}</span>
                          <span className="text-white/40">
                            {new Date(action.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                          </span>
                        </div>
                        <div className="text-white/70 leading-tight">
                          {action.description}
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </CardContent>
          </Card>

          {/* Real-time Call Logs */}
          <Card className="bg-gradient-to-br from-amber-500/10 to-orange-500/10 border-amber-300/20 backdrop-blur-sm">
            <CardHeader>
              <CardTitle className="text-sm text-amber-200 flex items-center gap-2">
                📞 Real-time Call Logs
                {logActivity && (
                  <Badge className="bg-green-500/30 text-green-200 border-green-400/50 text-xs">
                    Live
                  </Badge>
                )}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <div className="h-48 overflow-y-auto scrollbar-hide space-y-2">
                {recentCallEvents.length === 0 ? (
                  <div className="text-xs text-white/50 text-center py-4">
                    Call events will appear here in real-time
                  </div>
                ) : (
                  recentCallEvents.map((event, index) => {
                    // Ensure event has required properties
                    const eventType = event?.event_type || 'UNKNOWN';
                    const callSid = event?.call_sid || 'Unknown';
                    const timestamp = event?.timestamp || new Date().toISOString();
                    const message = event?.message || 'Event logged';
                    
                    return (
                      <div key={index} className="flex items-start gap-2 text-xs">
                        <div className="flex-shrink-0 mt-0.5">
                          {eventType === 'INITIATED' && <span className="text-blue-400">📞</span>}
                          {eventType === 'ROUTING' && <span className="text-yellow-400">🔄</span>}
                          {eventType === 'ANSWERED' && <span className="text-green-400">✅</span>}
                          {eventType === 'MISSED' && <span className="text-red-400">❌</span>}
                          {eventType === 'COMPLETED' && <span className="text-emerald-400">✓</span>}
                          {eventType === 'STATUS_CHANGE' && <span className="text-purple-400">📊</span>}
                          {!['INITIATED', 'ROUTING', 'ANSWERED', 'MISSED', 'COMPLETED', 'STATUS_CHANGE'].includes(eventType) && (
                            <span className="text-gray-400">📝</span>
                          )}
                        </div>
                        <div className="flex-1 space-y-0.5">
                          <div className="flex items-center gap-2">
                            <span className="font-medium text-white/90">{eventType}</span>
                            <span className="text-white/40">
                              {new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                            </span>
                          </div>
                          <div className="text-white/70 leading-tight text-xs">
                            Call {callSid} - {typeof message === 'string' ? message.split(' - ').pop() || 'Event logged' : 'Event logged'}
                          </div>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
              {lastLogUpdate && (
                <div className="text-xs text-white/40 text-center pt-2 border-t border-white/10">
                  Last updated: {new Date(lastLogUpdate).toLocaleTimeString()}
                </div>
              )}
            </CardContent>
          </Card>
          
          {/* Quick Stats */}
          <Card className="bg-gradient-to-br from-emerald-500/10 to-teal-500/10 border-emerald-300/20 backdrop-blur-sm">
            <CardContent className="grid grid-cols-2 gap-3 p-3 text-center">
              <div>
                <div className="text-xs text-emerald-200/80">Total Calls</div>
                <div className="text-lg font-semibold text-emerald-300">{typeof metrics.totalCalls === 'number' ? metrics.totalCalls : 0}</div>
              </div>
              <div>
                <div className="text-xs text-teal-200/80">Answered</div>
                <div className="text-lg font-semibold text-teal-300">{typeof metrics.answeredCalls === 'number' ? metrics.answeredCalls : 0}</div>
              </div>
              <div>
                <div className="text-xs text-cyan-200/80">Missed</div>
                <div className="text-lg font-semibold text-cyan-300">{typeof metrics.abandonedCalls === 'number' ? metrics.abandonedCalls : 0}</div>
              </div>
              <div>
                <div className="text-xs text-emerald-200/80">Service Rate</div>
                <div className="text-lg font-semibold text-emerald-300">{typeof latestSlaPct === 'number' ? `${latestSlaPct}%` : '-'}</div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Bottom sticky response time clock */}
      <div className="fixed bottom-0 left-0 right-0 border-t border-pink-300/20 bg-gradient-to-r from-purple-900/80 via-pink-900/80 to-rose-900/80 backdrop-blur-xl p-3">
        <div className="mx-auto max-w-7xl flex items-center justify-end gap-3">
          <div className="flex items-center gap-3 text-sm">
            <div className="text-pink-200/80">⏱️ Response Time</div>
            <div className={`px-3 py-1 rounded-full font-mono ${slaRunning ? (elapsedSec > slaTarget ? 'bg-red-400/30 text-red-200 border border-red-400/50' : 'bg-emerald-400/30 text-emerald-200 border border-emerald-400/50') : 'bg-pink-400/20 text-pink-200/80 border border-pink-400/30'}`}>
              {formatTime(elapsedSec)} / 02:00
            </div>
          </div>
        </div>
      </div>

      {/* Bottom Drawer */}
      <div
        className={cn(
          'fixed left-0 right-0 bottom-0 transition-transform duration-300 ease-out',
          drawerOpen ? 'translate-y-0' : 'translate-y-full'
        )}
      >
        <div className="mx-auto max-w-3xl rounded-t-xl border border-pink-300/30 bg-gradient-to-r from-purple-900/90 via-pink-900/90 to-rose-900/90 backdrop-blur-xl p-4">
          <div className="flex items-center justify-between">
            <div className="text-sm text-pink-200/80 flex items-center gap-2">
              ✨ Service Description
            </div>
            <button className="text-white/60 hover:text-white/90 text-sm" onClick={() => setDrawerOpen(false)}>Close</button>
          </div>
          {jobDesc ? (
            <div className="mt-3 text-center space-y-1">
              <div className="text-lg font-semibold text-white">{jobDesc.service_type}</div>
              <div className="text-white/90">Customer • {jobDesc.customer_phone || '+19404656984'}</div>
              <div className="text-white/80">{new Date(jobDesc.appointment_time).toLocaleString()}</div>
              {jobDesc.address ? <div className="text-white/70">{jobDesc.address}</div> : <div className="text-white/70">DENTON, TX</div>}
              {jobDesc.notes ? <div className="text-white/60 text-sm mt-2">{jobDesc.notes}</div> : null}
            </div>
          ) : (
            <div className="mt-3 text-center text-white/60">Waiting for job details…</div>
          )}
          {overrideMode && (
            <div className="mt-4 space-y-4">
              <div className="text-sm text-white/70 text-center">Select New Appointment Date</div>
              <div className="flex justify-center">
                <div className="w-full max-w-md">
                  <FullCalendarComponent 
                    date={overrideDate ?? new Date()} 
                    onSelect={(d) => { setOverrideDate(d); }} 
                  />
                </div>
              </div>
            </div>
          )}
          <div className="mt-4 flex items-center justify-center gap-3">
            <Button onClick={onDismiss} className="bg-pink-500/20 text-pink-200 hover:bg-pink-500/30 border border-pink-400/30">
              Dismiss
            </Button>
            <Button 
              onClick={onApprove}
              disabled={overrideMode && !overrideDate}
              className={cn(
                'bg-emerald-500/30 text-emerald-200 hover:bg-emerald-500/40 border border-emerald-400/50',
                highlightActions ? 'ring-2 ring-emerald-300 shadow-[0_0_20px_rgba(52,211,153,0.4)]' : ''
              )}
            >
              {overrideMode ? '✨ Approve Override' : '✨ Approve'}
            </Button>
            {!overrideMode && (
              <Button
                onClick={onOverride}
                className={cn(
                  'bg-amber-400/30 text-amber-200 hover:bg-amber-400/40 border border-amber-400/50', 
                  highlightActions ? 'ring-2 ring-amber-300 shadow-[0_0_20px_rgba(252,211,77,0.4)]' : ''
                )}
              >
                🔄 Override
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
