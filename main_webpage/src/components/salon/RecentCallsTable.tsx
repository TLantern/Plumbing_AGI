import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { ThumbsUp, ThumbsDown, Phone, Clock, Wifi, Activity } from "lucide-react";
import type { RecentCall } from "@/types/salon";

interface RecentCallsTableProps {
  calls: RecentCall[];
  isLiveConnected?: boolean;
  liveCallEvents?: Array<{ timestamp: string; call_sid: string; caller_number: string }>;
}

export function RecentCallsTable({ calls, isLiveConnected = false, liveCallEvents = [] }: RecentCallsTableProps) {
  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString('en-US', { 
      hour: 'numeric', 
      minute: '2-digit',
      hour12: true 
    });
  };

  const formatDuration = (seconds: number) => {
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
  };

  const getOutcomeBadge = (outcome: RecentCall['outcome']) => {
    switch (outcome) {
      case 'booked':
        return <Badge className="bg-primary/10 text-primary border-primary/20">Booked</Badge>;
      case 'transferred':
        return <Badge variant="secondary">Transferred</Badge>;
      case 'voicemail':
        return <Badge variant="outline">Voicemail</Badge>;
    }
  };

  const getSentimentIcon = (sentiment: RecentCall['sentiment']) => {
    return sentiment === 'up' ? (
      <ThumbsUp className="h-4 w-4 text-primary" />
    ) : (
      <ThumbsDown className="h-4 w-4 text-destructive" />
    );
  };

  const isLiveCall = (call: RecentCall) => {
    return call.id.startsWith('live-') || liveCallEvents.some(live => 
      Math.abs(new Date(live.timestamp).getTime() - new Date(call.timestamp).getTime()) < 60000
    );
  };

  return (
    <Card className="shadow-card">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>Recent Calls</CardTitle>
            <CardDescription>Latest customer interactions and outcomes</CardDescription>
          </div>
          {isLiveConnected && (
            <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200">
              <Wifi className="w-3 h-3 mr-1" />
              Live Updates
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Time</TableHead>
              <TableHead>Caller</TableHead>
              <TableHead>Intent</TableHead>
              <TableHead>Outcome</TableHead>
              <TableHead>Duration</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {calls.map((call) => {
              const isLive = isLiveCall(call);
              return (
                <TableRow key={call.id} className={isLive ? "bg-blue-50/50 border-l-4 border-l-blue-500" : ""}>
                  <TableCell className="font-medium">
                    <div className="flex items-center gap-2">
                      {isLive ? (
                        <Activity className="h-3 w-3 text-blue-500 animate-pulse" />
                      ) : (
                        <Phone className="h-3 w-3 text-muted-foreground" />
                      )}
                      {formatTime(call.timestamp)}
                      {isLive && (
                        <Badge variant="outline" className="text-xs ml-2 bg-blue-50 text-blue-700 border-blue-200">
                          Live
                        </Badge>
                      )}
                    </div>
                  </TableCell>
                  <TableCell>{call.callerNameMasked}</TableCell>
                  <TableCell>
                    <span className="capitalize">{call.intent}</span>
                  </TableCell>
                  <TableCell>{getOutcomeBadge(call.outcome)}</TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1">
                      <Clock className="h-3 w-3 text-muted-foreground" />
                      {isLive && call.durationSec === 0 ? "In Progress" : formatDuration(call.durationSec)}
                    </div>
                  </TableCell>
                  <TableCell className="text-center">
                    {getSentimentIcon(call.sentiment)}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}