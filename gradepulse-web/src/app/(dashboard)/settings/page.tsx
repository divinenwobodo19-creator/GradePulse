"use client";

import { useState, useEffect, useRef } from "react";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import type { BrainSummary, Invite } from "@/lib/types";

export default function SettingsPage() {
  const { user, loading: authLoading, logout } = useAuth();
  const [toast, setToast] = useState<{ type: string; message: string } | null>(null);
  const [summary, setSummary] = useState<BrainSummary | null>(null);
  const [apiStatus, setApiStatus] = useState<"checking" | "online" | "offline">("checking");
  const [error, setError] = useState("");
  const [invites, setInvites] = useState<Invite[]>([]);
  const [inviting, setInviting] = useState(false);
  const isAdmin = user?.role === "admin";
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const showToast = (type: string, message: string) => {
    if (toastTimer.current) clearTimeout(toastTimer.current);
    setToast({ type, message });
    toastTimer.current = setTimeout(() => setToast(null), 3000);
  };

  useEffect(() => {
    return () => {
      if (toastTimer.current) clearTimeout(toastTimer.current);
    };
  }, []);

  useEffect(() => {
    if (authLoading || !user) return;

    let cancelled = false;
    const controller = new AbortController();
    async function load() {
      const [summaryResult, healthResult] = await Promise.allSettled([
        api.summary(controller.signal),
        api.health(controller.signal),
      ]);
      if (cancelled) return;

      if (summaryResult.status === "fulfilled") {
        setSummary(summaryResult.value);
      } else {
        setError(summaryResult.reason instanceof Error ? summaryResult.reason.message : "Failed to load system summary");
      }

      setApiStatus(
        healthResult.status === "fulfilled" && healthResult.value.status === "alive"
          ? "online"
          : "offline"
      );
    }

    void load();
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [authLoading, user]);

  useEffect(() => {
    if (authLoading || !isAdmin) return;

    const controller = new AbortController();
    api
      .listInvites(controller.signal)
      .then(setInvites)
      .catch((err) => {
        if (!controller.signal.aborted) {
          setError(err instanceof Error ? err.message : "Failed to load invites");
        }
      });
    return () => controller.abort();
  }, [authLoading, isAdmin]);

  const inviteLink = (code: string) => `${window.location.origin}/signup?invite=${encodeURIComponent(code)}`;

  const handleCreateInvite = async () => {
    setInviting(true);
    try {
      const invite = await api.createInvite();
      setInvites((prev) => [invite, ...prev]);
      showToast("success", "Invite created. Send the link to your teacher.");
    } catch (err) {
      showToast("error", err instanceof Error ? err.message : "Could not create invite");
    } finally {
      setInviting(false);
    }
  };

  const handleCopyInvite = async (code: string) => {
    try {
      await navigator.clipboard.writeText(inviteLink(code));
      showToast("success", "Invite link copied");
    } catch {
      showToast("error", "Could not copy. Select the code and copy it by hand.");
    }
  };

  const handleRevokeInvite = async (code: string) => {
    try {
      await api.revokeInvite(code);
      setInvites((prev) => prev.filter((i) => i.code !== code));
      showToast("success", "Invite revoked");
    } catch (err) {
      showToast("error", err instanceof Error ? err.message : "Could not revoke invite");
    }
  };

  return (
    <div className="page-shell max-w-3xl">
      {toast && (
        <div role="status" aria-live="polite" aria-atomic="true" className={`toast toast-${toast.type}`}>
          {toast.type === "success" && (
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
            </svg>
          )}
          {toast.message}
        </div>
      )}

      {/* Header */}
      <div className="page-header">
        <div className="page-header-left">
          <h1 className="heading-display text-navy">Settings</h1>
          <p className="body text-text-secondary">
            Manage your account and system preferences
          </p>
        </div>
      </div>

      {error && (
        <div role="alert" aria-live="assertive" className="bg-danger-light border border-danger/20 text-danger px-4 py-3 rounded-lg text-sm">
          {error}
        </div>
      )}

      {/* Account Section */}
      <div className="card">
        <div className="card-body">
          <div className="flex items-center gap-3 mb-5">
            <div className="w-10 h-10 rounded-xl bg-navy/5 flex items-center justify-center">
              <svg className="w-5 h-5 text-navy" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                <circle cx="12" cy="7" r="4" />
              </svg>
            </div>
            <div>
              <h2 className="heading-2 text-navy">Account</h2>
              <p className="caption text-text-muted">Your account information</p>
            </div>
          </div>

          <div className="space-y-0 divide-y divide-border">
            <div className="flex items-center justify-between py-3.5">
              <span className="body text-text-secondary">Email</span>
              <span className="body font-medium text-navy">{user?.email}</span>
            </div>
            <div className="flex items-center justify-between py-3.5">
              <span className="body text-text-secondary">School</span>
              <span className="body font-medium text-navy">{user?.school_name || "Not set"}</span>
            </div>
            <div className="flex items-center justify-between py-3.5">
              <span className="body text-text-secondary">Role</span>
              <span className="badge badge-neutral">{isAdmin ? "School admin" : "Teacher"}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Teachers (admin only) */}
      {isAdmin && (
        <div className="card">
          <div className="card-body">
            <div className="flex items-center justify-between gap-3 mb-5">
              <div>
                <h2 className="heading-2 text-navy">Invite a Teacher</h2>
                <p className="caption text-text-muted">
                  Each link lets one teacher join {user?.school_name || "your school"} and expires after 7 days
                </p>
              </div>
              <button
                type="button"
                onClick={handleCreateInvite}
                disabled={inviting}
                aria-busy={inviting}
                className="btn btn-primary"
              >
                {inviting ? "Creating..." : "Create Invite"}
              </button>
            </div>

            {invites.length === 0 ? (
              <p className="caption text-text-muted">No pending invites</p>
            ) : (
              <ul className="space-y-2">
                {invites.map((invite) => (
                  <li key={invite.code} className="flex flex-wrap items-center justify-between gap-3 p-4 bg-surface-elevated rounded-xl">
                    <div className="min-w-0">
                      <div className="font-mono text-sm text-navy break-all">{invite.code}</div>
                      <div className="caption text-text-muted mt-0.5">
                        Expires {new Date(invite.expires_at).toLocaleDateString()}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <button type="button" onClick={() => handleCopyInvite(invite.code)} className="btn btn-secondary btn-sm">
                        Copy Link
                      </button>
                      <button
                        type="button"
                        onClick={() => handleRevokeInvite(invite.code)}
                        aria-label={`Revoke invite ${invite.code}`}
                        className="btn btn-ghost btn-sm text-danger"
                      >
                        Revoke
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}

      {/* System */}
      <div className="card">
        <div className="card-body">
          <div className="flex items-center gap-3 mb-5">
            <div className="w-10 h-10 rounded-xl bg-info/10 flex items-center justify-center">
              <svg className="w-5 h-5 text-info" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
              </svg>
            </div>
            <div>
              <h2 className="heading-2 text-navy">System</h2>
              <p className="caption text-text-muted">Connection and school totals</p>
            </div>
          </div>

          <div className="space-y-4">
            {/* API Status */}
            <div className="flex items-center justify-between p-4 bg-surface-elevated rounded-xl">
              <div>
                <h3 className="body font-medium text-navy">Connection</h3>
                <p className="caption text-text-muted mt-0.5">
                  Whether GradePulse can reach its server
                </p>
              </div>
               <span className={`flex items-center gap-2 badge ${apiStatus === "online" ? "badge-success" : apiStatus === "offline" ? "badge-danger" : "badge-neutral"}`}>
                 <span className={`status-dot ${apiStatus === "online" ? "active" : ""}`} />
                 {apiStatus === "online" ? "Connected" : apiStatus === "offline" ? "Unavailable" : "Checking"}
               </span>
            </div>

            {/* Student Count */}
            {summary && (
              <div className="flex items-center justify-between p-4 bg-surface-elevated rounded-xl">
                <div>
                  <h3 className="body font-medium text-navy">Students</h3>
                  <p className="caption text-text-muted mt-0.5">
                    In your school
                  </p>
                </div>
                <span className="heading-2 text-navy">{summary.student_count}</span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Danger Zone */}
      <div className="card border-danger/20">
        <div className="card-body">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-xl bg-danger/10 flex items-center justify-center">
              <svg className="w-5 h-5 text-danger" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                <polyline points="16 17 21 12 16 7" />
                <line x1="21" y1="12" x2="9" y2="12" />
              </svg>
            </div>
            <div>
              <h2 className="heading-2 text-danger">Danger Zone</h2>
              <p className="caption text-text-muted">Account actions</p>
            </div>
          </div>

          <div className="flex items-center justify-between p-4 bg-danger/[0.03] rounded-xl border border-danger/10">
            <div>
              <h3 className="body font-medium text-navy">Sign Out</h3>
              <p className="caption text-text-muted mt-0.5">
                End your session and return to login
              </p>
            </div>
            <button
              onClick={logout}
              className="btn btn-danger"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                <polyline points="16 17 21 12 16 7" />
                <line x1="21" y1="12" x2="9" y2="12" />
              </svg>
              Sign Out
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
