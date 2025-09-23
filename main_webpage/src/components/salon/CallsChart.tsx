import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ChartContainer, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart";
import { Area, AreaChart, ResponsiveContainer, XAxis, YAxis } from "recharts";
import type { CallsTimeseriesPoint } from "@/types/salon";

interface CallsChartProps {
  data: CallsTimeseriesPoint[];
}

const chartConfig = {
  answered: {
    label: "Answered",
    color: "hsl(var(--primary))",
  },
  missed: {
    label: "Missed",
    color: "hsl(var(--destructive))",
  },
  afterHoursCaptured: {
    label: "After Hours",
    color: "hsl(var(--primary-glow))",
  },
};

export function CallsChart({ data }: CallsChartProps) {
  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };

  const chartData = data.map(point => ({
    ...point,
    dateFormatted: formatDate(point.date),
  }));

  return (
    <Card className="shadow-card">
      <CardHeader>
        <CardTitle>Call Performance</CardTitle>
        <CardDescription>Daily call volume breakdown for the last 30 days</CardDescription>
      </CardHeader>
      <CardContent>
        <ChartContainer config={chartConfig}>
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={chartData}>
              <defs>
                <linearGradient id="answered" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="hsl(var(--primary))" stopOpacity={0.8}/>
                  <stop offset="95%" stopColor="hsl(var(--primary))" stopOpacity={0.1}/>
                </linearGradient>
                <linearGradient id="missed" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="hsl(var(--destructive))" stopOpacity={0.8}/>
                  <stop offset="95%" stopColor="hsl(var(--destructive))" stopOpacity={0.1}/>
                </linearGradient>
                <linearGradient id="afterHours" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="hsl(var(--primary-glow))" stopOpacity={0.8}/>
                  <stop offset="95%" stopColor="hsl(var(--primary-glow))" stopOpacity={0.1}/>
                </linearGradient>
              </defs>
              <XAxis 
                dataKey="dateFormatted" 
                axisLine={false}
                tickLine={false}
                className="text-xs"
              />
              <YAxis 
                axisLine={false}
                tickLine={false}
                className="text-xs"
              />
              <ChartTooltip content={<ChartTooltipContent />} />
              <Area
                type="monotone"
                dataKey="answered"
                stackId="1"
                stroke="hsl(var(--primary))"
                fill="url(#answered)"
              />
              <Area
                type="monotone"
                dataKey="afterHoursCaptured"
                stackId="1"
                stroke="hsl(var(--primary-glow))"
                fill="url(#afterHours)"
              />
              <Area
                type="monotone"
                dataKey="missed"
                stackId="1"
                stroke="hsl(var(--destructive))"
                fill="url(#missed)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </ChartContainer>
      </CardContent>
    </Card>
  );
}