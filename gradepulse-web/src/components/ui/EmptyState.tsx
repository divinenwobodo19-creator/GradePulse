import type { ReactNode } from "react";

// The "nothing here yet" panel used across the app: an optional icon, a
// heading, an optional line of guidance and an optional action button.
export default function EmptyState({
  icon,
  heading,
  body,
  action,
}: {
  icon?: ReactNode;
  heading: string;
  body?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="empty-state" data-testid="empty-state">
      {icon && <div className="empty-state-icon">{icon}</div>}
      <h3 className="heading-3 text-navy mb-1">{heading}</h3>
      {body && <p className={`body-sm text-text-muted${action ? " mb-4" : ""}`}>{body}</p>}
      {action}
    </div>
  );
}
