import { Card, CardContent } from "@/components/ui/card";
import { TrendingUp, DollarSign, Target } from "lucide-react";
import type { KPIs } from "@/types/salon";

interface InsightsBlockProps {
  kpis: KPIs;
  projectedMonthlyRevenue: number;
}

export function InsightsBlock({ kpis, projectedMonthlyRevenue }: InsightsBlockProps) {
  const formatCurrency = (cents: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(cents / 100);
  };

  const insights = [
    {
      icon: TrendingUp,
      title: "Monthly Projection",
      description: `At this pace, you'll recover ${formatCurrency(projectedMonthlyRevenue)} this month.`,
      highlight: true,
    },
    {
      icon: Target,
      title: "Conversion Success",
      description: `Your ${(kpis.conversionRate * 100).toFixed(1)}% conversion rate is capturing more revenue from every call.`,
      highlight: false,
    },
    {
      icon: DollarSign,
      title: "Revenue Impact",
      description: `Each answered call generates an average of ${formatCurrency(kpis.revenueRecovered / kpis.callsAnswered)} in bookings.`,
      highlight: false,
    },
  ];

  return (
    <Card className="shadow-card bg-gradient-to-br from-primary/5 to-primary-glow/5 border-primary/10">
      <CardContent className="p-6">
        <div className="mb-4">
          <h3 className="text-lg font-semibold text-foreground">Business Insights</h3>
          <p className="text-sm text-muted-foreground">AI-powered analysis of your salon's performance</p>
        </div>
        
        <div className="space-y-4">
          {insights.map((insight, index) => {
            const Icon = insight.icon;
            return (
              <div 
                key={index}
                className={`flex items-start gap-3 rounded-lg p-3 transition-colors ${
                  insight.highlight 
                    ? 'bg-primary/10 border border-primary/20' 
                    : 'bg-muted/30'
                }`}
              >
                <div className={`mt-0.5 ${insight.highlight ? 'text-primary' : 'text-muted-foreground'}`}>
                  <Icon className="h-5 w-5" />
                </div>
                <div className="flex-1">
                  <h4 className={`font-medium ${insight.highlight ? 'text-primary' : 'text-foreground'}`}>
                    {insight.title}
                  </h4>
                  <p className={`text-sm ${insight.highlight ? 'text-primary/80' : 'text-muted-foreground'}`}>
                    {insight.description}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}