import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useSalonWebSocket } from "@/hooks/useSalonWebSocket";
import { Phone, MessageSquare, Calendar, AlertCircle, Wifi, WifiOff } from "lucide-react";
import { formatDistanceToNow } from "date-fns";

export const RealTimeActivity = () => {
  const { 
    isConnected, 
    metrics, 
    recentCallEvents, 
    recentTranscripts, 
    recentAppointments, 
    error,
    reconnect 
  } = useSalonWebSocket();

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'booked': return 'bg-green-100 text-green-800';
      case 'inquiry': return 'bg-blue-100 text-blue-800';
      case 'in_progress': return 'bg-yellow-100 text-yellow-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const formatPhoneNumber = (phone: string) => {
    return phone.replace(/(\d{3})(\d{3})(\d{4})/, '($1) $2-$3');
  };

  return (
    <div className="space-y-6">
      {/* Connection Status */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg">Real-Time Connection</CardTitle>
            <div className="flex items-center gap-2">
              {isConnected ? (
                <Badge variant="default" className="bg-green-100 text-green-800">
                  <Wifi className="w-3 h-3 mr-1" />
                  Connected
                </Badge>
              ) : (
                <Badge variant="destructive">
                  <WifiOff className="w-3 h-3 mr-1" />
                  Disconnected
                </Badge>
              )}
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {error && (
            <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 rounded-md mb-4">
              <AlertCircle className="w-4 h-4 text-red-600" />
              <span className="text-sm text-red-700">{error}</span>
              <Button 
                size="sm" 
                variant="outline" 
                onClick={reconnect}
                className="ml-auto"
              >
                Retry
              </Button>
            </div>
          )}
          
          {metrics && (
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className="text-muted-foreground">Active Calls:</span>
                <span className="ml-2 font-medium">{metrics.active_calls}</span>
              </div>
              <div>
                <span className="text-muted-foreground">System Status:</span>
                <span className="ml-2 font-medium capitalize">{metrics.system_status}</span>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Recent Call Events */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Phone className="w-5 h-5" />
            Recent Calls
          </CardTitle>
          <CardDescription>
            Live call activity from your salon phone system
          </CardDescription>
        </CardHeader>
        <CardContent>
          {recentCallEvents.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <Phone className="w-8 h-8 mx-auto mb-2 opacity-50" />
              <p>No recent calls</p>
            </div>
          ) : (
            <div className="space-y-3">
              {recentCallEvents.map((call, index) => (
                <div key={index} className="flex items-center justify-between p-3 border rounded-lg">
                  <div className="flex items-center gap-3">
                    <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
                    <div>
                      <p className="font-medium">{formatPhoneNumber(call.caller_number)}</p>
                      <p className="text-sm text-muted-foreground">
                        {formatDistanceToNow(new Date(call.timestamp), { addSuffix: true })}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {call.supabase_logged && (
                      <Badge variant="outline" className="text-xs">Logged</Badge>
                    )}
                    {call.fallback_logged && (
                      <Badge variant="outline" className="text-xs">Fallback</Badge>
                    )}
                    {call.error && (
                      <Badge variant="destructive" className="text-xs">Error</Badge>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Recent Transcripts */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <MessageSquare className="w-5 h-5" />
            Recent Conversations
          </CardTitle>
          <CardDescription>
            Latest AI conversations with customers
          </CardDescription>
        </CardHeader>
        <CardContent>
          {recentTranscripts.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <MessageSquare className="w-8 h-8 mx-auto mb-2 opacity-50" />
              <p>No recent conversations</p>
            </div>
          ) : (
            <div className="space-y-3">
              {recentTranscripts.slice(0, 5).map((transcript, index) => (
                <div key={index} className="p-3 border rounded-lg">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium">Call {transcript.call_sid.slice(-8)}</span>
                    <span className="text-xs text-muted-foreground">
                      {formatDistanceToNow(new Date(transcript.timestamp), { addSuffix: true })}
                    </span>
                  </div>
                  <div className="space-y-2">
                    <div>
                      <p className="text-xs text-muted-foreground mb-1">Customer:</p>
                      <p className="text-sm bg-gray-50 p-2 rounded">{transcript.prompt}</p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground mb-1">AI Response:</p>
                      <p className="text-sm bg-blue-50 p-2 rounded">{transcript.response}</p>
                    </div>
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <span>Duration: {transcript.duration}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Recent Appointments */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Calendar className="w-5 h-5" />
            Recent Bookings
          </CardTitle>
          <CardDescription>
            Appointments created through phone calls
          </CardDescription>
        </CardHeader>
        <CardContent>
          {recentAppointments.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <Calendar className="w-8 h-8 mx-auto mb-2 opacity-50" />
              <p>No recent bookings</p>
            </div>
          ) : (
            <div className="space-y-3">
              {recentAppointments.map((appointment, index) => (
                <div key={index} className="flex items-center justify-between p-3 border rounded-lg">
                  <div>
                    <p className="font-medium">Appointment #{appointment.appointment_id.slice(-8)}</p>
                    <p className="text-sm text-muted-foreground">
                      {formatDistanceToNow(new Date(appointment.timestamp), { addSuffix: true })}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="font-medium text-green-600">
                      ${(appointment.estimated_revenue_cents / 100).toFixed(2)}
                    </p>
                    <p className="text-xs text-muted-foreground">Estimated Revenue</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};
