"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { SchoolClass, TriageResult } from "@/lib/types";
import { TIER_LABELS } from "@/lib/types";
import { activeSubject, useSubjects } from "@/lib/subjects";
import { currentScore, movementLabel, shortDate } from "@/lib/triage";

// Needs help first: it is the list a teacher acts on.
const TIER_ORDER = ["remediation", "on_track", "ahead"];

export default function TriagePage() {
  const { user, loading: authLoading } = useAuth();
  const subjects = useSubjects();
  const [pickedSubject, setSubject] = useState("");
  const subject = activeSubject(pickedSubject, subjects);
  const [classes, setClasses] = useState<SchoolClass[]>([]);
  const [classId, setClassId] = useState("");
  const [result, setResult] = useState<TriageResult | null>(null);
  const [error, setError] = useState("");
  // Which subject and class the shown list (or error) is for: loading until it matches.
  const wanted = `${subject}|${classId}`;
  const [loadedFor, setLoadedFor] = useState("");
  const loading = loadedFor !== wanted;

  useEffect(() => {
    if (authLoading || !user?.school_id) return;
    const controller = new AbortController();
    api.getClasses(user.school_id, controller.signal).then(setClasses).catch(() => undefined);
    return () => controller.abort();
  }, [authLoading, user]);

  useEffect(() => {
    if (authLoading || !user) return;
    let cancelled = false;
    const controller = new AbortController();
    api
      .triage(subject, controller.signal, classId || undefined)
      .then((data) => {
        if (!cancelled) {
          setResult(data);
          setError("");
          setLoadedFor(`${subject}|${classId}`);
        }
      })
      .catch((err) => {
        if (!cancelled && !(err instanceof Error && err.name === "AbortError")) {
          setError(err instanceof Error ? err.message : "Could not load the list");
          setLoadedFor(`${subject}|${classId}`);
        }
      });
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [authLoading, user, subject, classId]);

  const total = result?.total_students ?? 0;
  const tiers = result ? TIER_ORDER.filter((k) => result.tiers[k]).map((k) => [k, result.tiers[k]] as const) : [];

  return (
    <div className="page-shell">
      <div className="page-header">
        <div className="page-header-left">
          <h1 className="heading-display text-navy">Student Triage</h1>
          <p className="body text-text-secondary">
            Every assessed student, grouped on WAEC bands by their last few tests, with the change since last week
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

      {loading && (
        <div role="status" aria-live="polite" className="space-y-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-32 skeleton" />
          ))}
        </div>
      )}

      {!loading && error && (
        <div role="alert" aria-live="assertive" className="bg-danger-light border border-danger/20 text-danger px-4 py-3 rounded-lg text-sm">
          {error}
        </div>
      )}

      {!loading && !error && result && total === 0 && (
        <div className="empty-state">
          <h3 className="heading-3 text-navy mb-1">No {subject} scores yet</h3>
          <p className="body-sm text-text-muted">
            Enter this week&apos;s {subject} test on the Scores page{classId ? " for this class" : ""}, and the list will appear here.
          </p>
        </div>
      )}

      {!loading && !error && result && total > 0 && (
        <div className="space-y-6">
          <div className="card">
            <div className="card-body">
              <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
                <div>
                  <h2 className="heading-2 text-navy">
                    {result.subject}
                    {result.as_of ? `, week ending ${shortDate(result.as_of)}` : ""}
                  </h2>
                  <p className="caption text-text-muted mt-0.5">
                    {total} students assessed
                    {result.tested_this_week !== undefined ? `, ${result.tested_this_week} tested this week` : ""}
                    {` · based on each student's last ${result.recent_tests ?? 3} tests`}
                  </p>
                </div>
              </div>

              <div className="relative h-8 bg-surface-elevated rounded-lg overflow-hidden flex">
                {tiers.map(([key, tier]) => {
                  const meta = TIER_LABELS[key];
                  const pct = (tier.count / total) * 100;
                  return pct > 0 ? (
                    <div
                      key={key}
                      className="h-full flex items-center justify-center text-xs font-bold text-white"
                      style={{ width: `${pct}%`, background: meta?.color || "#94a3b8" }}
                      title={`${meta?.label || key}: ${tier.count} students (${Math.round(pct)}%)`}
                    >
                      {pct > 15 && `${Math.round(pct)}%`}
                    </div>
                  ) : null;
                })}
              </div>
              <div className="flex flex-wrap gap-4 mt-3">
                {tiers.map(([key, tier]) => {
                  const meta = TIER_LABELS[key];
                  return (
                    <div key={key} className="flex items-center gap-2">
                      <div className="w-3 h-3 rounded-sm" style={{ background: meta?.color || "#94a3b8" }} />
                      <span className="caption text-text-secondary">
                        {meta?.label || key}: {tier.count} ({Math.round((tier.count / total) * 100)}%)
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {tiers.map(([key, tier]) => {
            const meta = TIER_LABELS[key] || { label: key, color: "#94a3b8", badgeClass: "badge-neutral", description: "" };
            return (
              <div key={key} className={`card tier-card tier-${key}`}>
                <div className="card-body">
                  <div className="flex items-start justify-between mb-4">
                    <div>
                      <h3 className="heading-2 text-navy">{meta.label}</h3>
                      <p className="caption text-text-muted">{meta.description}</p>
                    </div>
                    <span className="heading-1" style={{ color: meta.color }}>{tier.count}</span>
                  </div>

                  {tier.students.length === 0 ? (
                    <p className="caption text-text-muted text-center py-4">No students in this group</p>
                  ) : (
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                      {tier.students.map((s) => {
                        const moved = movementLabel(s);
                        return (
                          <div
                            key={s.student_id}
                            className="flex items-center justify-between bg-white rounded-lg px-3 py-2.5 border border-border/50"
                          >
                            <div className="min-w-0">
                              <div className="text-sm font-medium text-navy truncate">{s.name}</div>
                              <div className={`caption ${moved?.tone ?? "text-text-muted"}`}>
                                {moved?.text ?? s.student_id}
                                {s.tested_this_week === false ? " · not tested this week" : ""}
                              </div>
                            </div>
                            <div className="text-right ml-2 shrink-0">
                              <div className="text-sm font-mono font-semibold text-navy">
                                {Math.round(currentScore(s) * 100)}%
                              </div>
                              <div className="caption text-text-muted">
                                {s.attempts} test{s.attempts !== 1 ? "s" : ""}
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
