import { useEffect, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { LayoutDashboard, Settings, LogOut, PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { BrandMark } from "@/components/BrandMark";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useApp } from "@/context/AppContext";

const SIDEBAR_KEY = "forinsighter_sidebar_collapsed";

export function AppSidebar() {
  const navigate = useNavigate();
  const location = useLocation();
  const { logout } = useApp();
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem(SIDEBAR_KEY) === "1");

  useEffect(() => {
    localStorage.setItem(SIDEBAR_KEY, collapsed ? "1" : "0");
  }, [collapsed]);

  const handleDashboard = () => {
    if (location.pathname === "/dashboard") {
      window.location.reload();
      return;
    }
    navigate("/dashboard");
  };

  const handleSettings = () => {
    // Placeholder — no action yet
  };

  const handleLogout = () => {
    logout();
    navigate("/");
  };

  const items = [
    { id: "dashboard", label: "Dashboards", icon: LayoutDashboard, onClick: handleDashboard },
    { id: "settings", label: "Settings", icon: Settings, onClick: handleSettings },
    { id: "logout", label: "Log out", icon: LogOut, onClick: handleLogout },
  ] as const;

  return (
    <aside
      className={cn(
        "relative border-r border-border bg-card flex flex-col transition-[width] duration-200 ease-out shrink-0",
        collapsed ? "w-14" : "w-64",
      )}
    >
      <div
        className={cn(
          "h-14 border-b border-border flex items-center gap-2 px-3",
          collapsed && "justify-center px-2",
        )}
      >
        {!collapsed && (
          <>
            <BrandMark className="h-5 w-5 text-foreground shrink-0" />
            <h2 className="font-semibold text-foreground text-sm truncate flex-1">Forinsighter</h2>
          </>
        )}
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8 shrink-0"
          onClick={() => setCollapsed((c) => !c)}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? <PanelLeftOpen className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
        </Button>
      </div>

      <nav className="flex-1 p-2 space-y-1">
        {items.map((item) => {
          const Icon = item.icon;
          const isActive = item.id === "dashboard" && location.pathname === "/dashboard";
          return (
            <button
              key={item.id}
              type="button"
              onClick={item.onClick}
              title={collapsed ? item.label : undefined}
              className={cn(
                "w-full flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors",
                collapsed && "justify-center px-0",
                isActive
                  ? "bg-primary/10 text-primary font-medium"
                  : "text-foreground hover:bg-muted/60",
                item.id === "logout" && "text-destructive hover:bg-destructive/10 hover:text-destructive",
              )}
            >
              <Icon className="h-4 w-4 shrink-0" />
              {!collapsed && <span>{item.label}</span>}
            </button>
          );
        })}
      </nav>
    </aside>
  );
}
