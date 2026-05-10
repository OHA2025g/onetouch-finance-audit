import React, { useEffect, useMemo, useState } from "react";
import { NavLink, useNavigate, Outlet } from "react-router-dom";
import { SignOut, CaretLeft, Lightning, Sun, Moon, List } from "@phosphor-icons/react";
import { useAuth } from "../lib/auth";
import { useTheme } from "../lib/theme";
import clsx from "clsx";
import { getSidebarNavGroups } from "../lib/routeConfig";
import { MastersFilterProvider } from "../lib/MastersFilterContext";
import Breadcrumbs from "./Breadcrumbs";
import AppErrorBoundary from "./AppErrorBoundary";

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const NAV_SECTIONS = useMemo(() => getSidebarNavGroups(user), [user]);
  const navSectionIds = useMemo(() => NAV_SECTIONS.map((s) => s.id), [NAV_SECTIONS]);
  const navSectionIdsKey = useMemo(() => navSectionIds.join("|"), [navSectionIds]);
  const [openSections, setOpenSections] = useState(() => new Set(navSectionIds));

  // When role changes / nav changes, keep all sections expanded by default.
  useEffect(() => {
    setOpenSections(new Set(navSectionIds));
  }, [navSectionIdsKey, navSectionIds]);

  const doLogout = () => {
    logout();
    navigate("/");
  };

  const closeMobile = () => setMobileNavOpen(false);

  return (
    <div
      className="flex h-screen min-h-0 overflow-hidden bg-zinc-100 dark:bg-background"
      data-testid="app-layout"
    >
      {mobileNavOpen ? (
        <button
          type="button"
          aria-label="Close navigation"
          className="fixed inset-0 z-40 bg-black/50 backdrop-blur-[1px] lg:hidden"
          onClick={closeMobile}
        />
      ) : null}
      <aside
        className={clsx(
          "fixed left-0 top-0 z-50 flex h-screen flex-col overflow-hidden border-r border-zinc-200 bg-white/95 backdrop-blur-xl transition-[transform,width] duration-200 dark:border-zinc-800 dark:bg-zinc-950/95",
          collapsed ? "w-16" : "w-64",
          mobileNavOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"
        )}
        data-testid="sidebar"
      >
        <div className="flex shrink-0 items-center justify-between border-b border-zinc-200 px-4 py-5 dark:border-zinc-800">
          <div className="flex items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center bg-primary text-primary-foreground shadow-sm">
              <Lightning size={14} weight="fill" />
            </div>
            {!collapsed && (
              <div className="flex flex-col leading-none">
                <span className="font-display text-sm font-semibold tracking-tight text-foreground">OneTouch</span>
                <span className="crt-num text-[9px] tracking-[0.08em] text-muted-foreground">Audit · AI</span>
              </div>
            )}
          </div>
          <button
            data-testid="sidebar-collapse-btn"
            onClick={() => setCollapsed((c) => !c)}
            className="text-muted-foreground transition-colors hover:text-foreground"
          >
            <CaretLeft size={14} weight="regular" className={clsx(collapsed && "rotate-180")} />
          </button>
        </div>

        <nav className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden py-3">
          {!collapsed && (
            <div className="crt-overline text-muted-foreground px-4 pb-2">Navigation</div>
          )}
          {NAV_SECTIONS.map((sec) => (
            <div key={sec.id} className="mt-1">
              {!collapsed && sec.title ? (
                <button
                  type="button"
                  className="crt-overline flex w-full items-center justify-between text-muted-foreground px-4 pb-1 pt-3 hover:text-foreground transition-colors"
                  onClick={() =>
                    setOpenSections((prev) => {
                      const next = new Set(prev);
                      if (next.has(sec.id)) next.delete(sec.id);
                      else next.add(sec.id);
                      return next;
                    })
                  }
                  data-testid={`nav-section-toggle-${sec.id}`}
                  aria-expanded={openSections.has(sec.id)}
                >
                  <span className="truncate text-left">{sec.title}</span>
                  <span className="text-[10px] font-mono opacity-70">
                    {openSections.has(sec.id) ? "▾" : "▸"}
                  </span>
                </button>
              ) : null}
              {(collapsed || openSections.has(sec.id) ? sec.items : []).map(({ to, label, icon: Icon }) => {
                const base = typeof to === "string" ? to.split("?")[0] : to.pathname || "";
                const testId = `nav-${sec.id}-${base.replace(/\//g, "-").replace(/^-/, "")}`;
                return (
                  <NavLink
                    key={testId}
                    to={to}
                    data-testid={testId}
                    onClick={closeMobile}
                    className={({ isActive }) =>
                      clsx(
                        "group flex items-center gap-3 border-l-2 px-4 py-2.5 text-sm transition-all duration-150",
                        isActive
                          ? "border-primary bg-muted/90 text-foreground shadow-sm dark:bg-zinc-900/80"
                          : "border-transparent text-muted-foreground hover:bg-muted/60 hover:text-foreground"
                      )
                    }
                  >
                    <Icon size={16} weight="regular" />
                    {!collapsed && <span className="min-w-0 flex-1 truncate">{label}</span>}
                    {!collapsed && (
                      <span className="crt-num shrink-0 text-[9px] uppercase tracking-[0.18em] text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100">
                        →
                      </span>
                    )}
                  </NavLink>
                );
              })}
            </div>
          ))}
        </nav>

        <div className="shrink-0 border-t border-zinc-200 px-4 py-4 dark:border-zinc-800">
          {!collapsed && user && (
            <div className="mb-3">
              <div className="crt-overline text-muted-foreground">Signed in</div>
              <div className="truncate text-sm text-foreground" data-testid="user-name">
                {user.full_name}
              </div>
              <div className="crt-num truncate text-[10px] text-muted-foreground">{user.role}</div>
            </div>
          )}
          <button
            data-testid="logout-btn"
            onClick={doLogout}
            className="flex w-full items-center gap-2 text-xs text-muted-foreground transition-colors hover:text-[hsl(var(--destructive))]"
          >
            <SignOut size={14} /> {!collapsed && "Sign out"}
          </button>
        </div>
      </aside>

      <main
        className={clsx(
          "flex h-screen min-h-0 min-w-0 flex-1 flex-col overflow-hidden transition-[margin] duration-150",
          "ml-0",
          collapsed ? "lg:ml-16" : "lg:ml-64"
        )}
      >
        <TopBar
          sidebarCollapsed={collapsed}
          onOpenMobileNav={() => setMobileNavOpen(true)}
        />
        <div className="min-h-0 flex-1 overflow-y-auto bg-zinc-50 pt-12 dark:bg-zinc-950" data-testid="main-content">
          <Breadcrumbs />
          <AppErrorBoundary>
            <MastersFilterProvider>
              <Outlet />
            </MastersFilterProvider>
          </AppErrorBoundary>
        </div>
      </main>
    </div>
  );
}

