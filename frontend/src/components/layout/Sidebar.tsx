"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Users,
  BarChart3,
  Play,
  Brain,
  FileText,
  Settings,
  ChevronLeft,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/hooks/useAuth";

interface NavItem {
  label: string;
  href: string;
  icon: React.ReactNode;
  roles?: string[];
  children?: { label: string; href: string }[];
}

const navItems: NavItem[] = [
  {
    label: "Dashboard",
    href: "/dashboard",
    icon: <LayoutDashboard className="h-5 w-5" />,
  },
  {
    label: "Agents",
    href: "/agents",
    icon: <Users className="h-5 w-5" />,
  },
  {
    label: "Analytics",
    href: "/analytics",
    icon: <BarChart3 className="h-5 w-5" />,
    children: [
      { label: "Overview", href: "/analytics" },
      { label: "Dormancy", href: "/analytics/dormancy" },
      { label: "Reactivation", href: "/analytics/reactivation" },
      { label: "ADM Performance", href: "/analytics/adm-performance" },
      { label: "Training", href: "/analytics/training" },
    ],
  },
  {
    label: "Content",
    href: "/content",
    icon: <FileText className="h-5 w-5" />,
    children: [
      { label: "Templates", href: "/content/templates" },
      { label: "Training", href: "/content/training" },
    ],
  },
  {
    label: "Playbooks",
    href: "/playbooks",
    icon: <Play className="h-5 w-5" />,
  },
  {
    label: "Decisions",
    href: "/decisions",
    icon: <Brain className="h-5 w-5" />,
  },
  {
    label: "Settings",
    href: "/settings",
    icon: <Settings className="h-5 w-5" />,
    roles: ["super_admin", "tenant_admin"],
  },
];

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

export function Sidebar({ collapsed, onToggle }: SidebarProps) {
  const pathname = usePathname();
  const { user } = useAuth();
  const [openSubmenu, setOpenSubmenu] = useState<string | null>(
    pathname.startsWith("/analytics") ? "Analytics" : pathname.startsWith("/content") ? "Content" : null
  );

  const userRoles = user?.roles ?? [];

  const visibleItems = navItems.filter(
    (item) => !item.roles || item.roles.some((r) => (userRoles as string[]).includes(r))
  );

  const isActive = (href: string) => {
    if (href === "/analytics") return pathname === "/analytics";
    return pathname === href || pathname.startsWith(href + "/");
  };

  return (
    <aside
      className={cn(
        "flex h-full flex-col border-r border-gray-200 bg-white transition-all duration-200",
        collapsed ? "w-16" : "w-64"
      )}
    >
      {/* Logo / Brand */}
      <div className="flex h-16 items-center justify-between border-b border-gray-200 px-4">
        {!collapsed && (
          <span className="text-lg font-bold text-gray-900">AARS</span>
        )}
        <button
          onClick={onToggle}
          className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
        >
          {collapsed ? (
            <ChevronRight className="h-5 w-5" />
          ) : (
            <ChevronLeft className="h-5 w-5" />
          )}
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto py-4">
        <ul className="space-y-1 px-2">
          {visibleItems.map((item) => {
            const active = isActive(item.href);
            const hasChildren = !!item.children;
            const submenuOpen = openSubmenu === item.label;

            return (
              <li key={item.label}>
                {hasChildren ? (
                  <>
                    <button
                      onClick={() => {
                        if (collapsed) return;
                        setOpenSubmenu(submenuOpen ? null : item.label);
                      }}
                      className={cn(
                        "flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                        active
                          ? "bg-blue-50 text-blue-700"
                          : "text-gray-700 hover:bg-gray-100"
                      )}
                      title={collapsed ? item.label : undefined}
                    >
                      {item.icon}
                      {!collapsed && (
                        <>
                          <span className="flex-1 text-left">{item.label}</span>
                          <ChevronDown
                            className={cn(
                              "h-4 w-4 transition-transform",
                              submenuOpen && "rotate-180"
                            )}
                          />
                        </>
                      )}
                    </button>
                    {!collapsed && submenuOpen && (
                      <ul className="ml-8 mt-1 space-y-1">
                        {item.children!.map((child) => (
                          <li key={child.href}>
                            <Link
                              href={child.href}
                              className={cn(
                                "block rounded-md px-3 py-1.5 text-sm transition-colors",
                                pathname === child.href
                                  ? "bg-blue-50 text-blue-700 font-medium"
                                  : "text-gray-600 hover:bg-gray-100"
                              )}
                            >
                              {child.label}
                            </Link>
                          </li>
                        ))}
                      </ul>
                    )}
                  </>
                ) : (
                  <Link
                    href={item.href}
                    className={cn(
                      "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                      active
                        ? "bg-blue-50 text-blue-700"
                        : "text-gray-700 hover:bg-gray-100"
                    )}
                    title={collapsed ? item.label : undefined}
                  >
                    {item.icon}
                    {!collapsed && <span>{item.label}</span>}
                  </Link>
                )}
              </li>
            );
          })}
        </ul>
      </nav>

      {/* User info at bottom */}
      {!collapsed && user && (
        <div className="border-t border-gray-200 px-4 py-3">
          <p className="truncate text-sm font-medium text-gray-900">
            {user.full_name}
          </p>
          <p className="truncate text-xs text-gray-500">
            {user.roles[0]?.replace(/_/g, " ")}
          </p>
        </div>
      )}
    </aside>
  );
}
