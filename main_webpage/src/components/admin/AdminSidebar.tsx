import { BarChart3, Building2, Settings, Users } from "lucide-react";
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarTrigger,
  useSidebar,
} from "@/components/ui/sidebar";

type AdminView = "overview" | "salons" | "salon-detail";

interface AdminSidebarProps {
  currentView: AdminView;
  onViewChange: (view: AdminView) => void;
}

const adminItems = [
  { 
    title: "Overview", 
    icon: BarChart3, 
    view: "overview" as AdminView,
    description: "Platform metrics and analytics"
  },
  { 
    title: "Salons", 
    icon: Building2, 
    view: "salons" as AdminView,
    description: "Manage all registered salons"
  },
  { 
    title: "Users", 
    icon: Users, 
    view: "users" as AdminView,
    description: "User management and roles"
  },
  { 
    title: "Settings", 
    icon: Settings, 
    view: "settings" as AdminView,
    description: "Platform configuration"
  },
];

export const AdminSidebar = ({ currentView, onViewChange }: AdminSidebarProps) => {
  const { state } = useSidebar();
  const collapsed = state === "collapsed";

  return (
    <Sidebar className={collapsed ? "w-14" : "w-60"} collapsible="icon">
      <div className="p-4 border-b">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center">
            <BarChart3 className="w-4 h-4 text-primary-foreground" />
          </div>
          {!collapsed && (
            <div>
              <h1 className="font-semibold">Admin Dashboard</h1>
              <p className="text-xs text-muted-foreground">Platform Management</p>
            </div>
          )}
        </div>
      </div>

      <SidebarTrigger className="m-2 self-end" />

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Navigation</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {adminItems.map((item) => (
                <SidebarMenuItem key={item.view}>
                  <SidebarMenuButton 
                    onClick={() => onViewChange(item.view)}
                    isActive={currentView === item.view}
                    className="w-full"
                  >
                    <item.icon className="w-4 h-4" />
                    {!collapsed && (
                      <div className="flex flex-col items-start">
                        <span className="font-medium">{item.title}</span>
                        <span className="text-xs text-muted-foreground">
                          {item.description}
                        </span>
                      </div>
                    )}
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
    </Sidebar>
  );
};