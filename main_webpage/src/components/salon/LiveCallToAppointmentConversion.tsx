import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Phone, Calendar, TrendingUp, Clock } from "lucide-react";
import { useSalonData } from "@/hooks/useSalonData";

interface LiveCallToAppointmentConversionProps {
  dateRange?: string;
}

export function LiveCallToAppointmentConversion({ dateRange = "30" }: LiveCallToAppointmentConversionProps) {
  const { 
    kpis, 
    isLiveConnected,
    liveCallEvents,
    liveAppointments,
    loading 
  } = useSalonData(dateRange);

  if (loading) {
    return (
      <Card className="shadow-card">
        <CardHeader>
          <CardTitle className="text-sm font-medium">Live Call Conversion</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="animate-pulse">
            <div className="h-4 bg-gray-200 rounded w-3/4 mb-2"></div>
            <div className="h-8 bg-gray-200 rounded w-1/2"></div>
          </div>
        </CardContent>
      </Card>
    );
  }

  // Calculate live conversion metrics
  const today = new Date().toDateString();
  const liveCalls = liveCallEvents?.filter(call => 
    new Date(call.timestamp).toDateString() === today
  ) || [];
  const liveBookings = liveAppointments?.filter(apt => 
    new Date(apt.timestamp).toDateString() === today
  ) || [];

  const liveConversionRate = liveCalls.length > 0 ? (liveBookings.length / liveCalls.length) * 100 : 0;
  const overallConversionRate = kpis ? (kpis.conversionRate * 100) : 0;

  // Calculate average time to conversion (mock data for now)
  const avgTimeToConversion = "2.3 min";

  return (
    <Card className="shadow-card">
      <CardHeader className="flex flex-row items-center justify-center space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">Live Call Conversion</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Live Stats Row */}
        <div className="grid grid-cols-2 gap-4">
          <div className="text-center">
            <div className="flex items-center justify-center mb-1">
              <Phone className="h-4 w-4 text-blue-500 mr-1" />
              <span className="text-xs text-muted-foreground">Calls Today</span>
            </div>
            <div className="text-lg font-bold text-blue-600">{liveCalls.length}</div>
          </div>
          <div className="text-center">
            <div className="flex items-center justify-center mb-1">
              <Calendar className="h-4 w-4 text-orange-500 mr-1" />
              <span className="text-xs text-muted-foreground">Bookings Today</span>
            </div>
            <div className="text-lg font-bold text-orange-600">{liveBookings.length}</div>
          </div>
        </div>

        {/* Conversion Rate */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs text-muted-foreground">Today's Conversion</span>
            <span className="text-sm font-medium">
              {liveConversionRate.toFixed(1)}%
            </span>
          </div>
          <Progress 
            value={liveConversionRate} 
            className="h-2"
          />
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>Overall: {overallConversionRate.toFixed(1)}%</span>
            <div className="flex items-center">
              <Clock className="h-3 w-3 mr-1" />
              <span>Avg: {avgTimeToConversion}</span>
            </div>
          </div>
        </div>

        {/* Performance Indicator */}
        {liveCalls.length > 0 && (
          <div className="pt-2 border-t">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">Performance</span>
              <div className="flex items-center">
                {liveConversionRate >= overallConversionRate ? (
                  <>
                    <TrendingUp className="h-3 w-3 text-green-500 mr-1" />
                    <span className="text-xs text-green-600 font-medium">Above Average</span>
                  </>
                ) : (
                  <>
                    <TrendingUp className="h-3 w-3 text-red-500 mr-1 rotate-180" />
                    <span className="text-xs text-red-600 font-medium">Below Average</span>
                  </>
                )}
              </div>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
