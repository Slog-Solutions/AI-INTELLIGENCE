import Icon from "./Icons";

export function BrandMark({ compact = false }: { compact?: boolean }) {
  return (
    <div className={`brand-mark ${compact ? "brand-mark--compact" : ""}`}>
      <div className="brand-mark__emblem"><Icon name="shield" size={compact ? 18 : 24} /></div>
      {!compact && (
        <div>
          <strong>ATIP</strong>
          <span>Indian Army Intelligence</span>
        </div>
      )}
    </div>
  );
}

export function StatusBadge({ status = "unknown" }: { status?: string }) {
  const normalized = status.toLowerCase();
  const tone = normalized.includes("process") || normalized.includes("ready") || normalized.includes("complete")
    ? "success"
    : normalized.includes("fail") || normalized.includes("error")
      ? "danger"
      : "warning";
  return <span className={`status-badge status-badge--${tone}`}><i />{status}</span>;
}

export function LoadingState({ label = "Retrieving intelligence data" }: { label?: string }) {
  return (
    <div className="loading-state" role="status">
      <div className="loading-state__radar"><span /></div>
      <p>{label}</p>
    </div>
  );
}

interface EmptyStateProps {
  icon?: "document" | "message" | "analytics" | "upload" | "spark";
  title: string;
  description: string;
  action?: React.ReactNode;
}

export function EmptyState({ icon = "document", title, description, action }: EmptyStateProps) {
  return (
    <div className="empty-state">
      <div className="empty-state__icon"><Icon name={icon} size={26} /></div>
      <h3>{title}</h3>
      <p>{description}</p>
      {action}
    </div>
  );
}

export function ErrorState({
  message = "Unable to retrieve intelligence data.",
  onRetry,
}: {
  message?: string;
  onRetry?: () => void;
}) {
  return (
    <div className="error-state">
      <div className="error-state__icon"><Icon name="alert" /></div>
      <div>
        <strong>Service interruption</strong>
        <p>{message}</p>
      </div>
      {onRetry && <button className="button button--secondary button--small" onClick={onRetry}><Icon name="refresh" />Retry</button>}
    </div>
  );
}

export function PageHeader({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow: string;
  title: string;
  description: string;
  action?: React.ReactNode;
}) {
  return (
    <header className="page-header">
      <div>
        <span className="eyebrow">{eyebrow}</span>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {action && <div className="page-header__action">{action}</div>}
    </header>
  );
}
