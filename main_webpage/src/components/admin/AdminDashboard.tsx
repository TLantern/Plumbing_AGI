import { useState } from "react";
import { useAdminData } from "@/hooks/useAdminData";
import { AdminSidebar } from "./AdminSidebar";
import { AdminOverview } from "./AdminOverview";
import { AdminSalonsTable } from "./AdminSalonsTable";
import { AdminSalonDetail } from "./AdminSalonDetail";
import { SidebarProvider } from "@/components/ui/sidebar";

type AdminView = "overview" | "salons" | "salon-detail";

export const AdminDashboard = () => {
  const [currentView, setCurrentView] = useState<AdminView>("overview");
  const [selectedSalonId, setSelectedSalonId] = useState<string | null>(null);
  const { 
    salons, 
    platformMetrics, 
    loading, 
    error,
    isLiveConnected,
    liveMetrics,
    allCallEvents,
    allTranscripts,
    allAppointments,
    todaysStats,
    getSalonData
  } = useAdminData();

  const handleViewSalon = (salonId: string) => {
    setSelectedSalonId(salonId);
    setCurrentView("salon-detail");
  };

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-destructive mb-2">Error Loading Admin Dashboard</h1>
          <p className="text-muted-foreground">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <SidebarProvider>
      <div className="flex min-h-screen w-full">
        <AdminSidebar 
          currentView={currentView} 
          onViewChange={setCurrentView}
        />
        
        <main className="flex-1 p-6">
          <div className="max-w-7xl mx-auto">
            {loading ? (
              <div className="flex items-center justify-center h-96">
                <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-primary"></div>
              </div>
            ) : (
              <>
                {currentView === "overview" && (
                  <AdminOverview 
                    platformMetrics={platformMetrics}
                    salons={salons}
                    onViewSalons={() => setCurrentView("salons")}
                    isLiveConnected={isLiveConnected}
                    liveMetrics={liveMetrics}
                    todaysStats={todaysStats}
                  />
                )}
                
                {currentView === "salons" && (
                  <AdminSalonsTable 
                    salons={salons}
                    onViewSalon={handleViewSalon}
                  />
                )}
                
                {currentView === "salon-detail" && selectedSalonId && (
                  <AdminSalonDetail 
                    salonId={selectedSalonId}
                    onBack={() => setCurrentView("salons")}
                  />
                )}
              </>
            )}
          </div>
        </main>
      </div>
    </SidebarProvider>
  );
};