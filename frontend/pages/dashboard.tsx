import { useEffect, useMemo, useState } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Table, THead, TBody, TR, TH, TD } from '@/components/ui/table';
import { useWebSocket } from '@/hooks/useWebSocket';
import { useIsMounted } from '@/hooks/useIsMounted';

const pieColors = ['#1f77b4', '#2ca02c', '#ff7f0e', '#9467bd', '#8c564b', '#e377c2', '#d62728'];

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

function formatPercent(n: number) {
  if (!isFinite(n)) return '0%';
  return `${Math.round(n)}%`;
}

function formatTime(sec: number) {
  const s = Math.max(0, Math.floor(sec));
  const m = Math.floor(s / 60);
  const rem = s % 60;
  return `${String(m).padStart(2, '0')}:${String(rem).padStart(2, '0')}`;
}

export default function LiveOpsDashboard() {
  const mounted = useIsMounted();
  const [metrics, setMetrics] = useState<MetricsSnapshot>(defaultMetrics);
  const [wsProblem, setWsProblem] = useState<string | null>(null);

  const wsUrl = useMemo(() => {
    if (typeof window === 'undefined') return null;
    const env = process.env.NEXT_PUBLIC_BACKEND_WS;
    if (env) return env;
    const host = window.location.hostname;
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
    return `${proto}://${host}:5001/ops`;
  }, []);

  useWebSocket<{ type: string; data?: MetricsSnapshot }>(wsUrl, {
    onOpen: () => setWsProblem(null),
    onError: () => setWsProblem('WebSocket connection issue'),
    onMessage: (msg) => {
      if (msg?.type === 'metrics' && msg.data) {
        setMetrics((prev) => ({ ...prev, ...msg.data }));
      }
    },
    enabled: mounted,
  });

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
      } catch (_e) {
        // ignore
      }
    };
    fetchMetrics();
    const id = setInterval(fetchMetrics, 15000);
    return () => clearInterval(id);
  }, [mounted]);

  const csat = metrics.csat && metrics.csat.length > 0 ? metrics.csat : [
    { name: 'Satisfied', value: 4 },
    { name: 'Neutral', value: 2 },
    { name: 'Dissatisfied', value: 1 },
  ];

  if (!mounted) {
    // Render deterministic shell to avoid SSR/CSR mismatch
    return (
      <div className="min-h-screen bg-background text-white p-6 space-y-6">
        <h1 className="text-xl font-semibold">Live Ops Dashboard</h1>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background text-white p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Live Ops Dashboard</h1>
        <div className="flex items-center gap-2">
          <Badge className={wsProblem ? 'bg-red-500/20 text-red-300' : 'bg-green-500/20 text-green-300'}>
            {wsProblem ? 'Disconnected' : 'Live'}
          </Badge>
          <span className="text-xs text-white/50">{new Date(metrics.timestamp).toLocaleTimeString()}</span>
        </div>
      </div>

      {/* Top Stats */}
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="text-xs text-white/60">Active Calls</div>
            <div className="text-2xl font-bold">{metrics.activeCalls}</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="text-xs text-white/60">Total Calls</div>
            <div className="text-2xl font-bold">{metrics.totalCalls}</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="text-xs text-white/60">Answered</div>
            <div className="text-2xl font-bold">{metrics.answeredCalls}</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="text-xs text-white/60">Abandoned</div>
            <div className="text-2xl font-bold">{metrics.abandonedCalls}</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="text-xs text-white/60">AHT</div>
            <div className="text-2xl font-bold">{metrics.aht || formatTime(metrics.ahtSec)}</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="text-xs text-white/60">Avg Wait</div>
            <div className="text-2xl font-bold">{metrics.avgWait || formatTime(metrics.avgWaitSec)}</div>
          </CardContent>
        </Card>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>SLA (Answered within 20s, last hour)</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={metrics.sla || []}>
                  <XAxis dataKey="date" stroke="#9CA3AF"/>
                  <YAxis stroke="#9CA3AF" tickFormatter={(v) => `${v}%`} domain={[0, 100]} />
                  <Tooltip formatter={(v: number) => `${v}%`} />
                  <Bar dataKey="value" fill="#00D1FF" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>CSAT</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={csat} dataKey="value" nameKey="name" outerRadius={90} label>
                    {csat.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={pieColors[index % pieColors.length]} />
                    ))}
                  </Pie>
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Recent Calls */}
      <Card>
        <CardHeader>
          <CardTitle>Recent Calls</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <THead>
              <TR>
                <TH>Call SID</TH>
                <TH>From</TH>
                <TH>To</TH>
                <TH>Start</TH>
                <TH>End</TH>
                <TH>Duration</TH>
                <TH>Answered</TH>
              </TR>
            </THead>
            <TBody>
              {metrics.recentCalls?.map((c) => (
                <TR key={c.call_sid}>
                  <TD>{c.call_sid}</TD>
                  <TD>{c.from || '-'}</TD>
                  <TD>{c.to || '-'}</TD>
                  <TD>{new Date(c.start_ts * 1000).toLocaleString()}</TD>
                  <TD>{new Date(c.end_ts * 1000).toLocaleString()}</TD>
                  <TD>{formatTime(c.duration_sec)}</TD>
                  <TD>{c.answered ? 'Yes' : 'No'}</TD>
                </TR>
              ))}
            </TBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
} 