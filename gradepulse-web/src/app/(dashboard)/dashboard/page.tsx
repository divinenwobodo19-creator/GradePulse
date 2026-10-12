"use client";

import { useEffect, useState, useMemo } from "react";
import { api } from "@/lib/api";
import { overallPercentLabel } from "@/lib/scores";
import { useAuth } from "@/lib/auth";
import type { BrainSummary, SchoolClass, TriageResult, Student } from "@/lib/types";
import { SUBJECTS, TIER_LABELS } from "@/lib/types";

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
  const { user, loading: authLoading } = useAuth();
  const [summary, setSummary] = useState<BrainSummary | null>(null);
  const [classes, setClasses] = useState<SchoolClass[]>([]);
  const [subject, setSubject] = useState<string>(SUBJECTS[0]);
  const [classId, setClassId] = useState("");
  const [triage, setTriage] = useState<TriageResult | null>(null);
  const [students, setStudents] = useState<Student[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // School-wide figures: loaded once.
  useEffect(() => {
    if (authLoading || !user) return;

    const controller = new AbortController();
    api.summary(controller.signal).then(setSummary).catch(() => undefined);
    if (user.school_id) {
      api.getClasses(user.school_id, controller.signal).then(setClasses).catch(() => undefined);
    }
    return () => controller.abort();
  }, [authLoading, user]);

  // The report itself follows the chosen subject and class.
  useEffect(() => {
    if (authLoading || !user) return;

    let cancelled = false;
    const controller = new AbortController();
    async function load() {
      try {
        const [t, st] = await Promise.all([
          api.triage(subject, controller.signal, classId || undefined),
          api.getStudents(undefined, classId || undefined, controller.signal),
        ]);
        if (!cancelled) {
          setTriage(t);
          setStudents(st);
          setError("");
        }
      } catch (err) {
        if (!cancelled && !(err instanceof Error && err.name === "AbortError")) {
          setError(err instanceof Error ? err.message : "Failed to load dashboard");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void load();
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [authLoading, user, subject, classId]);

  const tierCounts = useMemo(() => triage?.tiers
    ? Object.fromEntries(Object.entries(triage.tiers).map(([key, val]) => [key, val.count]))
    : {}, [triage]);

  const totalTriaged = triage?.total_students ?? 0;
  const riskCount = tierCounts["remediation"] ?? 0;
  const aheadCount = tierCounts["ahead"] ?? 0;
  const pctOfAssessed = (count: number) => (totalTriaged > 0 ? Math.round((count / totalTriaged) * 100) : 0);

  if (authLoading || loading) {
    return (
      <div role="status" aria-live="polite" className="page-shell">
        <div className="h-8 w-48 rounded-lg skeleton" />
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => <div key={i} className="h-28 rounded-xl skeleton" />)}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => <div key={i} className="h-48 rounded-xl skeleton" />)}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div role="alert" aria-live="assertive" className="bg-danger-light border border-danger/20 text-danger px-4 py-3 rounded-lg text-sm">
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
            Who needs help, who is on track and who is ahead{user?.school_name ? ` at ${user.school_name}` : ""}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <select
            aria-label="Subject"
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            className="input select w-auto min-w-[140px]"
          >
            {SUBJECTS.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
          <select
            aria-label="Class"
            value={classId}
            onChange={(e) => setClassId(e.target.value)}
            className="input select w-auto min-w-[140px]"
          >
            <option value="">All classes</option>
            {classes.map((c) => (
              <option key={c.class_id} value={c.class_id}>{c.label}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          accent="var(--color-gold)"
          label="Students"
          value={summary?.student_count ?? students.length}
          sub="In your school"
          icon={<svg className="w-4 h-4 text-gold" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /></svg>}
        />
        <MetricCard
          accent="var(--color-info)"
          label="Assessed"
          value={totalTriaged}
          sub={`Have a ${subject} score`}
          icon={<svg className="w-4 h-4 text-info" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><path d="M12 20V10" /><path d="M18 20V4" /><path d="M6 20v-4" /></svg>}
        />
        <MetricCard
          accent="var(--color-danger)"
          label="Need Help"
          value={riskCount}
          sub={`${pctOfAssessed(riskCount)}% of assessed, below 40%`}
          icon={<svg className="w-4 h-4 text-danger" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><path d="M12 9v4" /><path d="M12 17h.01" /><circle cx="12" cy="12" r="10" /></svg>}
        />
        <MetricCard
          accent="var(--color-success)"
          label="Ahead"
          value={aheadCount}
          sub={`${pctOfAssessed(aheadCount)}% of assessed, 75% and above`}
          icon={<svg className="w-4 h-4 text-success" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><path d="M13 7h8v8" /><path d="M21 7l-8 8-4-4-6 6" /></svg>}
        />
      </div>

      {/* Triage Breakdown */}
      {triage && totalTriaged === 0 && (
        <div className="card">
          <div className="card-body">
            <h2 className="heading-2 text-navy">Performance Triage</h2>
            <p className="body-sm text-text-muted mt-1">
              No {subject} scores recorded yet{classId ? " for this class" : ""}. Enter scores to see who needs help.
            </p>
          </div>
        </div>
      )}

      {triage?.tiers && totalTriaged > 0 && (
        <div className="card">
          <div className="card-body">
            <div className="flex items-center justify-between mb-5">
              <div>
                <h2 className="heading-2 text-navy">Performance Triage</h2>
                <p className="caption text-text-muted mt-0.5">
                  {triage.subject} &middot; {totalTriaged} students classified
                </p>
              </div>
              <span className="badge badge-neutral">Students with a {subject} score</span>
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
                              {Math.round((s.average_score ?? s.predicted_score ?? 0) * 100)}%
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
            <h2 className="heading-2 text-navy">{classId ? "Students in this class" : "All Students"}</h2>
          </div>
          <table className="data-table">
            <thead>
              <tr>
                <th>Student</th>
                <th>ID</th>
                <th className="text-right">Score</th>
                <th>Subject</th>
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
                      {overallPercentLabel(s)}
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
