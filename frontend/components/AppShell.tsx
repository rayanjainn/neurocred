"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState, useEffect, useRef } from "react";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { useTheme } from "next-themes";
import { useAuth } from "@/dib/authContext";
import { cn } from "@/dib/utils";
import {
  Bell,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  LogOut,
  Menu,
  LayoutDashboard,
  FileText,
  Briefcase,
  AlertTriangle,
  Calendar,
  HelpCircle,
  ListChecks,
  Shield,
  Network,
  Settings,
  Users,
  Building2,
  Key,
  ClipboardList,
  TrendingUp,
  Search,
  Database,
  GitBranch,
  Moon,
  Sun,
  Compass,
} from "lucide-react";
import { VoiceControlButton } from "@/src/components/navbar/VoiceControlButton";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { ScrollArea } from "@/components/ui/scroll-area";

// ---- Nav items per role ----
const NAV_ITEMS: Record<
  string,
  { label: string; href: string; icon: React.ElementType }[]
> = {
  msme: [
    { label: "Dashboard", href: "/msme/dashboard", icon: LayoutDashboard },
    { label: "Score Report", href: "/msme/score-report", icon: FileText },
    { label: "Loans", href: "/msme/loans", icon: Briefcase },
    { label: "Disputes", href: "/msme/disputes", icon: AlertTriangle },
    { label: "Reminders", href: "/msme/reminders", icon: Calendar },
    { label: "Strategy Lab", href: "/msme/strategy-lab", icon: Compass },
    { label: "Guide", href: "/msme/guide", icon: HelpCircle },
  ],
  loan_officer: [
    { label: "Loan Queue", href: "/bank/loan-queue", icon: ListChecks },
    { label: "Strategy Lab", href: "/bank/strategy-lab", icon: Compass },
    { label: "Decisions", href: "/bank/decisions", icon: FileText },
  ],
  credit_analyst: [
    { label: "SHAP Explorer", href: "/analyst/shap-explorer", icon: Search },
    { label: "Data Explorer", href: "/analyst/data-explorer", icon: Database },
    {
      label: "Signal Trends",
      href: "/analyst/signal-trends",
      icon: TrendingUp,
    },
    {
      label: "Dispute Queue",
      href: "/analyst/dispute-queue",
      icon: AlertTriangle,
    },
    { label: "Strategy Lab", href: "/analyst/strategy-lab", icon: Compass },
  ],
  risk_manager: [
    { label: "Fraud Queue", href: "/risk/fraud-queue", icon: Shield },
    { label: "Fraud Topology", href: "/risk/fraud-topology", icon: Network },
    { label: "Strategy Lab", href: "/risk/strategy-lab", icon: Compass },
    { label: "Thresholds", href: "/risk/thresholds", icon: Settings },
  ],
  admin: [
    { label: "Overview", href: "/admin/overview", icon: LayoutDashboard },
    { label: "API Keys", href: "/admin/api-keys", icon: Key },
    { label: "Users", href: "/admin/users", icon: Users },
    { label: "Banks", href: "/admin/banks", icon: Building2 },
    { label: "Audit Log", href: "/admin/audit-log", icon: ClipboardList },
  ],
};

