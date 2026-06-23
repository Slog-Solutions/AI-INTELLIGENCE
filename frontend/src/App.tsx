import { BrowserRouter, Routes, Route } from "react-router-dom";
import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import UploadPage from "./pages/UploadPage";
import DocumentsPage from "./pages/DocumentsPage";
import ChatPage from "./pages/ChatPage";
import AnalyticsDetailPage from "./pages/AnalyticsDetailPage";
import ProtectedRoute from "./components/ProtectedRoute";
import NotFoundPage from "./pages/NotFoundPage";
import AppShell from "./components/AppShell";

function SecuredPage({ children }: { children: React.ReactNode }) {
  return (
    <ProtectedRoute>
      <AppShell>{children}</AppShell>
    </ProtectedRoute>
  );
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LoginPage />} />
        <Route
          path="/dashboard"
          element={<SecuredPage><DashboardPage /></SecuredPage>}
        />
        <Route
          path="/upload"
          element={<SecuredPage><UploadPage /></SecuredPage>}
        />
        <Route
          path="/documents"
          element={<SecuredPage><DocumentsPage /></SecuredPage>}
        />
        <Route
          path="/assistant"
          element={<SecuredPage><ChatPage /></SecuredPage>}
        />
        <Route
          path="/documents/:id/analytics"
          element={<SecuredPage><AnalyticsDetailPage /></SecuredPage>}
        />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
