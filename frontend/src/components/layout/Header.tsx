"use client";

import React from "react";
import { LogOut, Menu } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { Badge } from "@/components/ui/Badge";

interface HeaderProps {
  onMenuToggle: () => void;
}

export function Header({ onMenuToggle }: HeaderProps) {
  const { user, logout } = useAuth();

  return (
    <header className="flex h-16 items-center justify-between border-b border-gray-200 bg-white px-4 lg:px-6">
      <div className="flex items-center gap-3">
        <button
          onClick={onMenuToggle}
          className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600 lg:hidden"
        >
          <Menu className="h-5 w-5" />
        </button>
        <span className="text-sm font-medium text-gray-500">
          AARS Dashboard
        </span>
      </div>

      <div className="flex items-center gap-4">
        {user && (
          <>
            <span className="text-sm text-gray-700">{user.full_name}</span>
            <Badge variant="info">
              {user.roles[0]?.replace(/_/g, " ")}
            </Badge>
            <button
              onClick={logout}
              className="rounded p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
              title="Logout"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </>
        )}
      </div>
    </header>
  );
}
