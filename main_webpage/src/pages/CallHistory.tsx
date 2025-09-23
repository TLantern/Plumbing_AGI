import { useState } from "react";
import { SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { DashboardSidebar } from "@/components/dashboard/DashboardSidebar";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { DateRangeSelector } from "@/components/salon/DateRangeSelector";
import { ThemeToggle } from "@/components/ThemeToggle";
import { useSalonData } from "@/hooks/useSalonData";
import type { DateRange } from "@/types/salon";
import { 
  Phone, 
  Search, 
  Filter,
  Clock,
  User,
  Calendar,
  MessageSquare,
  CheckCircle,
  XCircle,
  AlertCircle,
  Play,
  Download
} from "lucide-react";
import { format, parseISO } from "date-fns";

const CallHistory = () => {
  const [dateRange, setDateRange] = useState<DateRange>("30");
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedOutcome, setSelectedOutcome] = useState<string>("all");
  
  const { 
    recentCalls, 
    loading, 
    error,
    isLiveConnected,
    liveCallEvents,
    liveTranscripts
  } = useSalonData(dateRange);

  if (loading) {
    return (
      <SidebarProvider>
        <div className="flex min-h-screen w-full">
          <DashboardSidebar />
          <main className="flex-1 bg-background">
            <div className="container mx-auto px-4 py-8">
              <div className="flex items-center justify-center min-h-[400px]">
                <div className="text-center">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-4"></div>
                  <p className="text-muted-foreground">Loading call history...</p>
                </div>
              </div>
            </div>
          </main>
        </div>
      </SidebarProvider>
    );
  }

  if (error) {
    return (
      <SidebarProvider>
        <div className="flex min-h-screen w-full">
          <DashboardSidebar />
          <main className="flex-1 bg-background">
            <div className="container mx-auto px-4 py-8">
              <div className="flex items-center justify-center min-h-[400px]">
                <div className="text-center">
                  <p className="text-destructive mb-2">Error loading call history</p>
                  <p className="text-muted-foreground">{error}</p>
                </div>
              </div>
            </div>
          </main>
        </div>
      </SidebarProvider>
    );
  }

  // Filter calls based on search and outcome
  const filteredCalls = (recentCalls || []).filter(call => {
    const matchesSearch = call.callerNameMasked?.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         call.intent?.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         call.phoneNumber?.includes(searchTerm);
    const matchesOutcome = selectedOutcome === "all" || call.outcome === selectedOutcome;
    return matchesSearch && matchesOutcome;
  });

  const getOutcomeIcon = (outcome: string) => {
    switch (outcome) {
      case "booked":
        return <CheckCircle className="h-4 w-4 text-green-600" />;
      case "no_show":
        return <XCircle className="h-4 w-4 text-red-600" />;
      case "cancelled":
        return <AlertCircle className="h-4 w-4 text-orange-600" />;
      default:
        return <Phone className="h-4 w-4 text-gray-600" />;
    }
  };

  const getOutcomeBadge = (outcome: string) => {
    switch (outcome) {
      case "booked":
        return <Badge className="bg-green-100 text-green-800">Booked</Badge>;
      case "no_show":
        return <Badge className="bg-red-100 text-red-800">No Show</Badge>;
      case "cancelled":
        return <Badge className="bg-orange-100 text-orange-800">Cancelled</Badge>;
      default:
        return <Badge variant="outline">Unknown</Badge>;
    }
  };

  return (
    <SidebarProvider>
      <div className="flex min-h-screen w-full">
        <DashboardSidebar />
        
        <main className="flex-1 bg-background">
          <header className="h-16 flex items-center border-b px-4 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 sticky top-0 z-50">
            <div className="flex-1">
              <h1 className="text-xl font-semibold">Call History</h1>
            </div>
            <div className="flex items-center gap-2">
              <DateRangeSelector 
                selectedRange={dateRange} 
                onRangeChange={setDateRange} 
              />
              <ThemeToggle />
            </div>
          </header>

          <div className="container mx-auto px-4 py-8">
            {/* Live Status */}
            {isLiveConnected && (
              <Card className="mb-6">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
                    Live Call Monitoring
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid gap-4 md:grid-cols-3">
                    <div className="text-center">
                      <div className="text-2xl font-bold text-green-600">
                        {liveCallEvents?.filter(e => e.type === 'call_started').length || 0}
                      </div>
                      <p className="text-sm text-muted-foreground">Calls Today</p>
                    </div>
                    <div className="text-center">
                      <div className="text-2xl font-bold text-blue-600">
                        {liveCallEvents?.filter(e => e.type === 'appointment_booked').length || 0}
                      </div>
                      <p className="text-sm text-muted-foreground">Bookings Today</p>
                    </div>
                    <div className="text-center">
                      <div className="text-2xl font-bold text-purple-600">
                        {liveTranscripts?.length || 0}
                      </div>
                      <p className="text-sm text-muted-foreground">Active Transcripts</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Filters and Search */}
            <Card className="mb-6">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Filter className="h-5 w-5" />
                  Filter & Search
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-col md:flex-row gap-4">
                  <div className="flex-1">
                    <div className="relative">
                      <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                      <Input
                        placeholder="Search by name, phone, or service..."
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                        className="pl-10"
                      />
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant={selectedOutcome === "all" ? "default" : "outline"}
                      size="sm"
                      onClick={() => setSelectedOutcome("all")}
                    >
                      All
                    </Button>
                    <Button
                      variant={selectedOutcome === "booked" ? "default" : "outline"}
                      size="sm"
                      onClick={() => setSelectedOutcome("booked")}
                    >
                      Booked
                    </Button>
                    <Button
                      variant={selectedOutcome === "no_show" ? "default" : "outline"}
                      size="sm"
                      onClick={() => setSelectedOutcome("no_show")}
                    >
                      No Show
                    </Button>
                    <Button
                      variant={selectedOutcome === "cancelled" ? "default" : "outline"}
                      size="sm"
                      onClick={() => setSelectedOutcome("cancelled")}
                    >
                      Cancelled
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Call History Table */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center justify-between">
                  <span className="flex items-center gap-2">
                    <Phone className="h-5 w-5" />
                    Call History ({filteredCalls.length} calls)
                  </span>
                  <Button variant="outline" size="sm">
                    <Download className="h-4 w-4 mr-2" />
                    Export
                  </Button>
                </CardTitle>
              </CardHeader>
              <CardContent>
                {filteredCalls.length === 0 ? (
                  <div className="text-center py-8">
                    <Phone className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                    <p className="text-muted-foreground">No calls found matching your criteria</p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {filteredCalls.map((call, index) => (
                      <div key={index} className="border rounded-lg p-4 hover:bg-muted/50 transition-colors">
                        <div className="flex items-start justify-between">
                          <div className="flex-1">
                            <div className="flex items-center gap-3 mb-2">
                              {getOutcomeIcon(call.outcome)}
                              <div>
                                <h3 className="font-medium">
                                  {call.callerNameMasked || "Unknown Caller"}
                                </h3>
                                <p className="text-sm text-muted-foreground">
                                  {call.phoneNumber || "No phone number"}
                                </p>
                              </div>
                              {getOutcomeBadge(call.outcome)}
                            </div>
                            
                            <div className="grid gap-2 md:grid-cols-2 lg:grid-cols-4 text-sm">
                              <div className="flex items-center gap-2">
                                <Calendar className="h-4 w-4 text-muted-foreground" />
                                <span>{format(parseISO(call.timestamp), "MMM d, yyyy")}</span>
                              </div>
                              <div className="flex items-center gap-2">
                                <Clock className="h-4 w-4 text-muted-foreground" />
                                <span>{format(parseISO(call.timestamp), "h:mm a")}</span>
                              </div>
                              <div className="flex items-center gap-2">
                                <User className="h-4 w-4 text-muted-foreground" />
                                <span>{call.intent || "No service specified"}</span>
                              </div>
                              <div className="flex items-center gap-2">
                                <MessageSquare className="h-4 w-4 text-muted-foreground" />
                                <span>{call.duration || 0} minutes</span>
                              </div>
                            </div>

                            {call.transcript && (
                              <div className="mt-3 p-3 bg-muted/30 rounded-lg">
                                <p className="text-sm text-muted-foreground">
                                  <strong>Transcript:</strong> {call.transcript.substring(0, 200)}
                                  {call.transcript.length > 200 && "..."}
                                </p>
                              </div>
                            )}
                          </div>
                          
                          <div className="flex gap-2 ml-4">
                            <Button variant="outline" size="sm">
                              <Play className="h-4 w-4 mr-2" />
                              Play
                            </Button>
                            <Button variant="outline" size="sm">
                              <MessageSquare className="h-4 w-4 mr-2" />
                              View
                            </Button>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </main>
      </div>
    </SidebarProvider>
  );
};

export default CallHistory;
