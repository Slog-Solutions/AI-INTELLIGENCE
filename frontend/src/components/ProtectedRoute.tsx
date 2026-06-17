import { Navigate } from "react-router-dom";
import type { ReactElement } from "react";
import { isAuthenticated } from "../services/auth";

interface ProtectedRouteProps {
  children: ReactElement;
}

export default function ProtectedRoute({ children }: ProtectedRouteProps) {
  if (!isAuthenticated()) {
    return <Navigate to="/" replace />;
  }
  return children;
}
