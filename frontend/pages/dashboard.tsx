import { useEffect, useMemo, useState, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Table, THead, TBody, TR, TH, TD } from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { useWebSocket } from '@/hooks/useWebSocket';
import { useIsMounted } from '@/hooks/useIsMounted';
import { cn } from '@/lib/utils';

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

function MiniCalendar({ date = new Date(), onSelect }: { date?: Date; onSelect?: (d: Date) => void }) {
  const year = date.getFullYear();
  const month = date.getMonth();
  const firstDay = new Date(year, month, 1);
  const startDay = firstDay.getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const days: Array<Date | null> = [];
  for (let i = 0; i < startDay; i++) days.push(null);
  for (let d = 1; d <= daysInMonth; d++) days.push(new Date(year, month, d));
  while (days.length % 7 !== 0) days.push(null);

  const weekdays = ['S', 'M', 'T', 'W', 'T', 'F', 'S'];

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <div className="text-sm text-white/80">
          {date.toLocaleString(undefined, { month: 'long' })} {year}
        </div>
      </div>
      <div className="grid grid-cols-7 text-center text-xs text-white/50">
        {weekdays.map((w) => (
          <div key={w} className="py-1">{w}</div>
        ))}
      </div>
      <div className="grid grid-cols-7 gap-1">
        {days.map((d, idx) => (
          <button
            key={idx}
            className={`h-8 rounded text-xs ${d ? 'hover:bg-white/10 text-white/90' : 'opacity-30 cursor-default'}`}
            onClick={() => d && onSelect?.(d)}
            disabled={!d}
          >
            {d ? d.getDate() : ''}
          </button>
        ))}
      </div>
    </div>
  );
}

function generateTimeSlots(from: Date, count: number): Date[] {
  const slots: Date[] = [];
  const start = new Date(from);
  start.setSeconds(0, 0);
  const minute = start.getMinutes();
  start.setMinutes(minute + (minute % 30 === 0 ? 0 : 30 - (minute % 30)));
  for (let i = 0; i < count; i++) {
    slots.push(new Date(start.getTime() + i * 30 * 60 * 1000));
  }
  return slots;
}

