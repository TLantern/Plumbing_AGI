import { useState } from "react";
import { SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { DashboardSidebar } from "@/components/dashboard/DashboardSidebar";
import { KpiCards } from "@/components/salon/KpiCards";
import { CallsChart } from "@/components/salon/CallsChart";
import { RevenueChart } from "@/components/salon/RevenueChart";
import { RecentCallsTable } from "@/components/salon/RecentCallsTable";
import { TopServicesTable } from "@/components/salon/TopServicesTable";
import { PeakHoursHeat } from "@/components/salon/PeakHoursHeat";
import { DateRangeSelector } from "@/components/salon/DateRangeSelector";
import { InsightsBlock } from "@/components/salon/InsightsBlock";
import { GoogleCalendar } from "@/components/calendar/GoogleCalendar";
import { RealTimeActivity } from "@/components/salon/RealTimeActivity";
import { ContentCalendarGrid } from "@/components/calendar/ContentCalendarGrid";
import { Button } from "@/components/ui/button";
import { useNavigate } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Phone, Calendar as CalendarIcon } from "lucide-react";
import { ThemeToggle } from "@/components/ThemeToggle";
import { useSalonData } from "@/hooks/useSalonData";
import { useGoogleOAuth } from "@/hooks/useGoogleOAuth";
import { calculateProjectedMonthlyRevenue } from "@/lib/salonData";
import type { DateRange } from "@/types/salon";

