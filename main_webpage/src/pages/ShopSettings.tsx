import { useState, useEffect } from "react";
import { Navigation } from "@/components/Navigation";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
import { 
  Store, 
  MapPin, 
  Phone, 
  Clock, 
  Globe, 
  Mail,
  Save,
  Upload
} from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { supabase } from "@/integrations/supabase/client";
import { useAuth } from "@/hooks/useAuth";

interface ShopSettings {
  salon_name: string;
  phone: string;
  address?: string;
  website_url?: string;
  business_hours?: {
    [key: string]: { open: string; close: string; closed: boolean };
  };
  services?: string[];
  timezone: string;
}

const timezones = [
  { value: "America/New_York", label: "Eastern Time" },
  { value: "America/Chicago", label: "Central Time" },
  { value: "America/Denver", label: "Mountain Time" },
  { value: "America/Los_Angeles", label: "Pacific Time" },
];

const weekDays = [
  "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"
];

const ShopSettingsContent = () => {
  const { user, salonId } = useAuth();
  const { toast } = useToast();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [settings, setSettings] = useState<ShopSettings>({
    salon_name: "",
    phone: "",
    address: "",
    website_url: "",
    timezone: "America/New_York",
    business_hours: {
      Monday: { open: "09:00", close: "17:00", closed: false },
      Tuesday: { open: "09:00", close: "17:00", closed: false },
      Wednesday: { open: "09:00", close: "17:00", closed: false },
      Thursday: { open: "09:00", close: "17:00", closed: false },
      Friday: { open: "09:00", close: "17:00", closed: false },
      Saturday: { open: "10:00", close: "16:00", closed: false },
      Sunday: { open: "10:00", close: "16:00", closed: true },
    },
    services: [],
  });

  useEffect(() => {
    const loadSettings = async () => {
      if (!salonId) return;

      try {
        setLoading(true);
        
        // Load profile data
        const { data: profile, error: profileError } = await supabase
          .from('profiles')
          .select('*')
          .eq('id', salonId)
          .single();

        if (profileError) throw profileError;

        // Load salon info if exists
        const { data: salonInfo } = await supabase
          .from('salon_info')
          .select('*')
          .eq('salon_id', salonId)
          .single();

        setSettings({
          salon_name: profile.salon_name || "",
          phone: profile.phone || "",
          timezone: profile.timezone || "America/New_York",
          address: salonInfo?.address || "",
          website_url: salonInfo?.website_url || "",
          business_hours: (salonInfo?.hours && typeof salonInfo.hours === 'object' && !Array.isArray(salonInfo.hours)) 
            ? salonInfo.hours as { [key: string]: { open: string; close: string; closed: boolean } }
            : settings.business_hours,
          services: [],
        });
      } catch (error) {
        console.error('Error loading settings:', error);
        toast({
          title: "Error",
          description: "Failed to load shop settings",
          variant: "destructive",
        });
      } finally {
        setLoading(false);
      }
    };

    loadSettings();
  }, [salonId, toast]);

  const handleSave = async () => {
    if (!salonId) return;

    try {
      setSaving(true);

      // Update profile
      const { error: profileError } = await supabase
        .from('profiles')
        .update({
          salon_name: settings.salon_name,
          phone: settings.phone,
          timezone: settings.timezone,
        })
        .eq('id', salonId);

      if (profileError) throw profileError;

      // Upsert salon info
      const { error: salonError } = await supabase
        .from('salon_info')
        .upsert({
          salon_id: salonId,
          address: settings.address,
          website_url: settings.website_url,
          hours: settings.business_hours,
        }, {
          onConflict: 'salon_id'
        });

      if (salonError) throw salonError;

      toast({
        title: "Settings Saved",
        description: "Your shop settings have been updated successfully.",
      });
    } catch (error) {
      console.error('Error saving settings:', error);
      toast({
        title: "Error",
        description: "Failed to save shop settings",
        variant: "destructive",
      });
    } finally {
      setSaving(false);
    }
  };

  const updateBusinessHours = (day: string, field: 'open' | 'close' | 'closed', value: string | boolean) => {
    setSettings(prev => ({
      ...prev,
      business_hours: {
        ...prev.business_hours!,
        [day]: {
          ...prev.business_hours![day],
          [field]: value
        }
      }
    }));
  };

  if (loading) {
    return (
      <main className="min-h-screen bg-background">
        <Navigation />
        <div className="container mx-auto px-4 pt-24 pb-8">
          <div className="flex items-center justify-center min-h-[400px]">
            <div className="text-center">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-4"></div>
              <p className="text-muted-foreground">Loading settings...</p>
            </div>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-background">
      <Navigation />
      <div className="container mx-auto px-4 pt-24 pb-8 max-w-4xl">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-2">
            <Store className="h-6 w-6 text-primary" />
            <h1 className="text-3xl font-bold">Shop Settings</h1>
          </div>
          <p className="text-muted-foreground">Configure your salon details and preferences</p>
        </div>

        <div className="space-y-6">
          {/* Basic Information */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Store className="h-5 w-5" />
                Basic Information
              </CardTitle>
              <CardDescription>
                Update your salon's basic details and contact information
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="salon_name">Salon Name</Label>
                  <Input
                    id="salon_name"
                    value={settings.salon_name}
                    onChange={(e) => setSettings(prev => ({ ...prev, salon_name: e.target.value }))}
                    placeholder="My Beautiful Salon"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="phone">Phone Number</Label>
                  <Input
                    id="phone"
                    value={settings.phone}
                    onChange={(e) => setSettings(prev => ({ ...prev, phone: e.target.value }))}
                    placeholder="+1 (555) 123-4567"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="address">Address</Label>
                <Input
                  id="address"
                  value={settings.address || ""}
                  onChange={(e) => setSettings(prev => ({ ...prev, address: e.target.value }))}
                  placeholder="123 Main St, City, State 12345"
                />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="website">Website URL</Label>
                  <Input
                    id="website"
                    value={settings.website_url || ""}
                    onChange={(e) => setSettings(prev => ({ ...prev, website_url: e.target.value }))}
                    placeholder="https://mysalon.com"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="timezone">Timezone</Label>
                  <Select 
                    value={settings.timezone} 
                    onValueChange={(value) => setSettings(prev => ({ ...prev, timezone: value }))}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {timezones.map((tz) => (
                        <SelectItem key={tz.value} value={tz.value}>
                          {tz.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Business Hours */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Clock className="h-5 w-5" />
                Business Hours
              </CardTitle>
              <CardDescription>
                Set your salon's operating hours for each day of the week
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {weekDays.map((day) => {
                const hours = settings.business_hours?.[day];
                if (!hours) return null;

                return (
                  <div key={day} className="flex items-center gap-4 p-3 border rounded-lg">
                    <div className="w-20 font-medium">{day}</div>
                    <div className="flex items-center gap-2">
                      <Switch
                        checked={!hours.closed}
                        onCheckedChange={(checked) => updateBusinessHours(day, 'closed', !checked)}
                      />
                      <span className="text-sm text-muted-foreground">
                        {hours.closed ? 'Closed' : 'Open'}
                      </span>
                    </div>
                    {!hours.closed && (
                      <>
                        <Input
                          type="time"
                          value={hours.open}
                          onChange={(e) => updateBusinessHours(day, 'open', e.target.value)}
                          className="w-32"
                        />
                        <span className="text-muted-foreground">to</span>
                        <Input
                          type="time"
                          value={hours.close}
                          onChange={(e) => updateBusinessHours(day, 'close', e.target.value)}
                          className="w-32"
                        />
                      </>
                    )}
                  </div>
                );
              })}
            </CardContent>
          </Card>

          {/* Save Button */}
          <div className="flex justify-end">
            <Button onClick={handleSave} disabled={saving}>
              {saving ? (
                <>
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                  Saving...
                </>
              ) : (
                <>
                  <Save className="h-4 w-4 mr-2" />
                  Save Settings
                </>
              )}
            </Button>
          </div>
        </div>
      </div>
    </main>
  );
};

const ShopSettings = () => {
  return (
    <ProtectedRoute>
      <ShopSettingsContent />
    </ProtectedRoute>
  );
};

export default ShopSettings;