import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { TrendingUp, Wifi, Sparkles } from "lucide-react";
import type { TopService } from "@/types/salon";

interface TopServicesTableProps {
  services: TopService[];
  isLiveConnected?: boolean;
  liveAppointments?: Array<{ estimated_revenue_cents: number; timestamp: string }>;
}

export function TopServicesTable({ services, isLiveConnected = false, liveAppointments = [] }: TopServicesTableProps) {
  const formatCurrency = (cents: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(cents / 100);
  };

  const calculateEstRevenue = (count: number, avgPriceCents: number) => {
    return formatCurrency(count * avgPriceCents);
  };

  // Calculate today's live appointments
  const today = new Date().toDateString();
  const todaysLiveAppointments = liveAppointments.filter(apt => 
    new Date(apt.timestamp).toDateString() === today
  );

  return (
    <Card className="shadow-card">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>Top Services Booked</CardTitle>
            <CardDescription>Most popular services and their revenue impact</CardDescription>
          </div>
          <div className="flex items-center gap-2">
            {todaysLiveAppointments.length > 0 && (
              <Badge variant="outline" className="bg-orange-50 text-orange-700 border-orange-200">
                <Sparkles className="w-3 h-3 mr-1" />
                +{todaysLiveAppointments.length} today
              </Badge>
            )}
            {isLiveConnected && (
              <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200">
                <Wifi className="w-3 h-3 mr-1" />
                Live
              </Badge>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Service</TableHead>
              <TableHead className="text-center">Count</TableHead>
              <TableHead className="text-right">Avg. Price</TableHead>
              <TableHead className="text-right">Est. Revenue</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {services.map((service, index) => (
              <TableRow key={service.service}>
                <TableCell className="font-medium">
                  <div className="flex items-center gap-2">
                    <div className="flex h-6 w-6 items-center justify-center rounded-full bg-primary/10 text-xs font-bold text-primary">
                      {index + 1}
                    </div>
                    <span className="capitalize">{service.service}</span>
                  </div>
                </TableCell>
                <TableCell className="text-center">
                  <div className="flex items-center justify-center gap-1">
                    <TrendingUp className="h-3 w-3 text-primary" />
                    {service.count}
                  </div>
                </TableCell>
                <TableCell className="text-right">
                  {formatCurrency(service.avgPriceCents)}
                </TableCell>
                <TableCell className="text-right font-bold text-primary">
                  {calculateEstRevenue(service.count, service.avgPriceCents)}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}