export default function LiveOpsDashboard() {
  const mounted = useIsMounted();
  const [metrics, setMetrics] = useState<MetricsSnapshot>(defaultMetrics);
  const [wsProblem, setWsProblem] = useState<string | null>(null);

  const [leftTab, setLeftTab] = useState<'live' | 'inbox'>('live');
  const [rightTab, setRightTab] = useState<'details' | 'notes'>('details');
  const [selectedCall, setSelectedCall] = useState<RecentCall | null>(null);
  const [selectedDate, setSelectedDate] = useState<Date | null>(new Date());
  const [selectedSlot, setSelectedSlot] = useState<Date | null>(null);

  const transcriptRef = useRef<HTMLDivElement | null>(null);
  const [transcripts, setTranscripts] = useState<Array<{ callSid: string; text: string; intent?: string; ts: string }>>([]);
  const [activeCallSids, setActiveCallSids] = useState<string[]>([]);

  const wsUrl = useMemo(() => {
    if (typeof window === 'undefined') return null;
    const env = process.env.NEXT_PUBLIC_BACKEND_WS;
    if (env) return env;
    const host = window.location.hostname;
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
    return `${proto}://${host}:5001/ops`;
  }, []);

  // Bottom drawer state for job description
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
  const [overrideSlot, setOverrideSlot] = useState<Date | null>(null);

  // Helper functions for intent display
  const getIntentColor = (intent: string): string => {
    const colors: Record<string, string> = {
      EMERGENCY_FIX: 'bg-red-500/20 text-red-300 border border-red-500/30',
      CLOG_BLOCKAGE: 'bg-yellow-500/20 text-yellow-300 border border-yellow-500/30',
      LEAKING_FIXTURE: 'bg-blue-500/20 text-blue-300 border border-blue-500/30',
      INSTALL_REQUEST: 'bg-green-500/20 text-green-300 border border-green-500/30',
      WATER_HEATER_ISSUE: 'bg-orange-500/20 text-orange-300 border border-orange-500/30',
      QUOTE_REQUEST: 'bg-purple-500/20 text-purple-300 border border-purple-500/30',
      REMODEL_INQUIRY: 'bg-pink-500/20 text-pink-300 border border-pink-500/30',
      RECURRING_PROBLEM: 'bg-amber-500/20 text-amber-300 border border-amber-500/30',
      DRAIN_MAINTENANCE: 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30',
      GENERAL_INQUIRY: 'bg-gray-500/20 text-gray-300 border border-gray-500/30',
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
        setActiveCallSids(Array.from(active));
        // Note: Don't clear transcripts here - only clear when full conversation ends
        // Individual call ends don't mean the full conversation is over
      }
      if (msg?.type === 'transcript' && msg.data) {
        setTranscripts((prev) => [...prev.slice(-199), msg.data]);
      }
      if (msg?.type === 'conversation_ended' && msg.data?.callSid) {
        // Clear transcripts only when full conversation ends
        setTranscripts((prev) => prev.filter(t => t.callSid !== msg.data.callSid));
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
        setOverrideSlot(null);
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

  const { running: slaRunning, elapsedSec } = useSlaClock(metrics.activeCalls);
  const slaTarget = 20; // seconds target for SLA visual

  if (!mounted) {
    return (
      <div className="min-h-screen bg-background text-white p-6 space-y-6">
        <h1 className="text-xl font-semibold">Live Ops Dashboard</h1>
      </div>
    );
  }

  const slotOptions = generateTimeSlots(selectedDate ?? new Date(), 8);
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
    
    // Use job description time by default, or scheduler selection if in override mode
    let appointment_iso: string | undefined;
    
    if (overrideMode && overrideDate && overrideSlot) {
      // Override mode: use operator-selected time
      appointment_iso = new Date(
        Date.UTC(
          overrideDate.getFullYear(),
          overrideDate.getMonth(),
          overrideDate.getDate(),
          overrideSlot.getHours(),
          overrideSlot.getMinutes(),
          0,
          0
        )
      ).toISOString();
    } else if (jobDesc?.appointment_time) {
      // Default: use the time from the job description
      appointment_iso = jobDesc.appointment_time;
    } else if (selectedDate && selectedSlot) {
      // Fallback: use scheduler selection
      appointment_iso = new Date(
        Date.UTC(
          selectedDate.getFullYear(),
          selectedDate.getMonth(),
          selectedDate.getDate(),
          selectedSlot.getHours(),
          selectedSlot.getMinutes(),
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
    
    setHighlightActions(false);
    setOverrideMode(false);
    setDrawerOpen(false);
  }

  async function onOverride() {
    if (!selectedCall) return;
    
    // Mark as override in backend
    await callAction('/ops/action/override', {
      call_sid: selectedCall.call_sid,
      reason: 'operator override',
    });
    
    // Enable override mode to show date/time picker
    setOverrideMode(true);
    setOverrideDate(new Date()); // Default to today
    setOverrideSlot(null);
    setHighlightActions(true);
  }

  async function onHandoff() {
    if (!selectedCall) return;
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
    setOverrideSlot(null);
  }

  const liveTranscripts = transcripts.filter(t => !selectedCall || t.callSid === selectedCall.call_sid);

  return (
    <div className="min-h-screen bg-background text-white p-6 pb-28 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Live Ops Dashboard</h1>
        <div className="flex items-center gap-2">
          <Badge className={wsProblem ? 'bg-red-500/20 text-red-300' : 'bg-green-500/20 text-green-300'}>
            {wsProblem ? 'Disconnected' : 'Live'}
          </Badge>
          <span className="text-xs text-white/50">{new Date(metrics.timestamp).toLocaleTimeString()}</span>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-12 gap-4">
        {/* Left: Live Call / Inbox */}
        <div className="xl:col-span-3 space-y-4">
          <Card>
            <CardHeader className="flex items-center justify-between">
              <CardTitle>Live Call Panel</CardTitle>
              <div className="flex rounded-md overflow-hidden border border-white/10">
                <button
                  className={`px-3 py-1 text-xs ${leftTab === 'live' ? 'bg-white/10' : 'bg-transparent hover:bg-white/5'}`}
                  onClick={() => setLeftTab('live')}
                >
                  Live Call
                </button>
                <button
                  className={`px-3 py-1 text-xs ${leftTab === 'inbox' ? 'bg-white/10' : 'bg-transparent hover:bg-white/5'}`}
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
          <Card>
            <CardHeader>
              <CardTitle>Scheduler</CardTitle>
            </CardHeader>
            <CardContent className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <MiniCalendar date={selectedDate ?? undefined} onSelect={(d) => { setSelectedDate(d); setSelectedSlot(null); }} />
              </div>
              <div className="space-y-3">
                <div className="text-sm text-white/70">Suggested Time Slots</div>
                <div className="grid grid-cols-2 gap-2">
                  {slotOptions.map((d) => {
                    const label = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                    const selected = selectedSlot && d.getTime() === selectedSlot.getTime();
                    return (
                      <button
                        key={d.getTime()}
                        onClick={() => setSelectedSlot(d)}
                        className={`px-3 py-2 rounded border text-sm ${selected ? 'border-accent bg-accent/20 text-white' : 'border-white/10 hover:bg-white/5 text-white/90'}`}
                      >
                        {label}
                      </button>
                    );
                  })}
                </div>
                {selectedDate && selectedSlot && (
                  <div className="text-xs text-white/70">Selected: {selectedDate.toDateString()} @ {selectedSlot.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</div>
                )}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Right: Job Ticket */}
        <div className="xl:col-span-3 space-y-4">
          <Card>
            <CardHeader className="flex items-center justify-between">
              <CardTitle>Job Ticket</CardTitle>
              <div className="flex rounded-md overflow-hidden border border-white/10">
                <button
                  className={`px-3 py-1 text-xs ${rightTab === 'details' ? 'bg-white/10' : 'bg-transparent hover:bg-white/5'}`}
                  onClick={() => setRightTab('details')}
                >
                  Details
                </button>
                <button
                  className={`px-3 py-1 text-xs ${rightTab === 'notes' ? 'bg-white/10' : 'bg-transparent hover:bg-white/5'}`}
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
                      {selectedSlot && selectedDate && (
                        <div className="flex items-center justify-between"><div className="text-white/70">Scheduled</div><div className="text-white/90">{selectedDate.toDateString()} @ {selectedSlot.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</div></div>
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
          {/* Quick Stats */}
          <Card>
            <CardContent className="grid grid-cols-2 gap-3 p-3 text-center">
              <div>
                <div className="text-xs text-white/60">Total</div>
                <div className="text-lg font-semibold">{metrics.totalCalls}</div>
              </div>
              <div>
                <div className="text-xs text-white/60">Answered</div>
                <div className="text-lg font-semibold">{metrics.answeredCalls}</div>
              </div>
              <div>
                <div className="text-xs text-white/60">Abandoned</div>
                <div className="text-lg font-semibold">{metrics.abandonedCalls}</div>
              </div>
              <div>
                <div className="text-xs text-white/60">SLA</div>
                <div className="text-lg font-semibold">{latestSlaPct !== null ? `${latestSlaPct}%` : '-'}</div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Bottom sticky SLA clock */}
      <div className="fixed bottom-0 left-0 right-0 border-t border-white/10 bg-black/40 backdrop-blur p-3">
        <div className="mx-auto max-w-7xl flex items-center justify-end gap-3">
          <div className="flex items-center gap-3 text-sm">
            <div className="text-white/70">SLA Clock</div>
            <div className={`px-2 py-1 rounded font-mono ${slaRunning ? (elapsedSec > slaTarget ? 'bg-red-500/20 text-red-300' : 'bg-green-500/20 text-green-300') : 'bg-white/10 text-white/80'}`}>
              {formatTime(elapsedSec)} / 00:20
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
        <div className="mx-auto max-w-3xl rounded-t-xl border border-white/10 bg-black/80 backdrop-blur p-4">
          <div className="flex items-center justify-between">
            <div className="text-sm text-white/70">Job Description</div>
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
              <div className="text-sm text-white/70 text-center">Select New Appointment Time</div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <MiniCalendar 
                    date={overrideDate ?? new Date()} 
                    onSelect={(d) => { setOverrideDate(d); setOverrideSlot(null); }} 
                  />
                </div>
                <div className="space-y-3">
                  <div className="text-sm text-white/70">Available Time Slots</div>
                  <div className="grid grid-cols-2 gap-2">
                    {generateTimeSlots(overrideDate ?? new Date(), 8).map((d) => {
                      const label = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                      const selected = overrideSlot && d.getTime() === overrideSlot.getTime();
                      return (
                        <button
                          key={d.getTime()}
                          onClick={() => setOverrideSlot(d)}
                          className={`px-3 py-2 rounded border text-sm ${selected ? 'border-accent bg-accent/20 text-white' : 'border-white/10 hover:bg-white/5 text-white/90'}`}
                        >
                          {label}
                        </button>
                      );
                    })}
                  </div>
                  {overrideDate && overrideSlot && (
                    <div className="text-xs text-white/70">Selected: {overrideDate.toDateString()} @ {overrideSlot.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</div>
                  )}
                </div>
              </div>
            </div>
          )}
          <div className="mt-4 flex items-center justify-center gap-3">
            <Button onClick={onDismiss} className="bg-white/10 text-white hover:opacity-90">Dismiss</Button>
            <Button 
              onClick={onApprove}
              disabled={overrideMode && (!overrideDate || !overrideSlot)}
              className={highlightActions ? 'ring-2 ring-green-300 shadow-[0_0_20px_rgba(74,222,128,0.4)]' : ''}
            >
              {overrideMode ? 'Approve Override' : 'Approve'}
            </Button>
            {!overrideMode && (
              <Button
                onClick={onOverride}
                className={cn('bg-yellow-400 text-black hover:opacity-90', highlightActions ? 'ring-2 ring-yellow-300 shadow-[0_0_20px_rgba(250,204,21,0.35)]' : '')}
              >
                Override
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
} 