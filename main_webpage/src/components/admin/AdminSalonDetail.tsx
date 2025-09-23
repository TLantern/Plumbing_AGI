import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ArrowLeft, Phone, Calendar, DollarSign, Clock, TrendingUp, Users, Building2 } from "lucide-react";
import { supabase } from "@/integrations/supabase/client";
import { useSalonData } from "@/hooks/useSalonData";

interface AdminSalonDetailProps {
  salonId: string;
  onBack: () => void;
}

interface SalonProfile {
  id: string;
  salon_name: string;
  phone?: string;
  timezone?: string;
  created_at: string;
}

export const AdminSalonDetail = ({ salonId, onBack }: AdminSalonDetailProps) => {
  const [salonProfile, setSalonProfile] = useState<SalonProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // We can reuse the existing salon data hook by temporarily setting the salon context
  // For now, we'll fetch basic profile data and show a simplified view
  
  useEffect(() => {
    const fetchSalonProfile = async () => {
      try {
        setLoading(true);
        const { data, error } = await supabase
          .from('profiles')
          .select('*')
          .eq('id', salonId)
          .single();

        if (error) throw error;
        setSalonProfile(data);
      } catch (err) {
        console.error('Error fetching salon profile:', err);
        setError(err instanceof Error ? err.message : 'Failed to fetch salon data');
      } finally {
        setLoading(false);
      }
    };

    fetchSalonProfile();
  }, [salonId]);

  const formatCurrency = (cents: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(cents / 100);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-primary"></div>
      </div>
    );
  }

  if (error || !salonProfile) {
    return (
      <div className="space-y-6">
        <Button variant="outline" onClick={onBack}>
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to Salons
        </Button>
        <Card>
          <CardContent className="flex items-center justify-center h-96">
            <div className="text-center">
              <h3 className="text-lg font-semibold text-destructive mb-2">Error Loading Salon</h3>
              <p className="text-muted-foreground">{error || 'Salon not found'}</p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <Button variant="outline" onClick={onBack}>
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Salons
          </Button>
          <div>
            <h1 className="text-3xl font-bold tracking-tight">{salonProfile.salon_name}</h1>
            <p className="text-muted-foreground">
              Salon ID: {salonProfile.id}
            </p>
          </div>
        </div>
        <Badge variant="default">
          Active Salon
        </Badge>
      </div>

      {/* Salon Info Card */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center">
            <Building2 className="w-5 h-5 mr-2" />
            Salon Information
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <label className="text-sm font-medium text-muted-foreground">Salon Name</label>
              <p className="text-sm">{salonProfile.salon_name}</p>
            </div>
            {salonProfile.phone && (
              <div className="space-y-2">
                <label className="text-sm font-medium text-muted-foreground">Phone</label>
                <p className="text-sm flex items-center">
                  <Phone className="w-4 h-4 mr-1" />
                  {salonProfile.phone}
                </p>
              </div>
            )}
            <div className="space-y-2">
              <label className="text-sm font-medium text-muted-foreground">Timezone</label>
              <p className="text-sm flex items-center">
                <Clock className="w-4 h-4 mr-1" />
                {salonProfile.timezone || 'Not specified'}
              </p>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-muted-foreground">Registration Date</label>
              <p className="text-sm flex items-center">
                <Calendar className="w-4 h-4 mr-1" />
                {new Date(salonProfile.created_at).toLocaleDateString()}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Quick Stats */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Calls</CardTitle>
            <Phone className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">-</div>
            <p className="text-xs text-muted-foreground">
              All time
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Appointments</CardTitle>
            <Calendar className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">-</div>
            <p className="text-xs text-muted-foreground">
              Total booked
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Revenue</CardTitle>
            <DollarSign className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">-</div>
            <p className="text-xs text-muted-foreground">
              Total generated
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Conversion Rate</CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">-</div>
            <p className="text-xs text-muted-foreground">
              Calls to bookings
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Placeholder for future detailed analytics */}
      <Card>
        <CardHeader>
          <CardTitle>Detailed Analytics</CardTitle>
          <CardDescription>
            Comprehensive salon performance data will be displayed here
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="text-center text-muted-foreground py-12">
            <Users className="w-12 h-12 mx-auto mb-4 opacity-50" />
            <p>Detailed analytics view coming soon</p>
            <p className="text-sm mt-2">This will show call logs, appointment history, and performance metrics</p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};