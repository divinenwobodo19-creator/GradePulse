"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Student } from "@/lib/types";
import { SUBJECTS } from "@/lib/types";
import { scoreToGrade } from "@/lib/types";
import { percentToScore, scoreToInputValue, scoreToPercent, validateScorePercent } from "@/lib/scores";

export default function ScoresPage() {
  const { user, loading: authLoading } = useAuth();
  const [students, setStudents] = useState<Student[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [toast, setToast] = useState<{ type: string; message: string } | null>(null);
  const [subject, setSubject] = useState("MATH");
  const [scores, setScores] = useState<Record<string, string>>({});
  const [modified, setModified] = useState<Set<string>>(new Set());
  const [submitting, setSubmitting] = useState(false);
  const [invalid, setInvalid] = useState<Set<string>>(new Set());
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
    if (modified.size === 0) return;
    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [modified.size]);

  const applyStudents = (data: Student[]) => {
    setStudents(data);
    const initial: Record<string, string> = {};
    data.forEach((s) => {
      initial[s.student_id] = scoreToInputValue(s.performance_score);
    });
    setScores(initial);
  };

  useEffect(() => {
    if (authLoading || !user) return;

    let cancelled = false;
    const controller = new AbortController();
    async function load() {
      try {
        const data = await api.getStudents(undefined, undefined, controller.signal);
        if (cancelled) return;
        applyStudents(data);
      } catch (err) {
        if (!cancelled && !(err instanceof Error && err.name === "AbortError")) {
          setError(err instanceof Error ? err.message : "Failed to load students");
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
  }, [authLoading, user]);

  const handleScoreChange = (studentId: string, value: string) => {
    setScores((prev) => ({ ...prev, [studentId]: value }));
    setModified((prev) => {
      const next = new Set(prev);
      next.add(studentId);
      return next;
    });
    setInvalid((prev) => {
      const next = new Set(prev);
      if (validateScorePercent(value).valid) {
        next.delete(studentId);
      } else {
        next.add(studentId);
      }
      return next;
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      const entries = Object.entries(scores)
        .filter(([id]) => modified.has(id))
        .map(([studentId, score]) => ({
          student_id: studentId,
          subject,
          score: percentToScore(score),
        }));

      if (entries.length === 0) {
        showToast("error", "No scores changed. Modify at least one score.");
        return;
      }

      if (invalid.size > 0) {
        showToast("error", "Fix the highlighted scores. Each value must be between 0 and 100.");
        return;
      }

      await api.bulkUpdate(entries);
      showToast("success", `Updated ${entries.length} student${entries.length !== 1 ? "s" : ""}`);
      setModified(new Set());
      setInvalid(new Set());
      applyStudents(await api.getStudents(undefined, undefined));
    } catch (err) {
      showToast("error", err instanceof Error ? err.message : "Failed to update scores");
    } finally {
      setSubmitting(false);
    }
  };

  const modifiedCount = modified.size;

  if (authLoading || loading) {
    return (
      <div role="status" aria-live="polite" className="space-y-6">
        <div className="h-8 w-48 skeleton" />
        <div className="h-10 w-full skeleton" />
        <div className="h-64 skeleton" />
      </div>
    );
  }

  return (
    <div className="page-shell">
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
          <h1 className="heading-display text-navy">Enter Scores</h1>
          <p className="body text-text-secondary">
            Submit weekly test scores for your students
          </p>
        </div>
      </div>

      {error && (
        <div role="alert" aria-live="assertive" className="bg-danger-light border border-danger/20 text-danger px-4 py-3 rounded-lg text-sm">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Subject Selector */}
        <div className="card">
          <div className="card-body">
            <div className="flex flex-wrap items-center gap-4">
              <div className="input-group">
                 <label className="input-label" htmlFor="score-subject">Subject</label>
                 <select
                   id="score-subject"
                   value={subject}
                  onChange={(e) => setSubject(e.target.value)}
                  className="input select w-auto min-w-[160px]"
                >
                  {SUBJECTS.map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
              </div>

              {modifiedCount > 0 && (
                <div className="flex items-center gap-2 ml-auto">
                  <span className="badge badge-warning">{modifiedCount} changed</span>
                  <button
                    type="button"
                    onClick={() => {
                      setModified(new Set());
                      // Reset scores to original
                      const initial: Record<string, string> = {};
                      students.forEach((s) => {
                        initial[s.student_id] = String(Math.round(s.performance_score * 100));
                      });
                       applyStudents(students);
                       setInvalid(new Set());
                     }}
                     className="btn btn-ghost btn-sm"
                  >
                    Reset
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Score Table */}
        <div className="table-wrapper">
          {students.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">
                <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
                  <path d="M12 20V10" />
                  <path d="M18 20V4" />
                  <path d="M6 20v-4" />
                </svg>
              </div>
              <h3 className="heading-3 text-navy mb-1">No students found</h3>
              <p className="body-sm text-text-muted">
                Go to <strong>Students</strong> to add students first.
              </p>
            </div>
          ) : (
            <>
              <div className="px-5 py-3 border-b border-border flex items-center justify-between">
                <span className="body-sm text-text-secondary">
                  {students.length} student{students.length !== 1 ? "s" : ""} &middot; {subject}
                </span>
                {modifiedCount > 0 && (
                  <button
                    type="submit"
                    disabled={submitting}
                    aria-busy={submitting}
                    className="btn btn-primary btn-sm"
                  >
                    {submitting ? (
                      <>
                        <div className="spinner spinner-sm" style={{ borderTopColor: 'var(--color-navy)' }} />
                        Saving...
                      </>
                    ) : (
                      <>
                        Save {modifiedCount} Score{modifiedCount !== 1 ? "s" : ""}
                      </>
                    )}
                  </button>
                )}
              </div>
              <table className="data-table">
                <caption className="sr-only">
                  Weekly scores for {subject}, expressed as percentages
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Student</th>
                    <th scope="col">ID</th>
                    <th scope="col">Grade</th>
                    <th scope="col" className="text-right">Current (%)</th>
                    <th scope="col" className="text-right w-40">New Score (%)</th>
                  </tr>
                </thead>
                <tbody>
                  {students.map((s) => {
                    const currentPct = scoreToPercent(s.performance_score);
                    const grade = scoreToGrade(currentPct);
                    const newVal = scores[s.student_id] ?? "";
                    const isModified = modified.has(s.student_id);

                    return (
                      <tr key={s.student_id} className={isModified ? "bg-gold/[0.03]" : ""}>
                        <td>
                          <div className="flex items-center gap-3">
                            <div className="w-7 h-7 rounded-full bg-navy/5 flex items-center justify-center text-navy text-xs font-semibold shrink-0">
                              {s.name.charAt(0)}
                            </div>
                            <span className="font-medium text-navy">{s.name}</span>
                          </div>
                        </td>
                        <td className="font-mono text-xs text-text-muted">{s.student_id}</td>
                        <td>
                          <span className={`badge ${isModified ? "badge-warning" : "badge-info"} font-mono`}>
                            {grade}
                          </span>
                        </td>
                        <td className="text-right font-mono text-sm text-text-secondary">{currentPct}%</td>
                        <td className="text-right">
                          <input
                            id={`score-${s.student_id}`}
                            name={`score-${s.student_id}`}
                            type="number"
                            min="0"
                            max="100"
                            step="1"
                            inputMode="numeric"
                            value={newVal}
                            onChange={(e) => handleScoreChange(s.student_id, e.target.value)}
                            aria-label={`New score for ${s.name} in percent`}
                            aria-invalid={invalid.has(s.student_id)}
                            aria-describedby={
                              invalid.has(s.student_id) ? `score-error-${s.student_id}` : undefined
                            }
                            className={`input w-24 text-right font-mono ${
                              invalid.has(s.student_id) ? "border-danger focus:border-danger" : ""
                            }`}
                            placeholder="%"
                          />
                          {invalid.has(s.student_id) && (
                            <p
                              id={`score-error-${s.student_id}`}
                              className="text-xs text-danger mt-1 text-right"
                            >
                              Enter 0-100
                            </p>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </>
          )}
        </div>

        {/* Bottom Submit */}
        {students.length > 0 && modifiedCount > 0 && (
          <div className="flex justify-end">
            <button
              type="submit"
              disabled={submitting}
              aria-busy={submitting}
              className="btn btn-primary btn-lg"
            >
              {submitting ? (
                <>
                  <div className="spinner spinner-sm" style={{ borderTopColor: 'var(--color-navy)' }} />
                  Saving {modifiedCount} scores...
                </>
              ) : (
                <>
                  Save {modifiedCount} Score{modifiedCount !== 1 ? "s" : ""}
                </>
              )}
            </button>
          </div>
        )}
      </form>
    </div>
  );
}
