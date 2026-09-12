"use client";

import { useEffect, useState, useMemo } from "react";
import { api } from "@/lib/api";
import type { BrainSummary, TriageResult, Student } from "@/lib/types";
import { TIER_LABELS } from "@/lib/types";

function MetricCard({ accent, label, value, sub, icon }: {
  accent: string;
  label: string;
  value: string | number;
  sub: string;
  icon: React.ReactNode;
}) {
  return (
    <div className="metric-card" style={{ "--metric-accent": accent } as React.CSSProperties}>
      <div className="flex items-center justify-between mb-3">
        <span className="caption font-semibold text-text-secondary uppercase tracking-wider">{label}</span>
        <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: `${accent}15` }}>
          {icon}
        </div>
      </div>
      <div className="heading-1 text-navy">{value}</div>
      <div className="caption text-text-muted mt-1">{sub}</div>
    </div>
  );
}

export default function DashboardPage() {
  const [summary, setSummary] = useState<BrainSummary | null>(null);
  const [triage, setTriage] = useState<TriageResult | null>(null);
  const [students, setStudents] = useState<Student[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [s, t, st] = await Promise.all([
          api.summary(),
          api.triage("MATH").catch(() => null),
          api.getStudents().catch(() => []),
        ]);
        if (!cancelled) {
          setSummary(s);
          setTriage(t);
          setStudents(st);
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load dashboard");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, []);

  const tierCounts = useMemo(() => triage?.tiers
    ? Object.fromEntries(Object.entries(triage.tiers).map(([key, val]) => [key, val.count]))
    : {}, [triage]);

  const totalTriaged = triage?.total_students ?? 0;
  const riskCount = tierCounts["remediation"] ?? 0;
  const riskPct = totalTriaged > 0 ? Math.round((riskCount / totalTriaged) * 100) : 0;

  if (loading) {
    return (
      <div className="page-shell">
        <div className="h-8 w-48 rounded-lg skeleton" />
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => <div key={i} className="h-28 rounded-xl skeleton" />)}
        </div>
        <div className="h-40 rounded-xl skeleton" />
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => <div key={i} className="h-48 rounded-xl skeleton" />)}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-danger-light border border-danger/20 text-danger px-4 py-3 rounded-lg text-sm">
        {error}
      </div>
    );
  }

  return (
    <div className="page-shell">
      {/* Header */}
      <div className="page-header">
        <div className="page-header-left">
          <h1 className="heading-display text-navy">Dashboard</h1>
          <p className="body text-text-secondary">
            Overview of your school&apos;s performance intelligence
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="stat-pill">
            <span className="status-dot active" />
            Engine Active
          </span>
        </div>
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          accent="var(--color-gold)"
          label="Students"
          value={summary?.student_count ?? 0}
          sub="Active profiles"
          icon={<svg className="w-4 h-4 text-gold" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /></svg>}
        />
        <MetricCard
          accent="var(--color-info)"
          label="Sessions"
          value={(summary?.total_sessions ?? 0).toLocaleString()}
          sub="Learning interactions"
          icon={<svg className="w-4 h-4 text-info" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><path d="M12 20V10" /><path d="M18 20V4" /><path d="M6 20v-4" /></svg>}
        />
        <MetricCard
          accent="var(--color-navy)"
          label="Model"
          value={summary?.model_type ?? "N/A"}
          sub="LinUCB + Neural"
          icon={<svg className="w-4 h-4 text-navy" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="3" /><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" /></svg>}
        />
        <MetricCard
          accent="var(--color-danger)"
          label="At Risk"
          value={riskCount}
          sub={`${riskPct}% of triaged`}
          icon={<svg className="w-4 h-4 text-danger" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" /><line x1="12" y1="9" x2="12" y2="13" /><line x1="12" y1="17" x2="12.01" y2="17" /></svg>}
        />
      </div>

      {/* Algorithm Health Bar */}
      <div className="card">
        <div className="card-body">
          <div className="flex items-center justify-between mb-4">
            <h2 className="heading-2 text-navy">Algorithm Health</h2>
            <span className="badge badge-success">Active</span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-6">
            <div>
              <div className="caption text-text-muted mb-1">Alpha (Exploration)</div>
              <div className="flex items-center gap-2">
                <div className="flex-1 progress-bar">
                  <div
                    className="progress-bar-fill"
                    style={{ width: `${((summary?.current_alpha ?? 1) / 2) * 100}%` }}
                  />
                </div>
                <span className="text-sm font-mono font-semibold text-navy">
                  {summary?.current_alpha?.toFixed(2) ?? "1.00"}
                </span>
              </div>
            </div>
            <div>
              <div className="caption text-text-muted mb-1">Gamma (Discount)</div>
              <div className="flex items-center gap-2">
                <div className="flex-1 progress-bar">
                  <div
                    className="progress-bar-fill"
                    style={{ width: `${((summary?.current_gamma ?? 1) / 2) * 100}%` }}
                  />
                </div>
                <span className="text-sm font-mono font-semibold text-navy">
                  {summary?.current_gamma?.toFixed(2) ?? "1.00"}
                </span>
              </div>
            </div>
            <div>
              <div className="caption text-text-muted mb-1">Cumulative Regret</div>
              <div className="flex items-center gap-2">
                <div className="flex-1 progress-bar">
                  <div
                    className={`progress-bar-fill ${
                      (summary?.cumulative_regret ?? 0) > 5 ? "danger" : (summary?.cumulative_regret ?? 0) > 2 ? "warning" : "success"
                    }`}
                    style={{ width: `${Math.min(100, ((summary?.cumulative_regret ?? 0) / 10) * 100)}%` }}
                  />
                </div>
                <span className="text-sm font-mono font-semibold text-navy">
                  {summary?.cumulative_regret?.toFixed(2) ?? "0.00"}
                </span>
              </div>
            </div>
            <div>
              <div className="caption text-text-muted mb-1">Neural Score</div>
              <div className="flex items-center gap-2">
                <div className="flex-1 progress-bar">
                  <div
                    className="progress-bar-fill success"
                    style={{ width: `${((summary?.last_neural_score ?? 0) + 1) / 2 * 100}%` }}
                  />
                </div>
                <span className="text-sm font-mono font-semibold text-navy">
                  {summary?.last_neural_score?.toFixed(2) ?? "0.00"}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Triage Breakdown */}
      {triage?.tiers && Object.keys(triage.tiers).length > 0 && (
        <div className="card">
          <div className="card-body">
            <div className="flex items-center justify-between mb-5">
              <div>
                <h2 className="heading-2 text-navy">Performance Triage</h2>
                <p className="caption text-text-muted mt-0.5">
                  {triage.subject} &middot; {totalTriaged} students classified
                </p>
              </div>
              <span className="badge badge-neutral">{triage.scope}</span>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              {Object.entries(triage.tiers).map(([key, tier]) => {
                const meta = TIER_LABELS[key] || { label: key, color: "#94a3b8", badgeClass: "badge-neutral", description: "" };
                const pct = totalTriaged > 0 ? Math.round((tier.count / totalTriaged) * 100) : 0;

                return (
                  <div key={key} className={`tier-card tier-${key}`}>
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-2">
                        <h3 className="heading-3 text-navy">{meta.label}</h3>
                      </div>
                      <span className={`badge ${meta.badgeClass}`}>{tier.count}</span>
                    </div>

                    {/* Progress Bar */}
                    <div className="mb-3">
                      <div className="progress-bar">
                        <div
                          className="progress-bar-fill"
                          style={{
                            width: `${pct}%`,
                            background: meta.color,
                          }}
                        />
                      </div>
                      <div className="flex justify-between mt-1">
                        <span className="caption text-text-muted">{pct}% of total</span>
                        <span className="caption text-text-muted">
                          Difficulty: {tier.recommended_difficulty}
                        </span>
                      </div>
                    </div>

                    {/* Students */}
                    {tier.students.length > 0 ? (
                      <div className="space-y-1.5">
                        {tier.students.slice(0, 4).map((s) => (
                          <div key={s.student_id} className="flex items-center justify-between bg-white/60 rounded-lg px-3 py-2">
                            <div className="min-w-0">
                              <div className="text-sm font-medium text-navy truncate">{s.name}</div>
                              <div className="caption text-text-muted">{s.attempts} attempt{s.attempts !== 1 ? "s" : ""}</div>
                            </div>
                            <span className="text-sm font-mono font-semibold text-navy ml-2">
                              {Math.round(s.average_score * 100)}%
                            </span>
                          </div>
                        ))}
                        {tier.students.length > 4 && (
                          <div className="text-center caption text-text-muted py-1">
                            +{tier.students.length - 4} more students
                          </div>
                        )}
                      </div>
                    ) : (
                      <p className="caption text-text-muted">No students in this tier</p>
                    )}

                    {/* Recommendation */}
                    <div className="mt-3 pt-3 border-t border-black/5">
                      <p className="caption text-text-muted italic">{tier.note}</p>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* Student Table */}
      {students.length > 0 && (
        <div className="table-wrapper">
          <div className="px-5 py-4 border-b border-border">
            <h2 className="heading-2 text-navy">All Students</h2>
          </div>
          <table className="data-table">
            <thead>
              <tr>
                <th>Student</th>
                <th>ID</th>
                <th className="text-right">Score</th>
                <th>Topic</th>
              </tr>
            </thead>
            <tbody>
              {students.map((s) => (
                <tr key={s.student_id}>
                  <td>
                    <div className="flex items-center gap-3">
                      <div className="w-7 h-7 rounded-full bg-navy/5 flex items-center justify-center text-navy text-xs font-semibold">
                        {s.name.charAt(0)}
                      </div>
                      <span className="font-medium text-navy">{s.name}</span>
                    </div>
                  </td>
                  <td className="font-mono text-xs text-text-muted">{s.student_id}</td>
                  <td className="text-right">
                    <span className="badge badge-info font-mono">
                      {Math.round(s.performance_score * 100)}%
                    </span>
                  </td>
                  <td className="text-text-secondary">{s.current_topic}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
