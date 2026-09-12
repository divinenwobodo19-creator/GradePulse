"use client";

import { useState, useEffect } from "react";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import type { BrainSummary } from "@/lib/types";

export default function SettingsPage() {
  const { user, logout } = useAuth();
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<{ type: string; message: string } | null>(null);
  const [summary, setSummary] = useState<BrainSummary | null>(null);

  const showToast = (type: string, message: string) => {
    setToast({ type, message });
    setTimeout(() => setToast(null), 3000);
  };

  useEffect(() => {
    api.summary().then(setSummary).catch(() => {});
  }, []);

  const handleSaveBrain = async () => {
    setSaving(true);
    try {
      await api.save();
      showToast("success", "Brain state saved successfully");
    } catch (err) {
      showToast("error", err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="page-shell max-w-3xl">
      {toast && (
        <div className={`toast toast-${toast.type}`}>
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
              <span className="badge badge-info">Teacher</span>
            </div>
          </div>
        </div>
      </div>

      {/* Algorithm Status */}
      {summary && (
        <div className="card">
          <div className="card-body">
            <div className="flex items-center gap-3 mb-5">
              <div className="w-10 h-10 rounded-xl bg-gold/10 flex items-center justify-center">
                <svg className="w-5 h-5 text-gold" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="3" />
                  <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
                </svg>
              </div>
              <div>
                <h2 className="heading-2 text-navy">Algorithm Engine</h2>
                <p className="caption text-text-muted">LinUCB + Neural Hybrid status</p>
              </div>
              <span className="badge badge-success ml-auto">Active</span>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="p-4 bg-surface-elevated rounded-xl">
                <div className="caption text-text-muted mb-1">Model Type</div>
                <div className="heading-2 text-navy capitalize">{summary.model_type}</div>
              </div>
              <div className="p-4 bg-surface-elevated rounded-xl">
                <div className="caption text-text-muted mb-1">Total Sessions</div>
                <div className="heading-2 text-navy">{summary.total_sessions.toLocaleString()}</div>
              </div>
              <div className="p-4 bg-surface-elevated rounded-xl">
                <div className="caption text-text-muted mb-1">Alpha (Exploration)</div>
                <div className="heading-2 text-navy font-mono">{summary.current_alpha?.toFixed(3) ?? "1.000"}</div>
              </div>
              <div className="p-4 bg-surface-elevated rounded-xl">
                <div className="caption text-text-muted mb-1">Gamma (Discount)</div>
                <div className="heading-2 text-navy font-mono">{summary.current_gamma?.toFixed(3) ?? "1.000"}</div>
              </div>
              <div className="p-4 bg-surface-elevated rounded-xl">
                <div className="caption text-text-muted mb-1">Cumulative Regret</div>
                <div className="heading-2 text-navy font-mono">{summary.cumulative_regret?.toFixed(3) ?? "0.000"}</div>
              </div>
              <div className="p-4 bg-surface-elevated rounded-xl">
                <div className="caption text-text-muted mb-1">Neural Score</div>
                <div className="heading-2 text-navy font-mono">{summary.last_neural_score?.toFixed(3) ?? "0.000"}</div>
              </div>
            </div>
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
              <p className="caption text-text-muted">Engine operations and health</p>
            </div>
          </div>

          <div className="space-y-4">
            {/* Save Brain State */}
            <div className="flex items-center justify-between p-4 bg-surface-elevated rounded-xl">
              <div>
                <h3 className="body font-medium text-navy">Save Brain State</h3>
                <p className="caption text-text-muted mt-0.5">
                  Persist the current model state to disk
                </p>
              </div>
              <button
                onClick={handleSaveBrain}
                disabled={saving}
                className="btn btn-secondary"
              >
                {saving ? (
                  <>
                    <div className="spinner spinner-sm" style={{ borderTopColor: 'white' }} />
                    Saving...
                  </>
                ) : (
                  <>
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                      <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z" />
                      <polyline points="17 21 17 13 7 13 7 21" />
                      <polyline points="7 3 7 8 15 8" />
                    </svg>
                    Save Now
                  </>
                )}
              </button>
            </div>

            {/* API Status */}
            <div className="flex items-center justify-between p-4 bg-surface-elevated rounded-xl">
              <div>
                <h3 className="body font-medium text-navy">API Status</h3>
                <p className="caption text-text-muted mt-0.5">
                  Backend connection health
                </p>
              </div>
              <span className="flex items-center gap-2 badge badge-success">
                <span className="status-dot active" />
                Connected
              </span>
            </div>

            {/* Content Count */}
            {summary && (
              <div className="flex items-center justify-between p-4 bg-surface-elevated rounded-xl">
                <div>
                  <h3 className="body font-medium text-navy">Content Library</h3>
                  <p className="caption text-text-muted mt-0.5">
                    Available learning materials
                  </p>
                </div>
                <span className="heading-2 text-navy">{summary.content_count}</span>
              </div>
            )}

            {/* Student Count */}
            {summary && (
              <div className="flex items-center justify-between p-4 bg-surface-elevated rounded-xl">
                <div>
                  <h3 className="body font-medium text-navy">Student Profiles</h3>
                  <p className="caption text-text-muted mt-0.5">
                    Active student records
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
