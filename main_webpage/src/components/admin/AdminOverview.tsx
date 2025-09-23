import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Building2, Phone, Calendar, DollarSign, TrendingUp, Users, Wifi, Activity, Sparkles } from "lucide-react";
import { PlatformMetrics, SalonOverview } from "@/hooks/useAdminData";
import { Badge } from "@/components/ui/badge";

interface AdminOverviewProps {
  platformMetrics: PlatformMetrics | null;
  salons: SalonOverview[];
  onViewSalons: () => void;
  isLiveConnected?: boolean;
  liveMetrics?: any;
  todaysStats?: {
    calls: number;
    appointments: number;
    revenue: number;
  };
}

export const AdminOverview = ({ 
  platformMetrics, 
  salons, 
  onViewSalons, 
  isLiveConnected = false, 
  liveMetrics, 
  todaysStats 
}: AdminOverviewProps) => {
  const formatCurrency = (cents: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(cents / 100);
  };

  const formatNumber = (num: number) => {
    return new Intl.NumberFormat('en-US').format(num);
  };

  const recentSalons = salons.slice(0, 5);
  const topPerformingSalons = [...salons]
    .sort((a, b) => b.total_revenue_cents - a.total_revenue_cents)
    .slice(0, 3);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Admin Dashboard</h1>
          <p className="text-muted-foreground">
            Platform overview and key metrics
          </p>
        </div>
        <div className="flex items-center gap-2">
          {liveMetrics?.active_calls > 0 && (
            <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200">
              <Activity className="w-3 h-3 mr-1 animate-pulse" />
              {liveMetrics.active_calls} active calls
            </Badge>
          )}
          {isLiveConnected ? (
            <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200">
              <Wifi className="w-3 h-3 mr-1" />
              Live Data
            </Badge>
          ) : (
            <Badge variant="outline" className="bg-gray-50 text-gray-700 border-gray-200">
              <Activity className="w-3 h-3 mr-1" />
              Historical Data Only
            </Badge>
          )}
        </div>
      </div>

      {/* Key Metrics Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Salons</CardTitle>
            <Building2 className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {formatNumber(platformMetrics?.total_salons || 0)}
            </div>
            <p className="text-xs text-muted-foreground">
              {formatNumber(platformMetrics?.active_salons || 0)} active this month
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Revenue</CardTitle>
            <div className="flex items-center gap-2">
              <DollarSign className="h-4 w-4 text-muted-foreground" />
              {todaysStats?.revenue && todaysStats.revenue > 0 && (
                <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
              )}
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {formatCurrency(platformMetrics?.total_revenue_cents || 0)}
            </div>
            <div className="flex items-center justify-between">
              <p className="text-xs text-muted-foreground">
                Across all salons
              </p>
              {todaysStats?.revenue && todaysStats.revenue > 0 && (
                <p className="text-xs text-green-600 font-medium">
                  +{formatCurrency(todaysStats.revenue)} today
                </p>
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Calls</CardTitle>
            <div className="flex items-center gap-2">
              <Phone className="h-4 w-4 text-muted-foreground" />
              {todaysStats?.calls && todaysStats.calls > 0 && (
                <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse" />
              )}
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {formatNumber(platformMetrics?.total_calls || 0)}
            </div>
            <div className="flex items-center justify-between">
              <p className="text-xs text-muted-foreground">
                Platform-wide call volume
              </p>
              {todaysStats?.calls && todaysStats.calls > 0 && (
                <p className="text-xs text-blue-600 font-medium">
                  +{todaysStats.calls} today
                </p>
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Appointments</CardTitle>
            <div className="flex items-center gap-2">
              <Calendar className="h-4 w-4 text-muted-foreground" />
              {todaysStats?.appointments && todaysStats.appointments > 0 && (
                <div className="w-2 h-2 bg-orange-500 rounded-full animate-pulse" />
              )}
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {formatNumber(platformMetrics?.total_appointments || 0)}
            </div>
            <div className="flex items-center justify-between">
              <p className="text-xs text-muted-foreground">
                Booked through the platform
              </p>
              {todaysStats?.appointments && todaysStats.appointments > 0 && (
                <p className="text-xs text-orange-600 font-medium">
                  +{todaysStats.appointments} today
                </p>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        {/* Recent Salons */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Recent Salons</CardTitle>
                <CardDescription>
                  Latest salon registrations
                </CardDescription>
              </div>
              <Button variant="outline" onClick={onViewSalons}>
                View All
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {recentSalons.map((salon) => (
                <div key={salon.salon_id} className="flex items-center justify-between">
                  <div className="space-y-1">
                    <p className="text-sm font-medium leading-none">
                      {salon.salon_name}
                    </p>
                    <p className="text-sm text-muted-foreground">
                      {new Date(salon.created_at).toLocaleDateString()}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-medium">
                      {formatCurrency(salon.total_revenue_cents)}
                    </p>
                    <p className="text-sm text-muted-foreground">
                      {salon.total_calls} calls
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Top Performing Salons */}
        <Card>
          <CardHeader>
            <CardTitle>Top Performing Salons</CardTitle>
            <CardDescription>
              Salons by revenue generated
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {topPerformingSalons.map((salon, index) => (
                <div key={salon.salon_id} className="flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <Badge variant={index === 0 ? "default" : "secondary"}>
                      #{index + 1}
                    </Badge>
                    <div>
                      <p className="text-sm font-medium leading-none">
                        {salon.salon_name}
                      </p>
                      <p className="text-sm text-muted-foreground">
                        {salon.total_appointments} appointments
                      </p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-medium">
                      {formatCurrency(salon.total_revenue_cents)}
                    </p>
                    <div className="flex items-center text-xs text-muted-foreground">
                      <TrendingUp className="w-3 h-3 mr-1" />
                      {salon.total_calls} calls
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};