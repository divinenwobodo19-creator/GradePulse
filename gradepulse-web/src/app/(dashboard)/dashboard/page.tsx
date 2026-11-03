"use client";

import { useEffect, useState, useMemo } from "react";
import { api } from "@/lib/api";
import { overallPercentLabel } from "@/lib/scores";
import { useAuth } from "@/lib/auth";
import type { BrainSummary, SchoolClass, TriageResult, Student } from "@/lib/types";
import { TIER_LABELS, getStudentClassId } from "@/lib/types";
import { activeSubject, useSubjects } from "@/lib/subjects";
import { currentScore, hasLastWeek, movementLabel, pointsLabel, shortDate } from "@/lib/triage";

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
  const subjects = useSubjects();
  const [pickedSubject, setSubject] = useState("");
  const subject = activeSubject(pickedSubject, subjects);
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
  const compared = triage ? hasLastWeek(triage) : false;
  const movedIn = triage?.changes?.moved_into_help ?? [];
  const movedOut = triage?.changes?.left_help ?? [];
  const watch = triage?.changes?.watch ?? [];

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
            {user?.role === "admin"
              ? `Who needs help, who is on track and who is ahead${user?.school_name ? ` at ${user.school_name}` : ""}`
              : classes.length > 0
                ? `Your classes: ${classes.map((c) => c.label).join(", ")}`
                : "You have not been given a class yet. Ask your school admin to add you in Settings → People."}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <select
            aria-label="Subject"
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            className="input select w-auto min-w-[140px]"
          >
            {subjects.map((s) => (
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
          sub={user?.role === "admin" ? "In your school" : "In your classes"}
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
          sub={compared
            ? `${movedIn.length} new this week, ${movedOut.length} moved out`
            : `${pctOfAssessed(riskCount)}% of assessed, below 40%`}
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
            <h2 className="heading-2 text-navy">Who needs help this week</h2>
            <p className="body-sm text-text-muted mt-1">
              No {subject} scores recorded yet{classId ? " for this class" : ""}. Enter this week&apos;s test on the Scores page to see who needs help.
            </p>
          </div>
        </div>
      )}

      {triage?.tiers && totalTriaged > 0 && (
        <div className="card">
          <div className="card-body">
            <div className="mb-5">
              <h2 className="heading-2 text-navy">Who needs help this week</h2>
              <p className="caption text-text-muted mt-0.5">
                {triage.subject}
                {triage.as_of ? ` \u00b7 week ending ${shortDate(triage.as_of)}` : ""}
                {` \u00b7 each student's last ${triage.recent_tests ?? 3} tests`}
                {triage.tested_this_week !== undefined
                  ? ` \u00b7 ${triage.tested_this_week} of ${totalTriaged} tested this week`
                  : ""}
              </p>
            </div>

            {/* Since last week */}
            {compared ? (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-5">
                {[
                  { title: "New in needs help", list: movedIn, tone: "text-danger", empty: "Nobody new this week." },
                  { title: "Moved out of needs help", list: movedOut, tone: "text-success", empty: "Nobody moved out this week." },
                  { title: "Watch: latest test below 40%", list: watch, tone: "text-danger", empty: "Nobody else scored below 40%.", latest: true },
                ].map((group) => (
                  <div key={group.title} className="rounded-lg border border-border p-3">
                    <div className="flex items-center justify-between mb-2">
                      <h3 className="body-sm font-semibold text-navy">{group.title}</h3>
                      <span className={`text-sm font-mono font-semibold ${group.tone}`}>{group.list.length}</span>
                    </div>
                    {group.list.length === 0 ? (
                      <p className="caption text-text-muted">{group.empty}</p>
                    ) : (
                      <ul className="space-y-1">
                        {group.list.slice(0, 5).map((c) => (
                          <li key={c.student_id} className="flex items-center justify-between gap-2 caption">
                            <span className="text-navy truncate">{c.name}</span>
                            <span className="font-mono text-text-secondary shrink-0">
                              {"latest" in group
                                ? `latest ${Math.round((c.latest_score ?? 0) * 100)}%, average ${Math.round(c.current_score * 100)}%`
                                : <>
                                    {c.previous_score != null ? `${Math.round(c.previous_score * 100)}% to ` : ""}
                                    {Math.round(c.current_score * 100)}%
                                    <span className={`ml-1 ${group.tone}`}>({pointsLabel(c.change)})</span>
                                  </>}
                            </span>
                          </li>
                        ))}
                        {group.list.length > 5 && (
                          <li className="caption text-text-muted">and {group.list.length - 5} more</li>
                        )}
                      </ul>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="caption text-text-muted mb-5">
                Changes since last week will show here once a second week of {subject} tests is entered.
              </p>
            )}

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              {Object.entries(triage.tiers).map(([key, tier]) => {
                const meta = TIER_LABELS[key] || { label: key, color: "#94a3b8", badgeClass: "badge-neutral", description: "" };
                const pct = totalTriaged > 0 ? Math.round((tier.count / totalTriaged) * 100) : 0;

                return (
                  <div key={key} className={`tier-card tier-${key}`}>
                    <div className="flex items-center justify-between mb-3">
                      <h3 className="heading-3 text-navy">{meta.label}</h3>
                      <span className={`badge ${meta.badgeClass}`}>{tier.count}</span>
                    </div>

                    <div className="mb-3">
                      <div className="progress-bar">
                        <div className="progress-bar-fill" style={{ width: `${pct}%`, background: meta.color }} />
                      </div>
                      <div className="caption text-text-muted mt-1">{pct}% of assessed &middot; {meta.description}</div>
                    </div>

                    {tier.students.length > 0 ? (
                      <div className="space-y-1.5">
                        {tier.students.slice(0, 5).map((s) => {
                          const moved = movementLabel(s);
                          return (
                            <div key={s.student_id} className="flex items-center justify-between bg-white/60 rounded-lg px-3 py-2">
                              <div className="min-w-0">
                                <div className="text-sm font-medium text-navy truncate">{s.name}</div>
                                <div className={`caption ${moved?.tone ?? "text-text-muted"}`}>
                                  {moved?.text ?? `${s.attempts} test${s.attempts !== 1 ? "s" : ""}`}
                                </div>
                              </div>
                              <span className="text-sm font-mono font-semibold text-navy ml-2">
                                {Math.round(currentScore(s) * 100)}%
                              </span>
                            </div>
                          );
                        })}
                        {tier.students.length > 5 && (
                          <div className="text-center caption text-text-muted py-1">
                            +{tier.students.length - 5} more on the Triage page
                          </div>
                        )}
                      </div>
                    ) : (
                      <p className="caption text-text-muted">No students in this group</p>
                    )}
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
                <th>Class</th>
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
                  <td className="text-text-secondary">
                    {classes.find((c) => c.class_id === getStudentClassId(s))?.label ?? "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
