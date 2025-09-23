import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Phone, Calendar, TrendingUp, DollarSign, Wifi, WifiOff } from "lucide-react";
import type { KPIs } from "@/types/salon";

interface KpiCardsProps {
  kpis: KPIs;
  isLiveConnected?: boolean;
  liveCallEvents?: Array<{ timestamp: string; call_sid: string }>;
  liveAppointments?: Array<{ estimated_revenue_cents: number; timestamp: string }>;
}

export function KpiCards({ kpis, isLiveConnected = false, liveCallEvents = [], liveAppointments = [] }: KpiCardsProps) {
  const formatCurrency = (cents: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(cents / 100);
  };

  const formatPercentage = (rate: number) => {
    return `${(rate * 100).toFixed(1)}%`;
  };

  // Calculate live stats for today
  const today = new Date().toDateString();
  const liveCalls = liveCallEvents.filter(call => 
    new Date(call.timestamp).toDateString() === today
  );
  const liveBookings = liveAppointments.filter(apt => 
    new Date(apt.timestamp).toDateString() === today
  );
  const liveRevenue = liveBookings.reduce((sum, apt) => sum + apt.estimated_revenue_cents, 0);

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      <Card className="shadow-card">
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Revenue Recovered</CardTitle>
          <div className="flex items-center gap-2">
            <DollarSign className="h-4 w-4 text-primary" />
            {isLiveConnected && (
              <Badge variant="outline" className="text-xs bg-green-50 text-green-700 border-green-200">
                <Wifi className="w-3 h-3 mr-1" />
                Live
              </Badge>
            )}
          </div>
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold text-primary">
            {formatCurrency(kpis.revenueRecovered)}
          </div>
          <div className="flex items-center justify-between">
            <p className="text-xs text-muted-foreground">This month</p>
            {liveRevenue > 0 && (
              <p className="text-xs text-green-600 font-medium">
                +{formatCurrency(liveRevenue)} today
              </p>
            )}
          </div>
        </CardContent>
      </Card>

      <Card className="shadow-card">
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Calls Answered</CardTitle>
          <div className="flex items-center gap-2">
            <Phone className="h-4 w-4 text-muted-foreground" />
            {liveCalls.length > 0 && (
              <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
            )}
          </div>
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{kpis.callsAnswered.toLocaleString()}</div>
          <div className="flex items-center justify-between">
            <p className="text-xs text-muted-foreground">Total calls handled</p>
            {liveCalls.length > 0 && (
              <p className="text-xs text-blue-600 font-medium">
                +{liveCalls.length} today
              </p>
            )}
          </div>
        </CardContent>
      </Card>

      <Card className="shadow-card">
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Appointments Booked</CardTitle>
          <div className="flex items-center gap-2">
            <Calendar className="h-4 w-4 text-muted-foreground" />
            {liveBookings.length > 0 && (
              <div className="w-2 h-2 bg-orange-500 rounded-full animate-pulse" />
            )}
          </div>
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{kpis.appointmentsBooked.toLocaleString()}</div>
          <div className="flex items-center justify-between">
            <p className="text-xs text-muted-foreground">From AI calls</p>
            {liveBookings.length > 0 && (
              <p className="text-xs text-orange-600 font-medium">
                +{liveBookings.length} today
              </p>
            )}
          </div>
        </CardContent>
      </Card>

      <Card className="shadow-card">
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Conversion Rate</CardTitle>
          <div className="flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
            {!isLiveConnected && (
              <WifiOff className="h-3 w-3 text-gray-400" />
            )}
          </div>
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{formatPercentage(kpis.conversionRate)}</div>
          <div className="flex items-center justify-between">
            <p className="text-xs text-muted-foreground">Calls to bookings</p>
            {liveCalls.length > 0 && liveBookings.length > 0 && (
              <p className="text-xs text-purple-600 font-medium">
                {formatPercentage(liveBookings.length / liveCalls.length)} today
              </p>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}