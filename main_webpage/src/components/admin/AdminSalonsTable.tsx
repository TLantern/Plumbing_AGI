import { useState } from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Search, Eye, Phone, Calendar, DollarSign } from "lucide-react";
import { SalonOverview } from "@/hooks/useAdminData";

interface AdminSalonsTableProps {
  salons: SalonOverview[];
  onViewSalon: (salonId: string) => void;
}

export const AdminSalonsTable = ({ salons, onViewSalon }: AdminSalonsTableProps) => {
  const [searchTerm, setSearchTerm] = useState("");

  const filteredSalons = salons.filter(salon =>
    salon.salon_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    salon.phone?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const formatCurrency = (cents: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(cents / 100);
  };

  const formatNumber = (num: number) => {
    return new Intl.NumberFormat('en-US').format(num);
  };

  const getActivityStatus = (totalCalls: number) => {
    if (totalCalls === 0) return { status: "Inactive", variant: "destructive" as const };
    if (totalCalls < 10) return { status: "Low", variant: "secondary" as const };
    if (totalCalls < 50) return { status: "Moderate", variant: "default" as const };
    return { status: "High", variant: "default" as const };
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Salon Management</h1>
          <p className="text-muted-foreground">
            View and manage all registered salons
          </p>
        </div>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>All Salons ({filteredSalons.length})</CardTitle>
              <CardDescription>
                Complete list of registered salon accounts
              </CardDescription>
            </div>
            <div className="relative w-72">
              <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search salons..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-8"
              />
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Salon Name</TableHead>
                  <TableHead>Contact</TableHead>
                  <TableHead>Registration Date</TableHead>
                  <TableHead className="text-right">Revenue</TableHead>
                  <TableHead className="text-right">Calls</TableHead>
                  <TableHead className="text-right">Appointments</TableHead>
                  <TableHead>Activity</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredSalons.map((salon) => {
                  const activity = getActivityStatus(salon.total_calls);
                  return (
                    <TableRow key={salon.salon_id}>
                      <TableCell className="font-medium">
                        {salon.salon_name}
                      </TableCell>
                      <TableCell>
                        <div className="space-y-1">
                          {salon.phone && (
                            <div className="flex items-center text-sm">
                              <Phone className="w-3 h-3 mr-1" />
                              {salon.phone}
                            </div>
                          )}
                          {salon.timezone && (
                            <div className="text-xs text-muted-foreground">
                              {salon.timezone}
                            </div>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="text-sm">
                          {new Date(salon.created_at).toLocaleDateString()}
                        </div>
                        <div className="text-xs text-muted-foreground">
                          {new Date(salon.created_at).toLocaleTimeString()}
                        </div>
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end">
                          <DollarSign className="w-3 h-3 mr-1" />
                          {formatCurrency(salon.total_revenue_cents)}
                        </div>
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end">
                          <Phone className="w-3 h-3 mr-1" />
                          {formatNumber(salon.total_calls)}
                        </div>
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end">
                          <Calendar className="w-3 h-3 mr-1" />
                          {formatNumber(salon.total_appointments)}
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant={activity.variant}>
                          {activity.status}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => onViewSalon(salon.salon_id)}
                        >
                          <Eye className="w-4 h-4 mr-1" />
                          View Details
                        </Button>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};