import { Navigation } from "@/components/Navigation";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Bell, Moon, Globe, Shield, Database, Trash2, Calendar, RefreshCw, CheckCircle, XCircle } from "lucide-react";
import { useState, useEffect } from "react";
import { useGoogleOAuth } from "@/hooks/useGoogleOAuth";
import { useToast } from "@/hooks/use-toast";

const Settings = () => {
  const { isConnected, connect, disconnect } = useGoogleOAuth();
  const { toast } = useToast();
  const [syncEnabled, setSyncEnabled] = useState(false);
  const [selectedCalendar, setSelectedCalendar] = useState("");
  const [syncFrequency, setSyncFrequency] = useState("15");
  const [lastSync, setLastSync] = useState<Date | null>(null);
  const [isSyncing, setIsSyncing] = useState(false);

  const handleConnect = async () => {
    try {
      await connect();
      toast({
        title: "Successfully Connected!",
        description: "Your Google Calendar has been connected.",
      });
    } catch (error) {
      toast({
        title: "Connection Failed",
        description: "Failed to connect to Google Calendar. Please try again.",
        variant: "destructive",
      });
    }
  };

  const handleDisconnect = async () => {
    try {
      await disconnect();
      setSyncEnabled(false);
      setSelectedCalendar("");
      toast({
        title: "Disconnected",
        description: "Google Calendar connection has been removed.",
      });
    } catch (error) {
      toast({
        title: "Disconnect Failed",
        description: "Failed to disconnect from Google Calendar.",
        variant: "destructive",
      });
    }
  };

  const handleSyncNow = async () => {
    if (!isConnected) return;
    
    setIsSyncing(true);
    try {
      // Simulate sync process
      await new Promise(resolve => setTimeout(resolve, 2000));
      setLastSync(new Date());
      toast({
        title: "Sync Complete",
        description: "Your calendar has been synchronized successfully.",
      });
    } catch (error) {
      toast({
        title: "Sync Failed",
        description: "Failed to synchronize calendar. Please try again.",
        variant: "destructive",
      });
    } finally {
      setIsSyncing(false);
    }
  };

  return (
    <main className="min-h-screen bg-background">
      <Navigation />
      <div className="container mx-auto px-4 pt-24">
        <div className="mb-8">
          <h1 className="text-3xl font-bold mb-2">Settings</h1>
          <p className="text-muted-foreground">Manage your application preferences and account settings</p>
        </div>
        
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center space-x-2">
                <Calendar className="h-5 w-5" />
                <span>Google Calendar Sync</span>
              </CardTitle>
              <CardDescription>Synchronize your Google Calendar with the dashboard</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Connection Status */}
              <div className="flex items-center justify-between p-4 rounded-lg border">
                <div className="flex items-center space-x-3">
                  {isConnected ? (
                    <CheckCircle className="h-5 w-5 text-green-500" />
                  ) : (
                    <XCircle className="h-5 w-5 text-red-500" />
                  )}
                  <div>
                    <p className="font-medium">
                      {isConnected ? "Connected" : "Not Connected"}
                    </p>
                    <p className="text-sm text-muted-foreground">
                      {isConnected ? "Google Calendar is connected" : "Connect to sync your calendar"}
                    </p>
                  </div>
                </div>
                {isConnected ? (
                  <Button variant="outline" size="sm" onClick={handleDisconnect}>
                    Disconnect
                  </Button>
                ) : (
                  <Button size="sm" onClick={handleConnect}>
                    Connect
                  </Button>
                )}
              </div>

              {/* Sync Settings */}
              {isConnected && (
                <>
                  <div className="flex items-center justify-between">
                    <div>
                      <Label htmlFor="sync-enabled">Enable Auto Sync</Label>
                      <p className="text-sm text-muted-foreground">Automatically sync calendar events</p>
                    </div>
                    <Switch 
                      id="sync-enabled" 
                      checked={syncEnabled}
                      onCheckedChange={setSyncEnabled}
                    />
                  </div>

                  <div>
                    <Label htmlFor="sync-frequency">Sync Frequency</Label>
                    <Select value={syncFrequency} onValueChange={setSyncFrequency}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="5">Every 5 minutes</SelectItem>
                        <SelectItem value="15">Every 15 minutes</SelectItem>
                        <SelectItem value="30">Every 30 minutes</SelectItem>
                        <SelectItem value="60">Every hour</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  <div>
                    <Label htmlFor="calendar-select">Calendar</Label>
                    <Select value={selectedCalendar} onValueChange={setSelectedCalendar}>
                      <SelectTrigger>
                        <SelectValue placeholder="Select calendar to sync" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="primary">Primary Calendar</SelectItem>
                        <SelectItem value="work">Work Calendar</SelectItem>
                        <SelectItem value="personal">Personal Calendar</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  {/* Last Sync Info */}
                  {lastSync && (
                    <div className="text-sm text-muted-foreground">
                      Last synced: {lastSync.toLocaleString()}
                    </div>
                  )}

                  {/* Manual Sync Button */}
                  <Button 
                    variant="outline" 
                    className="w-full" 
                    onClick={handleSyncNow}
                    disabled={isSyncing}
                  >
                    <RefreshCw className={`h-4 w-4 mr-2 ${isSyncing ? 'animate-spin' : ''}`} />
                    {isSyncing ? 'Syncing...' : 'Sync Now'}
                  </Button>
                </>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center space-x-2">
                <Bell className="h-5 w-5" />
                <span>Notifications</span>
              </CardTitle>
              <CardDescription>Configure your notification preferences</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <Label htmlFor="email-notifications">Email Notifications</Label>
                  <p className="text-sm text-muted-foreground">Receive updates via email</p>
                </div>
                <Switch id="email-notifications" defaultChecked />
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <Label htmlFor="push-notifications">Push Notifications</Label>
                  <p className="text-sm text-muted-foreground">Receive browser notifications</p>
                </div>
                <Switch id="push-notifications" defaultChecked />
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <Label htmlFor="dispatch-alerts">Dispatch Alerts</Label>
                  <p className="text-sm text-muted-foreground">Get notified about new dispatches</p>
                </div>
                <Switch id="dispatch-alerts" defaultChecked />
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <Label htmlFor="weekly-reports">Weekly Reports</Label>
                  <p className="text-sm text-muted-foreground">Receive weekly performance summaries</p>
                </div>
                <Switch id="weekly-reports" />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center space-x-2">
                <Moon className="h-5 w-5" />
                <span>Appearance</span>
              </CardTitle>
              <CardDescription>Customize how the application looks</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              /*               <div>
              /*                 <Label htmlFor="theme">Theme</Label>
              /*                 <Select defaultValue="system">
              /*                   <SelectTrigger>
              /*                     <SelectValue />
              /*                   </SelectTrigger>
              /*                   <SelectContent>
              /*                     <SelectItem value="light">Light</SelectItem>
              /*                     <SelectItem value="dark">Dark</SelectItem>
              /*                     <SelectItem value="system">System</SelectItem>
              /*                   </SelectContent>
              /*                 </Select>
              /*               </div> */
              <div>
                <Label htmlFor="language">Language</Label>
                <Select defaultValue="en">
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="en">English</SelectItem>
                    <SelectItem value="es">Spanish</SelectItem>
                    <SelectItem value="fr">French</SelectItem>
                    <SelectItem value="de">German</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label htmlFor="timezone">Timezone</Label>
                <Select defaultValue="utc-5">
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="utc-8">Pacific Time (UTC-8)</SelectItem>
                    <SelectItem value="utc-7">Mountain Time (UTC-7)</SelectItem>
                    <SelectItem value="utc-6">Central Time (UTC-6)</SelectItem>
                    <SelectItem value="utc-5">Eastern Time (UTC-5)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center space-x-2">
                <Shield className="h-5 w-5" />
                <span>Privacy & Security</span>
              </CardTitle>
              <CardDescription>Control your privacy and security settings</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <Label htmlFor="two-factor">Two-Factor Authentication</Label>
                  <p className="text-sm text-muted-foreground">Add an extra layer of security</p>
                </div>
                <Switch id="two-factor" />
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <Label htmlFor="session-timeout">Auto Logout</Label>
                  <p className="text-sm text-muted-foreground">Automatically sign out after inactivity</p>
                </div>
                <Switch id="session-timeout" defaultChecked />
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <Label htmlFor="data-sharing">Analytics Data Sharing</Label>
                  <p className="text-sm text-muted-foreground">Help improve our service</p>
                </div>
                <Switch id="data-sharing" defaultChecked />
              </div>
              <Button variant="outline" className="w-full">
                <Shield className="h-4 w-4 mr-2" />
                View Security Log
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center space-x-2">
                <Database className="h-5 w-5" />
                <span>Data Management</span>
              </CardTitle>
              <CardDescription>Manage your data and account</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div>
                <Label>Data Export</Label>
                <p className="text-sm text-muted-foreground mb-3">Download a copy of your data</p>
                <Button variant="outline" className="w-full">
                  <Database className="h-4 w-4 mr-2" />
                  Export Data
                </Button>
              </div>
              <Separator />
              <div>
                <Label className="text-red-600">Danger Zone</Label>
                <p className="text-sm text-muted-foreground mb-3">Irreversible and destructive actions</p>
                <Button variant="destructive" className="w-full">
                  <Trash2 className="h-4 w-4 mr-2" />
                  Delete Account
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="mt-6 flex justify-end space-x-4">
          <Button variant="outline">Cancel</Button>
          <Button>Save All Changes</Button>
        </div>
      </div>
    </main>
  );
};

export default Settings;