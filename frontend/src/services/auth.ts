import { jwtDecode } from "jwt-decode";

const TOKEN_KEY = "access_token";
const USER_KEY = "atip_user";

export interface JwtPayload {
  sub: string;
  exp: number;
}

export interface UserSession {
  id: number;
  username: string;
  email: string;
  full_name: string;
  role: string;
  department_id?: number;
  unit_id?: number;
}

export function setAuthSession(token: string, user: UserSession) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function getAuthToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function getAuthUser(): UserSession | null {
  const userJson = localStorage.getItem(USER_KEY);
  return userJson ? (JSON.parse(userJson) as UserSession) : null;
}

export function clearAuthSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

export function isTokenExpired(token: string) {
  try {
    const decoded = jwtDecode<JwtPayload>(token);
    return decoded.exp * 1000 < Date.now();
  } catch {
    return true;
  }
}

export function isAuthenticated() {
  const token = getAuthToken();
  if (!token) return false;
  return !isTokenExpired(token);
}

export function requireRole(roles: string[]) {
  const user = getAuthUser();
  return user ? roles.includes(user.role) : false;
}
