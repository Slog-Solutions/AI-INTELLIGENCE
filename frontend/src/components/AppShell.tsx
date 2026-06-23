import { useEffect, useState } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { clearAuthSession, getAuthUser } from "../services/auth";
import Icon, { type IconName } from "./Icons";
import { BrandMark } from "./Ui";
import { chatApi } from "../services/api";

const navigation: Array<{ to: string; label: string; icon: IconName }> = [
  { to: "/assistant", label: "New Chat", icon: "message" },
  { to: "/documents", label: "Intelligence Library", icon: "library" },
  { to: "/dashboard", label: "Analytics Workspace", icon: "analytics" },
  { to: "/upload", label: "Upload Center", icon: "upload" },
];

export default function AppShell({ children }: { children: React.ReactNode }) {
  const user = getAuthUser();
  const navigate = useNavigate();
  const location = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [recentConversations, setRecentConversations] = useState<any[]>([]);

  useEffect(() => setSidebarOpen(false), [location.pathname]);

  useEffect(() => {
    loadConversations();
  }, [location.pathname]); // Reload when navigating

  const loadConversations = async () => {
    try {
      const response = await chatApi.getConversations();
      setRecentConversations(response.data);
    } catch (error) {
      console.error("Failed to load conversations", error);
    }
  };

  const deleteConversation = async (e: React.MouseEvent, id: number) => {
    e.preventDefault();
    e.stopPropagation();
    if (confirm("Delete this conversation?")) {
      try {
        await chatApi.deleteConversation(id);
        setRecentConversations(prev => prev.filter(c => c.id !== id));
        if (location.search.includes(`c=${id}`)) {
          navigate("/assistant");
        }
      } catch (error) {
        console.error("Failed to delete chat", error);
      }
    }
  };

  const logout = () => {
    clearAuthSession();
    navigate("/");
  };

  const filteredRecent = recentConversations.filter((item) =>
    item.title.toLowerCase().includes(search.toLowerCase()),
  );

  return (
    <div className="app-shell">
      <button className="mobile-menu" onClick={() => setSidebarOpen(true)} aria-label="Open navigation">
        <Icon name="menu" />
      </button>
      {sidebarOpen && <button className="sidebar-scrim" onClick={() => setSidebarOpen(false)} aria-label="Close navigation" />}
      <aside className={`sidebar ${sidebarOpen ? "sidebar--open" : ""}`}>
        <div className="sidebar__header">
          <BrandMark />
          <button className="sidebar__close" onClick={() => setSidebarOpen(false)} aria-label="Close navigation"><Icon name="close" /></button>
          <button className="new-chat-button" onClick={() => navigate("/assistant")}>
            <Icon name="plus" />
            New intelligence chat
          </button>
        </div>

        <nav className="primary-nav" aria-label="Primary navigation">
          <span className="sidebar-label">Command modules</span>
          {navigation.map((item) => (
            <NavLink key={item.to} to={item.to} className={({ isActive }) => `nav-item ${isActive ? "nav-item--active" : ""}`}>
              <Icon name={item.icon} />
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>

        <section className="recent-section">
          <span className="sidebar-label">Recent conversations</span>
          <label className="sidebar-search">
            <Icon name="search" size={15} />
            <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search conversations" />
          </label>
          <div className="recent-list">
            {filteredRecent.map((item) => (
              <div key={item.id} className="recent-item-row">
                <button onClick={() => navigate(`/assistant?c=${item.id}`)} className={location.search.includes(`c=${item.id}`) ? "active" : ""}>
                  <Icon name="message" size={15} />
                  <span>{item.title}</span>
                </button>
                <button className="delete-action" onClick={(e) => deleteConversation(e, item.id)}>
                  <Icon name="close" size={12} />
                </button>
              </div>
            ))}
            {!filteredRecent.length && <p>No matching conversations</p>}
          </div>
        </section>

        <div className="sidebar__footer">
          <div className="user-card">
            <div className="user-avatar">{(user?.full_name || user?.username || "U").charAt(0).toUpperCase()}</div>
            <div>
              <strong>{user?.full_name || user?.username || "Operator"}</strong>
              <span>{user?.role || "Authorized user"}</span>
            </div>
            <button onClick={logout} aria-label="Logout"><Icon name="logout" size={17} /></button>
          </div>
          <div className="secure-indicator"><i />Indian Army secure environment</div>
        </div>
      </aside>
      <main className="app-main">{children}</main>
    </div>
  );
}