const ROLE_LABELS: Record<string, string> = {
  msme: "MSME Owner",
  loan_officer: "Loan Officer",
  credit_analyst: "Credit Analyst",
  risk_manager: "Risk Manager",
  admin: "Admin",
};

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, logout, notifications, markRead, markAllRead, unreadCount } =
    useAuth();
  const { theme, setTheme, resolvedTheme } = useTheme();
  const pathname = usePathname();
  const router = useRouter();
  const [mounted, setMounted] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);
  const [notifVisible, setNotifVisible] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const mainRef = useRef<HTMLElement>(null);
  const notifPanelRef = useRef<HTMLDivElement>(null);

  // When opening: set visible first so panel mounts, then animate in
  useEffect(() => {
    if (notifOpen) setNotifVisible(true);
  }, [notifOpen]);

  // Animate IN — fires after panel mounts (notifVisible → true → DOM renders)
  useEffect(() => {
    if (notifVisible && notifPanelRef.current) {
      gsap.fromTo(
        notifPanelRef.current,
        { opacity: 0, scale: 0.04, transformOrigin: "top right" },
        {
          opacity: 1,
          scale: 1,
          transformOrigin: "top right",
          duration: 0.5,
          ease: "back.out(1.5)",
        },
      );
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [notifVisible]);

  // Animate OUT — fires when notifOpen flips false while panel is visible
  useEffect(() => {
    if (!notifOpen && notifVisible && notifPanelRef.current) {
      gsap.to(notifPanelRef.current, {
        opacity: 0,
        scale: 0.05,
        transformOrigin: "top right",
        duration: 0.35,
        ease: "back.in(1.4)",
        onComplete: () => setNotifVisible(false),
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [notifOpen]);

  const closeNotif = () => setNotifOpen(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    const stored = window.localStorage.getItem("app.sidebarCollapsed");
    if (stored === "1") {
      setSidebarCollapsed(true);
    }
  }, []);

  useEffect(() => {
    window.localStorage.setItem("app.sidebarCollapsed", sidebarCollapsed ? "1" : "0");
  }, [sidebarCollapsed]);

  useGSAP(
    () => {
      if (!mainRef.current) return;
      gsap.fromTo(
        mainRef.current,
        { opacity: 0, y: 15 },
        { opacity: 1, y: 0, duration: 0.6, ease: "power3.out", delay: 0.1 },
      );
    },
    { scope: mainRef, dependencies: [pathname] },
  );

  const isDark = (resolvedTheme ?? theme) === "dark";

  if (!user)
    return (
      <>
        <div className="fixed top-4 right-4 z-[70]">
          <Button
            type="button"
            variant="ghost"
            size="icon"
            aria-label="Toggle theme"
            onClick={() => mounted && setTheme(isDark ? "light" : "dark")}
            className="rounded-full border border-border bg-card/80 backdrop-blur-md"
          >
            {mounted && isDark ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
          </Button>
        </div>
        {children}
      </>
    );

  const navItems = NAV_ITEMS[user.role] || [];
  const currentItem = navItems.find((item) => pathname.startsWith(item.href));

  const handleLogout = () => {
    logout();
  };

  const MobileMenuContent = () => (
    <div className="h-full flex flex-col">
      <div className="px-4 py-3 border-b">
        <p className="text-sm font-semibold">Menu</p>
        <p className="text-xs text-muted-foreground">
          {ROLE_LABELS[user.role]}
        </p>
      </div>
      <nav className="p-3 space-y-1">
        {navItems.map((item) => {
          const Icon = item.icon;
          const active = pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={() => setMenuOpen(false)}
              className={cn(
                "flex items-center gap-2.5 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                active
                  ? "bg-primary text-primary-foreground"
                  : "text-foreground hover:bg-muted",
              )}
            >
              <Icon className="w-4 h-4 shrink-0" />
              {item.label}
            </Link>
          );
        })}
      </nav>
    </div>
  );

  return (
    <div className="min-h-screen w-full">
      <div className="flex min-h-screen w-full">
        <aside
          className={cn(
            "sticky top-0 h-screen overflow-hidden hidden md:flex shrink-0 border-r border-white/20 bg-background/60 backdrop-blur-2xl shadow-[8px_0_32px_rgba(0,0,0,0.25)] transition-all duration-300 z-50",
            sidebarCollapsed ? "w-20" : "w-72",
          )}
        >
          <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-white/14 via-white/6 to-transparent dark:from-white/8 dark:via-white/4 dark:to-transparent" />
          <div className="relative z-10 flex h-full w-full flex-col">
            <div className={cn("flex h-16 items-center border-b border-border/60 px-3", sidebarCollapsed ? "justify-center" : "gap-3 px-4") }>
              <div className="w-8 h-8 rounded-full bg-primary/15 flex items-center justify-center shrink-0 border border-primary/20">
                <GitBranch className="w-4 h-4 text-primary" />
              </div>
              {!sidebarCollapsed && (
                <div>
                  <p className="text-sm font-semibold tracking-tight">MSME Credit</p>
                  <p className="text-[11px] text-muted-foreground">{ROLE_LABELS[user.role]}</p>
                </div>
              )}
            </div>

            <ScrollArea className={cn("flex-1 py-3", sidebarCollapsed ? "px-2" : "px-3")}>
              <nav className="space-y-1">
                {navItems.map((item) => {
                  const Icon = item.icon;
                  const active = pathname.startsWith(item.href);
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      title={item.label}
                      className={cn(
                        "flex items-center rounded-lg px-3 py-3 transition-colors",
                        sidebarCollapsed ? "justify-center" : "gap-3",
                        active
                          ? "bg-primary text-primary-foreground"
                          : "text-foreground/80 hover:bg-muted hover:text-foreground",
                      )}
                    >
                      <Icon className="w-5 h-5 shrink-0" />
                      {!sidebarCollapsed && <span className="text-[15px] font-semibold">{item.label}</span>}
                    </Link>
                  );
                })}
              </nav>
            </ScrollArea>

            <div className="border-t border-white/15 p-3 space-y-1.5">
              <Button
                type="button"
                variant="ghost"
                onClick={handleLogout}
                className={cn(
                  "w-full text-foreground/80 hover:bg-destructive/10 hover:text-destructive transition-colors rounded-lg",
                  sidebarCollapsed ? "justify-center px-0" : "justify-start gap-3 px-3"
                )}
                title="Log out"
              >
                <LogOut className="w-5 h-5 shrink-0" />
                {!sidebarCollapsed && <span className="text-[15px] font-semibold">Log out</span>}
              </Button>
              <Button
                type="button"
                variant="ghost"
                onClick={() => setSidebarCollapsed((v) => !v)}
                className={cn(
                  "w-full text-foreground/80 hover:bg-muted hover:text-foreground transition-colors rounded-lg",
                  sidebarCollapsed ? "justify-center px-0" : "justify-start gap-3 px-3"
                )}
                title={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
              >
                {sidebarCollapsed ? <ChevronRight className="w-5 h-5 shrink-0" /> : <ChevronLeft className="w-5 h-5 shrink-0" />}
                {!sidebarCollapsed && <span className="text-[15px] font-semibold">Collapse menu</span>}
              </Button>
            </div>
          </div>
        </aside>

        <div className="flex min-h-screen min-w-0 flex-1 flex-col">
          <header className="sticky top-0 z-40 h-16 border-b border-border/60 bg-background/85 backdrop-blur-md px-4 sm:px-6">
            <div className="h-full flex items-center justify-between gap-3">
              <div className="flex items-center gap-2 min-w-0">
                <Sheet open={menuOpen} onOpenChange={setMenuOpen}>
                  <SheetTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="md:hidden shrink-0"
                    >
                      <Menu className="w-5 h-5" />
                    </Button>
                  </SheetTrigger>
                  <SheetContent
                    side="left"
                    className="p-0 w-64 glass-popover border-none"
                  >
                    <SheetHeader className="sr-only">
                      <SheetTitle>Navigation</SheetTitle>
                    </SheetHeader>
                    <MobileMenuContent />
                  </SheetContent>
                </Sheet>

                <div className="min-w-0">
                  <p className="text-[11px] uppercase tracking-[0.12em] text-muted-foreground">
                    Dashboard
                  </p>
                  <p className="text-sm font-semibold truncate">
                    {currentItem?.label ?? "Overview"}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2">
              <VoiceControlButton />
              <Button
                type="button"
                variant="ghost"
                size="icon"
                aria-label="Toggle theme"
                onClick={() => mounted && setTheme(isDark ? "light" : "dark")}
                className="rounded-full"
              >
                {mounted && isDark ? <Sun className="w-4.5 h-4.5" /> : <Moon className="w-4.5 h-4.5" />}
              </Button>

              {/* Notifications — glass popover panel */}
              <div className="relative">
                <Button
                  variant="ghost"
                  size="icon"
                  className="relative"
                  onClick={() => setNotifOpen((v) => !v)}
                >
                  <Bell className="w-5 h-5" />
                  {unreadCount > 0 && (
                    <span className="absolute -top-0.5 -right-0.5 w-4 h-4 bg-destructive text-destructive-foreground text-[10px] font-bold rounded-full flex items-center justify-center">
                      {unreadCount}
                    </span>
                  )}
                </Button>

                {notifVisible && (
                  <>
                    {/* Backdrop dismiss */}
                    <div className="fixed inset-0 z-40" onClick={closeNotif} />
                    {/* Panel — fixed to escape header overflow-hidden */}
                    <div
                      ref={notifPanelRef}
                      className="fixed right-4 top-20 z-[100] w-80 rounded-2xl overflow-hidden"
                      style={{
                        background: "rgba(255,255,255,0.03)",
                        backdropFilter: "blur(14px)",
                        WebkitBackdropFilter: "blur(14px)",
                        border: "1px solid rgba(255,255,255,0.08)",
                        boxShadow:
                          "0 16px 48px rgba(0,0,0,0.55), inset 0 1px 0 rgba(255,255,255,0.06)",
                      }}
                    >
                      {/* Header */}
                      <div className="flex items-center justify-between px-4 py-3 border-b border-white/10">
                        <div className="flex items-center gap-2">
                          <Bell className="w-4 h-4 text-primary" />
                          <span className="text-sm font-semibold">
                            Notifications
                          </span>
                          {unreadCount > 0 && (
                            <span className="text-[10px] font-bold bg-primary text-primary-foreground px-1.5 py-0.5 rounded-full">
                              {unreadCount}
                            </span>
                          )}
                        </div>
                        {unreadCount > 0 && (
                          <button
                            onClick={markAllRead}
                            className="text-xs text-primary hover:text-primary/70 font-medium transition-colors"
                          >
                            Mark all read
                          </button>
                        )}
                      </div>

                      {/* Items */}
                      <div className="max-h-[360px] overflow-y-auto">
                        {notifications.length === 0 ? (
                          <div className="flex flex-col items-center justify-center py-10 gap-2 text-muted-foreground">
                            <Bell className="w-8 h-8 opacity-30" />
                            <p className="text-sm">No notifications</p>
                          </div>
                        ) : (
                          <div>
                            {notifications.map((n) => (
                              <div
                                key={n.id}
                                onClick={() => {
                                  markRead(n.id);
                                  closeNotif();
                                  router.push(n.action_url);
                                }}
                                className={cn(
                                  "flex items-start gap-3 px-4 py-3 cursor-pointer transition-colors border-b border-white/6 last:border-0",
                                  !n.read
                                    ? "bg-primary/8 hover:bg-primary/14"
                                    : "hover:bg-white/4",
                                )}
                              >
                                {/* Read indicator dot */}
                                <div className="mt-1.5 shrink-0">
                                  {!n.read ? (
                                    <span className="block w-2 h-2 rounded-full bg-primary shadow-sm shadow-primary/50" />
                                  ) : (
                                    <span className="block w-2 h-2 rounded-full bg-transparent" />
                                  )}
                                </div>
                                <div className="flex-1 min-w-0">
                                  <p
                                    className={cn(
                                      "text-sm leading-tight",
                                      !n.read
                                        ? "font-semibold text-foreground"
                                        : "font-medium text-foreground/80",
                                    )}
                                  >
                                    {n.title}
                                  </p>
                                  <p className="text-xs text-muted-foreground mt-0.5 leading-relaxed line-clamp-2">
                                    {n.body}
                                  </p>
                                  <p className="text-[10px] text-muted-foreground/60 mt-1 font-medium">
                                    {new Date(n.created_at).toLocaleDateString(
                                      "en-IN",
                                      {
                                        day: "numeric",
                                        month: "short",
                                        hour: "2-digit",
                                        minute: "2-digit",
                                      },
                                    )}
                                  </p>
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  </>
                )}
              </div>

              {/* User dropdown */}
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="rounded-full gap-2 px-3"
                  >
                    <div className="w-6 h-6 rounded-full bg-primary text-primary-foreground text-xs font-bold flex flex-row items-center justify-center shrink-0 shadow-sm border border-primary/20">
                      {user.name.charAt(0)}
                    </div>
                    <div className="hidden sm:flex items-center shrink-0 mx-1">
                      <span className="hidden sm:block text-sm font-medium tracking-tight">
                        {user.name.split(" ")[0]}
                      </span>
                    </div>
                    <ChevronDown className="hidden sm:block w-3 h-3 shrink-0 opacity-70" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent
                  align="end"
                  className="w-52 p-0 overflow-hidden rounded-2xl border-0"
                  style={{
                    background: "rgba(255,255,255,0.03)",
                    backdropFilter: "blur(14px)",
                    WebkitBackdropFilter: "blur(14px)",
                    border: "1px solid rgba(255,255,255,0.08)",
                    boxShadow:
                      "0 16px 48px rgba(0,0,0,0.55), inset 0 1px 0 rgba(255,255,255,0.06)",
                  }}
                >
                  <div className="px-3 py-2.5 border-b border-white/10">
                    <p className="text-sm font-semibold text-foreground">
                      {user.name}
                    </p>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {ROLE_LABELS[user.role]}
                    </p>
                  </div>
                  <div className="p-1">
                    <DropdownMenuItem
                      onClick={handleLogout}
                      className="flex items-center gap-2 px-3 py-2 rounded-xl text-destructive focus:text-destructive focus:bg-destructive/10 cursor-pointer"
                    >
                      <LogOut className="w-4 h-4" />
                      <span className="text-sm font-medium">Sign out</span>
                    </DropdownMenuItem>
                  </div>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
            </div>
          </header>

          <main
            ref={mainRef}
            className="flex-1 w-full px-4 sm:px-6 py-6 overflow-visible"
          >
            {children}
          </main>
        </div>
      </div>
    </div>
  );
}
