import { Navigate } from "react-router-dom";
import type { ReactElement } from "react";
import { getAuthUser } from "../services/auth";

interface RoleRouteProps {
  children: ReactElement;
  roles: string[];
}

export default function RoleRoute({ children, roles }: RoleRouteProps) {
  const user = getAuthUser();
  if (!user || !roles.includes(user.role)) {
    return <Navigate to="/dashboard" replace />;
  }
  return children;
}
