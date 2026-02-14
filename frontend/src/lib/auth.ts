import Cookies from "js-cookie";
import { jwtDecode } from "jwt-decode";

const TOKEN_KEY = "aars_token";

interface TokenPayload {
  user_id: string;
  tenant_id: string;
  roles: string[];
  exp: number;
  sub: string;
}

export function getToken(): string | undefined {
  return Cookies.get(TOKEN_KEY);
}

export function setToken(token: string): void {
  Cookies.set(TOKEN_KEY, token, { sameSite: "lax" });
}

export function removeToken(): void {
  Cookies.remove(TOKEN_KEY);
}

export function decodeToken(token: string): TokenPayload | null {
  try {
    return jwtDecode<TokenPayload>(token);
  } catch {
    return null;
  }
}

export function isTokenExpired(token: string): boolean {
  const payload = decodeToken(token);
  if (!payload) return true;
  return payload.exp * 1000 < Date.now();
}

export function getUserFromToken(token: string) {
  const payload = decodeToken(token);
  if (!payload) return null;
  return {
    id: payload.user_id || payload.sub,
    tenant_id: payload.tenant_id,
    roles: payload.roles,
  };
}
