"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { TriageResult } from "@/lib/types";
import { TIER_LABELS, SUBJECTS } from "@/lib/types";

const TIER_ICONS: Record<string, React.ReactNode> = {
  ahead: (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
      <path strokeLinecap="round" strokeLinejoin="round" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
    </svg>
  ),
  on_track: (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
    </svg>
  ),
  remediation: (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
    </svg>
  ),
};

export default function TriagePage() {
  const [subject, setSubject] = useState("MATH");
  const [result, setResult] = useState<TriageResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [history, setHistory] = useState<TriageResult[]>([]);

  const runTriage = async () => {
    setLoading(true);
    setError("");
    try {
      const data = await api.triage(subject);
      setResult(data);
      setHistory((prev) => [data, ...prev.slice(0, 4)]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Triage failed");
    } finally {
      setLoading(false);
    }
  };

  const totalStudents = result?.total_students ?? 0;

  return (
    <div className="page-shell">
      {/* Header */}
      <div className="page-header">
        <div className="page-header-left">
          <h1 className="heading-display text-navy">Student Triage</h1>
          <p className="body text-text-secondary">
            Classify students into performance tiers using the AI engine
          </p>
        </div>
      </div>

      {/* Controls */}
      <div className="card">
        <div className="card-body">
          <div className="flex flex-wrap items-end gap-4">
            <div className="input-group">
              <label className="input-label">Subject</label>
              <select
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                className="input select w-auto min-w-[160px]"
              >
                {SUBJECTS.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </div>
            <button
              onClick={runTriage}
              disabled={loading}
              className="btn btn-primary"
            >
              {loading ? (
                <>
                  <div className="spinner spinner-sm" style={{ borderTopColor: 'var(--color-navy)' }} />
                  Running...
                </>
              ) : (
                <>
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                  Run Triage
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Loading */}
      {loading && (
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-32 skeleton" />
          ))}
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="bg-danger-light border border-danger/20 text-danger px-4 py-3 rounded-lg text-sm flex items-center gap-2">
          <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
          {error}
        </div>
      )}

      {/* Results */}
      {result?.tiers && Object.keys(result.tiers).length > 0 && (
        <div className="space-y-6">
          {/* Summary Bar */}
          <div className="card">
            <div className="card-body">
              <div className="flex items-center justify-between mb-4">
                <h2 className="heading-2 text-navy">Classification Results</h2>
                <div className="flex items-center gap-3">
                  <span className="badge badge-neutral">{result.subject}</span>
                  <span className="badge badge-success">{totalStudents} classified</span>
                  <span className="badge badge-neutral">{result.scope}</span>
                </div>
              </div>

              {/* Visual Distribution Bar */}
              <div className="relative h-8 bg-surface-elevated rounded-lg overflow-hidden flex">
                {Object.entries(result.tiers).map(([key, tier]) => {
                  const meta = TIER_LABELS[key];
                  const pct = totalStudents > 0 ? (tier.count / totalStudents) * 100 : 0;
                  return pct > 0 ? (
                    <div
                      key={key}
                      className="h-full flex items-center justify-center text-xs font-bold text-white transition-all duration-500"
                      style={{
                        width: `${pct}%`,
                        background: meta?.color || "#94a3b8",
                      }}
                      title={`${meta?.label || key}: ${tier.count} students (${Math.round(pct)}%)`}
                    >
                      {pct > 15 && `${Math.round(pct)}%`}
                    </div>
                  ) : null;
                })}
              </div>

              {/* Legend */}
              <div className="flex flex-wrap gap-4 mt-3">
                {Object.entries(result.tiers).map(([key, tier]) => {
                  const meta = TIER_LABELS[key];
                  const pct = totalStudents > 0 ? Math.round((tier.count / totalStudents) * 100) : 0;
                  return (
                    <div key={key} className="flex items-center gap-2">
                      <div
                        className="w-3 h-3 rounded-sm"
                        style={{ background: meta?.color || "#94a3b8" }}
                      />
                      <span className="caption text-text-secondary">
                        {meta?.label || key}: {tier.count} ({pct}%)
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Tier Cards */}
          <div className="space-y-4">
            {Object.entries(result.tiers).map(([key, tier]) => {
              const meta = TIER_LABELS[key] || { label: key, color: "#94a3b8", badgeClass: "badge-neutral", description: "" };
              const pct = totalStudents > 0 ? Math.round((tier.count / totalStudents) * 100) : 0;

              return (
                <div key={key} className={`card tier-card tier-${key}`}>
                  <div className="card-body">
                    {/* Header */}
                    <div className="flex items-start justify-between mb-4">
                      <div className="flex items-center gap-3">
                        <div
                          className="w-10 h-10 rounded-xl flex items-center justify-center"
                          style={{ background: `${meta.color}15`, color: meta.color }}
                        >
                          {TIER_ICONS[key]}
                        </div>
                        <div>
                          <h3 className="heading-2 text-navy">{meta.label}</h3>
                          <p className="caption text-text-muted">{meta.description}</p>
                        </div>
                      </div>
                      <div className="text-right">
                        <span className="heading-1" style={{ color: meta.color }}>{tier.count}</span>
                        <span className="caption text-text-muted block">students ({pct}%)</span>
                      </div>
                    </div>

                    {/* Progress Bar */}
                    <div className="mb-4">
                      <div className="progress-bar">
                        <div
                          className="progress-bar-fill"
                          style={{ width: `${pct}%`, background: meta.color }}
                        />
                      </div>
                    </div>

                    {/* Recommended Difficulty */}
                    <div className="flex items-center gap-4 mb-4 p-3 bg-white/60 rounded-lg">
                      <div className="flex items-center gap-2">
                        <svg className="w-4 h-4 text-text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                        </svg>
                        <span className="caption text-text-secondary font-medium">Recommended Difficulty:</span>
                      </div>
                      <div className="flex gap-1">
                        {[1, 2, 3, 4, 5].map((d) => (
                          <div
                            key={d}
                            className="w-8 h-2 rounded-full transition-all"
                            style={{
                              background: d <= tier.recommended_difficulty ? meta.color : "#e2e8f0",
                            }}
                          />
                        ))}
                      </div>
                      <span className="text-sm font-mono font-semibold text-navy">
                        Level {tier.recommended_difficulty}
                      </span>
                    </div>

                    {/* Note */}
                    <div className="p-3 bg-white/60 rounded-lg mb-4">
                      <p className="body-sm text-text-secondary italic">{tier.note}</p>
                    </div>

                    {/* Students Grid */}
                    {tier.students.length === 0 ? (
                      <p className="caption text-text-muted text-center py-4">No students in this tier</p>
                    ) : (
                      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                        {tier.students.map((s) => (
                          <div
                            key={s.student_id}
                            className="flex items-center justify-between bg-white rounded-lg px-3 py-2.5 border border-border/50"
                          >
                            <div className="min-w-0">
                              <div className="text-sm font-medium text-navy truncate">{s.name}</div>
                              <div className="caption text-text-muted font-mono">{s.student_id}</div>
                            </div>
                            <div className="text-right ml-2 shrink-0">
                              <div className="text-sm font-mono font-semibold text-navy">
                                {Math.round(s.average_score * 100)}%
                              </div>
                              <div className="caption text-text-muted">
                                {s.attempts} try{s.attempts !== 1 ? "s" : ""}
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Empty State */}
      {!loading && !error && !result && (
        <div className="empty-state">
          <div className="empty-state-icon">
            <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
          </div>
          <h3 className="heading-3 text-navy mb-1">Ready to classify</h3>
          <p className="body-sm text-text-muted mb-4">
            Select a subject and click &quot;Run Triage&quot; to classify students into performance tiers
          </p>
          <button onClick={runTriage} className="btn btn-primary btn-sm">
            Run Triage
          </button>
        </div>
      )}

      {/* Previous Runs */}
      {history.length > 1 && (
        <div className="card">
          <div className="card-body">
            <h2 className="heading-2 text-navy mb-4">Previous Runs</h2>
            <div className="space-y-2">
              {history.slice(1).map((run, i) => (
                <div key={i} className="flex items-center justify-between p-3 bg-surface-elevated rounded-lg">
                  <div className="flex items-center gap-3">
                    <span className="badge badge-neutral">{run.subject}</span>
                    <span className="body-sm text-text-secondary">{run.total_students} students</span>
                  </div>
                  <div className="flex items-center gap-2">
                    {Object.entries(run.tiers).map(([key, tier]) => {
                      const meta = TIER_LABELS[key];
                      return (
                        <span key={key} className="text-xs font-mono" style={{ color: meta?.color }}>
                          {tier.count}
                        </span>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
