import { useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../services/api";
import { setAuthSession } from "../services/auth";
import Icon from "../components/Icons";
import { BrandMark } from "../components/Ui";

export default function LoginPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleLogin = async (event: React.FormEvent) => {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      const response = await api.post("/auth/login", { username, password });
      setAuthSession(response.data.access_token, response.data.user);
      navigate("/dashboard");
    } catch {
      setError("Authentication failed. Verify your credentials and secure service connection.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-grid" />
      <div className="login-scanline" />
      <div className="login-orb login-orb--one" />
      <div className="login-orb login-orb--two" />

      <section className="login-brief">
        <BrandMark />
        <div className="login-brief__content">
          <span className="eyebrow"><i />Restricted command environment</span>
          <h1>ARMY TRAINING<br />INTELLIGENCE PLATFORM</h1>
          <p>Offline AI Defence Intelligence System</p>
          <div className="login-capabilities">
            <div><Icon name="shield" /><span><strong>Protected analysis</strong>Air-gapped intelligence processing</span></div>
            <div><Icon name="activity" /><span><strong>Operational awareness</strong>Training readiness and risk insight</span></div>
            <div><Icon name="lock" /><span><strong>Controlled access</strong>Role-based command authorization</span></div>
          </div>
        </div>
        <small>ATIP // DEFENCE INTELLIGENCE NETWORK // SECURE NODE</small>
      </section>

      <section className="login-panel">
        <div className="login-card">
          <div className="login-card__status"><span><i />System operational</span><span>NODE 01</span></div>
          <div className="login-card__heading">
            <div className="login-card__icon"><Icon name="lock" size={22} /></div>
            <div>
              <span>Secure access</span>
              <h2>Operator authentication</h2>
            </div>
          </div>
          <p className="login-card__intro">Enter your assigned credentials to access the intelligence workspace.</p>
          <form onSubmit={handleLogin}>
            <label className="field-label" htmlFor="username">Username</label>
            <div className="input-shell">
              <Icon name="user" size={18} />
              <input
                id="username"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                placeholder="Operator ID"
                autoComplete="username"
                required
              />
            </div>
            <label className="field-label" htmlFor="password">Password</label>
            <div className="input-shell">
              <Icon name="lock" size={18} />
              <input
                id="password"
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="Secure passphrase"
                autoComplete="current-password"
                required
              />
            </div>
            {error && <div className="form-error"><Icon name="alert" size={16} />{error}</div>}
            <button className="button button--primary login-submit" disabled={loading}>
              {loading ? <><span className="button-spinner" />Authenticating</> : <>Tactical login<Icon name="arrow" /></>}
            </button>
          </form>
          <div className="login-card__footer"><Icon name="shield" size={14} />Authorized personnel only. Activity is monitored.</div>
        </div>
      </section>
    </div>
  );
}
