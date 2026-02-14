"use client";

import React, { createContext, useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import {
  getToken,
  setToken as storeToken,
  removeToken,
  decodeToken,
  isTokenExpired,
} from "@/lib/auth";
import type { User } from "@/lib/types";

interface AuthContextValue {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    const savedToken = getToken();
    if (savedToken && !isTokenExpired(savedToken)) {
      setToken(savedToken);
      const payload = decodeToken(savedToken);
      if (payload) {
        // Fetch full user profile
        api.auth
          .me()
          .then((u) => setUser(u))
          .catch(() => {
            removeToken();
            setToken(null);
          })
          .finally(() => setIsLoading(false));
        return;
      }
    } else if (savedToken) {
      removeToken();
    }
    setIsLoading(false);
  }, []);

  const login = useCallback(
    async (email: string, password: string) => {
      const res = await api.auth.login(email, password);
      storeToken(res.access_token);
      setToken(res.access_token);
      setUser(res.user);
      router.push("/dashboard");
    },
    [router]
  );

  const logout = useCallback(() => {
    removeToken();
    setToken(null);
    setUser(null);
    router.push("/login");
  }, [router]);

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isAuthenticated: !!user && !!token,
        isLoading,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}