const DashboardContent = () => {
  const [dateRange, setDateRange] = useState<DateRange>("30");
  const navigate = useNavigate();
  
  // Handle Google OAuth callback
  useGoogleOAuth();
  
  const { 
    kpis, 
    callsTimeseries, 
    revenueByService, 
    recentCalls, 
    topServices, 
    peakHours, 
    loading, 
    error,
    isLiveConnected,
    liveMetrics,
    liveCallEvents,
    liveTranscripts,
    liveAppointments
  } = useSalonData(dateRange);

  if (loading) {
    return (
      <SidebarProvider>
        <div className="flex min-h-screen w-full">
          <DashboardSidebar />
          <main className="flex-1 bg-background">
            <div className="container mx-auto px-4 py-8">
              <div className="flex items-center justify-center min-h-[400px]">
                <div className="text-center">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-4"></div>
                  <p className="text-muted-foreground">Loading dashboard data...</p>
                </div>
              </div>
            </div>
          </main>
        </div>
      </SidebarProvider>
    );
  }

  if (error) {
    return (
      <SidebarProvider>
        <div className="flex min-h-screen w-full">
          <DashboardSidebar />
          <main className="flex-1 bg-background">
            <div className="container mx-auto px-4 py-8">
              <div className="flex items-center justify-center min-h-[400px]">
                <div className="text-center">
                  <p className="text-destructive mb-2">Error loading dashboard data</p>
                  <p className="text-muted-foreground">{error}</p>
                </div>
              </div>
            </div>
          </main>
        </div>
      </SidebarProvider>
    );
  }

  // Calculate projected monthly revenue
  const dailyAverage = (kpis?.revenueRecovered || 0) / 30;
  const projectedMonthly = calculateProjectedMonthlyRevenue(dailyAverage);

  return (
    <SidebarProvider>
      <div className="flex min-h-screen w-full">
        <DashboardSidebar />
        
        <main className="flex-1 bg-background">
          {/* Global trigger in header */}
          <header className="h-16 flex items-center border-b px-4 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 sticky top-0 z-50">            <div className="flex-1">
              <h1 className="text-xl font-semibold">Salon Owner Dashboard</h1>
            </div>
            <div className="flex items-center gap-2">
              <DateRangeSelector 
                selectedRange={dateRange} 
                onRangeChange={setDateRange} 
              />
              <ThemeToggle />
            </div>
          </header>

          <div className="container mx-auto px-4 py-8">
            {/* Header section removed */}

            {/* Top row: left KPIs and connect card (1/3), right calendar (2/3 aligned right) */}
            <div className="flex flex-col lg:flex-row gap-6 mb-6">
              <div className="lg:w-1/3 space-y-4">
                <Card className="shadow-card">
                  <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                    <CardTitle className="text-sm font-medium">Calls Answered</CardTitle>
                    <Phone className="h-4 w-4 text-muted-foreground" />
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold">{(kpis?.callsAnswered ?? 0).toLocaleString()}</div>
                    <p className="text-xs text-muted-foreground">Total calls handled</p>
                  </CardContent>
                </Card>
                <Card className="shadow-card">
                  <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                    <CardTitle className="text-sm font-medium">Appointments Booked</CardTitle>
                    <CalendarIcon className="h-4 w-4 text-muted-foreground" />
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold">{(kpis?.appointmentsBooked ?? 0).toLocaleString()}</div>
                    <p className="text-xs text-muted-foreground">From AI calls</p>
                  </CardContent>
                </Card>
                <Card className="shadow-card">
                  <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                    <CardTitle className="text-sm font-medium">Most Recent Booking</CardTitle>
                    <CalendarIcon className="h-4 w-4 text-muted-foreground" />
                  </CardHeader>
                  <CardContent>
                    {(() => {
                      const latest = (recentCalls || []).reduce((acc, c) => {
                        if (c.outcome !== "booked") return acc;
                        if (!acc) return c;
                        return new Date(c.timestamp) > new Date(acc.timestamp) ? c : acc;
                      }, undefined as any);
                      if (!latest) {
                        return <p className="text-sm text-muted-foreground">No bookings yet</p>;
                      }
                      const date = new Date(latest.timestamp);
                      return (
                        <div>
                          <div className="text-sm font-medium">{latest.callerNameMasked || "Customer"}</div>
                          <div className="text-xs text-muted-foreground">{date.toLocaleString()}</div>
                          <div className="text-xs text-muted-foreground mt-1">Service: {latest.intent}</div>
                        </div>
                      );
                    })()}
                  </CardContent>
                </Card>
                <div className="rounded-lg border bg-card p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="font-semibold">Connect Calendar</h3>
                      <p className="text-sm text-muted-foreground">Sync Google Calendar</p>
                    </div>
                    <Button size="sm" onClick={() => navigate("/settings")}>Connect</Button>
                  </div>
                </div>
              </div>
              <div className="lg:w-2/3 lg:ml-auto">
                <div className="rounded-lg border bg-card">
                  <div className="p-4 border-b">
                    <h3 className="font-semibold">Content Calendar</h3>
                  </div>
                  <div className="p-2">
                    <ContentCalendarGrid />
                  </div>
                </div>
              </div>
            </div>

            {/* KPI Cards moved to left column above */}

            {/* Charts Row */}
            <div className="grid gap-6 lg:grid-cols-2 mb-6">
              <CallsChart data={callsTimeseries} />
              <RevenueChart data={revenueByService} />
            </div>

            {/* Tables and Insights Row */}
            <div className="grid gap-6 lg:grid-cols-3 mb-6">
              <div className="lg:col-span-2">
                <RecentCallsTable 
                  calls={recentCalls} 
                  isLiveConnected={isLiveConnected}
                  liveCallEvents={liveCallEvents}
                />
              </div>
              <div className="space-y-6">
                <TopServicesTable 
                  services={topServices} 
                  isLiveConnected={isLiveConnected}
                  liveAppointments={liveAppointments}
                />
                {kpis && (
                  <InsightsBlock 
                    kpis={kpis} 
                    projectedMonthlyRevenue={projectedMonthly} 
                  />
                )}
              </div>
            </div>

            {/* Real-Time Activity */}
            <div className="mb-6">
              <RealTimeActivity />
            </div>

            {/* Peak Hours */}
            <div>
              <PeakHoursHeat hourlyCallCounts={peakHours} />
            </div>
          </div>
        </main>
      </div>
    </SidebarProvider>
  );
};

const Dashboard = () => {
  return (
    <DashboardContent />
  );
};

export default Dashboard;