function TopBar({ sidebarCollapsed, onOpenMobileNav = () => {} }) {
  const { user } = useAuth();
  const { theme, toggle } = useTheme();
  const [now, setNow] = useState(new Date());
  React.useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 30000);
    return () => clearInterval(t);
  }, []);
  return (
    <header
      className={clsx(
        "fixed right-0 top-0 z-30 flex h-12 items-center justify-between border-b border-zinc-200 bg-white/90 px-4 backdrop-blur-xl transition-[left] duration-150 dark:border-zinc-800 dark:bg-zinc-950/90 sm:px-6",
        "left-0",
        sidebarCollapsed ? "lg:left-16" : "lg:left-64"
      )}
      data-testid="topbar"
    >
      <div className="crt-num flex min-w-0 flex-1 items-center gap-3 text-[10px] font-medium uppercase tracking-[0.15em] text-muted-foreground sm:gap-6">
        <button
          type="button"
          className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-sm border border-zinc-200 text-foreground hover:bg-zinc-100 lg:hidden dark:border-zinc-700 dark:hover:bg-zinc-900"
          aria-label="Open navigation menu"
          data-testid="mobile-nav-open"
          onClick={onOpenMobileNav}
        >
          <List size={18} weight="bold" />
        </button>
        <span className="flex items-center gap-2">
          <span className="pulse-dot h-1.5 w-1.5 rounded-full bg-[hsl(var(--chart-4))]" /> system · live
        </span>
        <span>
          {now.toLocaleString("en-GB", {
            weekday: "short",
            day: "2-digit",
            month: "short",
            hour: "2-digit",
            minute: "2-digit",
            timeZoneName: "short",
          })}
        </span>
      </div>
      <div className="flex items-center gap-3">
        <button
          data-testid="theme-toggle-btn"
          onClick={toggle}
          title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
          aria-label="Toggle theme"
          className="crt-card flex h-8 items-center gap-2 rounded-sm px-3 font-mono text-[10px] uppercase tracking-wider text-muted-foreground transition-colors hover:text-foreground"
        >
          {theme === "dark" ? <Sun size={13} weight="regular" /> : <Moon size={13} weight="regular" />}
          <span>{theme === "dark" ? "light" : "dark"}</span>
        </button>
        {user && (
          <div className="crt-card flex items-center gap-2 rounded-sm px-3 py-1">
            <div className="flex h-6 w-6 items-center justify-center bg-primary text-xs text-primary-foreground crt-num">
              {user.full_name?.[0] || "?"}
            </div>
            <span className="crt-num text-[10px] uppercase tracking-wider text-muted-foreground">{user.role}</span>
          </div>
        )}
      </div>
    </header>
  );
}
