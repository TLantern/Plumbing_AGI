import { SidebarProvider } from "@/components/ui/sidebar";
import { DashboardSidebar } from "@/components/dashboard/DashboardSidebar";
import { GoogleCalendar } from "@/components/calendar/GoogleCalendar";
import { useGoogleOAuth } from "@/hooks/useGoogleOAuth";

const Calendar = () => {
  // Handle Google OAuth callback
  useGoogleOAuth();

  return (
    <SidebarProvider>
      <div className="flex min-h-screen w-full">
        <DashboardSidebar />
        
        <main className="flex-1 bg-background">
          <header className="h-16 flex items-center border-b px-4 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 sticky top-0 z-50">
            <div className="flex-1">
              <h1 className="text-xl font-semibold">Calendar Integration</h1>
            </div>
          </header>

          <div className="container mx-auto px-4 py-8">
            <div className="max-w-4xl mx-auto">
              <GoogleCalendar />
            </div>
          </div>
        </main>
      </div>
    </SidebarProvider>
  );
};

export default Calendar;
