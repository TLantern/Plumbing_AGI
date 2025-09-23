import { useState } from "react";
import { SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { DashboardSidebar } from "@/components/dashboard/DashboardSidebar";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { DateRangeSelector } from "@/components/salon/DateRangeSelector";
// import { ThemeToggle } from "@/components/ThemeToggle";
import { useSalonData } from "@/hooks/useSalonData";
import { calculateProjectedMonthlyRevenue } from "@/lib/salonData";
import type { DateRange } from "@/types/salon";
import { 
  BarChart3, 
  TrendingUp, 
  Users, 
  Phone, 
  Calendar,
  DollarSign,
  Clock,
  Target
} from "lucide-react";

const Analytics = () => {
  const [dateRange, setDateRange] = useState<DateRange>("30");
  
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
                  <p className="text-muted-foreground">Loading analytics data...</p>
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
                  <p className="text-destructive mb-2">Error loading analytics data</p>
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
          <header className="h-16 flex items-center border-b px-4 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 sticky top-0 z-50">
            <div className="flex-1">
              <h1 className="text-xl font-semibold">Analytics Dashboard</h1>
            </div>
            <div className="flex items-center gap-2">
              <DateRangeSelector 
                selectedRange={dateRange} 
                onRangeChange={setDateRange} 
              />
              {/* <ThemeToggle /> */}
            </div>
          </header>

          <div className="container mx-auto px-4 py-8">
            {/* Key Metrics Overview */}
            <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4 mb-8">
              <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">Total Revenue</CardTitle>
                  <DollarSign className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">${(kpis?.revenueRecovered || 0).toLocaleString()}</div>
                  <p className="text-xs text-muted-foreground">
                    +{((kpis?.revenueRecovered || 0) / 30).toFixed(0)} daily average
                  </p>
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">Calls Answered</CardTitle>
                  <Phone className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">{(kpis?.callsAnswered || 0).toLocaleString()}</div>
                  <p className="text-xs text-muted-foreground">
                    {((kpis?.callsAnswered || 0) / 30).toFixed(1)} calls/day
                  </p>
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">Appointments</CardTitle>
                  <Calendar className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">{(kpis?.appointmentsBooked || 0).toLocaleString()}</div>
                  <p className="text-xs text-muted-foreground">
                    {((kpis?.appointmentsBooked || 0) / (kpis?.callsAnswered || 1) * 100).toFixed(1)}% conversion
                  </p>
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">Avg Call Duration</CardTitle>
                  <Clock className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">{kpis?.avgCallDuration || 0}m</div>
                  <p className="text-xs text-muted-foreground">
                    Per call average
                  </p>
                </CardContent>
              </Card>
            </div>

            {/* Performance Metrics */}
            <div className="grid gap-6 lg:grid-cols-2 mb-8">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <TrendingUp className="h-5 w-5" />
                    Revenue Trends
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    <div className="flex justify-between items-center">
                      <span className="text-sm text-muted-foreground">Projected Monthly Revenue</span>
                      <span className="font-semibold">${projectedMonthly.toLocaleString()}</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-sm text-muted-foreground">Daily Average</span>
                      <span className="font-semibold">${dailyAverage.toFixed(0)}</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-sm text-muted-foreground">Growth Rate</span>
                      <span className="font-semibold text-green-600">+12.5%</span>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Target className="h-5 w-5" />
                    Conversion Metrics
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    <div className="flex justify-between items-center">
                      <span className="text-sm text-muted-foreground">Call to Appointment</span>
                      <span className="font-semibold">
                        {((kpis?.appointmentsBooked || 0) / (kpis?.callsAnswered || 1) * 100).toFixed(1)}%
                      </span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-sm text-muted-foreground">Revenue per Call</span>
                      <span className="font-semibold">
                        ${((kpis?.revenueRecovered || 0) / (kpis?.callsAnswered || 1)).toFixed(0)}
                      </span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-sm text-muted-foreground">Customer Satisfaction</span>
                      <span className="font-semibold text-green-600">4.8/5</span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Live Status */}
            {isLiveConnected && (
              <Card className="mb-8">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
                    Live Analytics
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid gap-4 md:grid-cols-3">
                    <div className="text-center">
                      <div className="text-2xl font-bold text-green-600">
                        {liveMetrics?.activeCalls || 0}
                      </div>
                      <p className="text-sm text-muted-foreground">Active Calls</p>
                    </div>
                    <div className="text-center">
                      <div className="text-2xl font-bold text-blue-600">
                        {liveMetrics?.todayAppointments || 0}
                      </div>
                      <p className="text-sm text-muted-foreground">Today's Appointments</p>
                    </div>
                    <div className="text-center">
                      <div className="text-2xl font-bold text-purple-600">
                        {liveMetrics?.revenueToday || 0}
                      </div>
                      <p className="text-sm text-muted-foreground">Revenue Today</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Charts Section */}
            <div className="grid gap-6 lg:grid-cols-2">
              <Card>
                <CardHeader>
                  <CardTitle>Call Volume Trends</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="h-[300px] flex items-center justify-center text-muted-foreground">
                    <div className="text-center">
                      <BarChart3 className="h-12 w-12 mx-auto mb-4 opacity-50" />
                      <p>Call volume chart will be displayed here</p>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Revenue by Service</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="h-[300px] flex items-center justify-center text-muted-foreground">
                    <div className="text-center">
                      <TrendingUp className="h-12 w-12 mx-auto mb-4 opacity-50" />
                      <p>Revenue breakdown chart will be displayed here</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        </main>
      </div>
    </SidebarProvider>
  );
};

export default Analytics;
