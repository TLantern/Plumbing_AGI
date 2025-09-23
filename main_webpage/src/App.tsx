import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Routes, Route } from "react-router-dom";
import Index from "./pages/Index";
import Auth from "./pages/Auth";
import Dashboard from "./pages/Dashboard";
import Profile from "./pages/Profile";
import Settings from "./pages/Settings";
import Account from "./pages/Account";
import Admin from "./pages/Admin";
import ShopSettings from "./pages/ShopSettings";

import NotFound from "./pages/NotFound";
import { ProtectedRoute } from "./components/ProtectedRoute";

const queryClient = new QueryClient();

const requireAuthEnv = import.meta.env.VITE_REQUIRE_AUTH;
const requireAuth = (requireAuthEnv === undefined || requireAuthEnv === null || requireAuthEnv === '')
  ? true
  : requireAuthEnv === 'true';

const MaybeProtected = ({ children }: { children: React.ReactNode }) => {
  return requireAuth ? <ProtectedRoute>{children}</ProtectedRoute> : <>{children}</>;
};

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Toaster />
      <Sonner />
      <Routes>
        <Route path="/" element={<Index />} />
        <Route path="/auth" element={<Auth />} />
        
        <Route path="/dashboard" element={<MaybeProtected><Dashboard /></MaybeProtected>} />
        <Route path="/profile" element={<MaybeProtected><Profile /></MaybeProtected>} />
        <Route path="/settings" element={<MaybeProtected><Settings /></MaybeProtected>} />
        <Route path="/settings/shop" element={<MaybeProtected><ShopSettings /></MaybeProtected>} />
        <Route path="/account" element={<MaybeProtected><Account /></MaybeProtected>} />
        <Route path="/admin" element={<MaybeProtected><Admin /></MaybeProtected>} />
        {/* ADD ALL CUSTOM ROUTES ABOVE THE CATCH-ALL "*" ROUTE */}
        <Route path="*" element={<NotFound />} />
      </Routes>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
