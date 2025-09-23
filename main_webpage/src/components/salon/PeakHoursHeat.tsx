import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

interface PeakHoursHeatProps {
  hourlyCallCounts: number[]; // 24 hours, index 0 = 12AM
}

export function PeakHoursHeat({ hourlyCallCounts }: PeakHoursHeatProps) {
  const maxCalls = Math.max(...hourlyCallCounts);
  
  const formatHour = (hour: number) => {
    if (hour === 0) return '12AM';
    if (hour === 12) return '12PM';
    if (hour < 12) return `${hour}AM`;
    return `${hour - 12}PM`;
  };

  const getIntensity = (calls: number) => {
    if (maxCalls === 0) return 0;
    return calls / maxCalls;
  };

  const getOpacity = (intensity: number) => {
    return Math.max(0.1, intensity);
  };

  return (
    <Card className="shadow-card">
      <CardHeader>
        <CardTitle>Peak Call Hours</CardTitle>
        <CardDescription>Call volume distribution throughout the day</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          <div className="grid grid-cols-12 gap-1 sm:grid-cols-24">
            {hourlyCallCounts.map((calls, hour) => {
              const intensity = getIntensity(calls);
              return (
                <div
                  key={hour}
                  className="group relative aspect-square rounded-sm transition-all hover:scale-110"
                  style={{
                    backgroundColor: `hsl(var(--primary))`,
                    opacity: getOpacity(intensity),
                  }}
                >
                  <div className="absolute -top-12 left-1/2 z-10 hidden -translate-x-1/2 rounded bg-popover px-2 py-1 text-xs shadow-md group-hover:block">
                    <div className="font-medium">{formatHour(hour)}</div>
                    <div className="text-muted-foreground">{calls} calls</div>
                  </div>
                </div>
              );
            })}
          </div>
          
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>12AM</span>
            <span>6AM</span>
            <span>12PM</span>
            <span>6PM</span>
            <span>12AM</span>
          </div>
          
          <div className="flex items-center justify-center gap-2 text-xs text-muted-foreground">
            <div className="h-3 w-3 rounded-sm bg-primary/20"></div>
            <span>Low</span>
            <div className="h-3 w-3 rounded-sm bg-primary/60"></div>
            <span>Medium</span>
            <div className="h-3 w-3 rounded-sm bg-primary"></div>
            <span>High</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}