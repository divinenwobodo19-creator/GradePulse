"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Student, Content } from "@/lib/types";
import { scoreToGrade, scoreToPercentage, GRADE_COLORS, SUBJECTS } from "@/lib/types";

interface Recommendation {
  content_id: string;
  title: string;
  topic: string;
  difficulty: number;
  content_type: string;
  times_recommended: number;
  times_rewarded: number;
  avg_reward: number;
}

export default function ProgressPage() {
  const [students, setStudents] = useState<Student[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [loading, setLoading] = useState(true);
  const [recLoading, setRecLoading] = useState(false);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");

  useEffect(() => {
    async function load() {
      try {
        const data = await api.getStudents();
        setStudents(data);
        if (data.length > 0) setSelected(data[0].student_id);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load students");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const getRecommendation = async (studentId: string) => {
    setRecLoading(true);
    setRecommendations([]);
    try {
      const data = await api.recommend(studentId, 3);
      setRecommendations(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to get recommendation");
    } finally {
      setRecLoading(false);
    }
  };

  const currentStudent = students.find((s) => s.student_id === selected);

  const filtered = students.filter((s) =>
    s.name.toLowerCase().includes(search.toLowerCase()) ||
    s.student_id.toLowerCase().includes(search.toLowerCase())
  );

  const getDifficultyColor = (d: number) => {
    if (d <= 1) return "text-success";
    if (d <= 2) return "text-info";
    if (d <= 3) return "text-warning";
    if (d <= 4) return "text-orange-500";
    return "text-danger";
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-48 skeleton" />
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="h-96 skeleton" />
          <div className="lg:col-span-2 h-96 skeleton" />
        </div>
      </div>
    );
  }

  return (
    <div className="page-shell">
      {/* Header */}
      <div className="page-header">
        <div className="page-header-left">
          <h1 className="heading-display text-navy">Student Progress</h1>
          <p className="body text-text-secondary">
            View individual student progress and get AI recommendations
          </p>
        </div>
      </div>

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

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Student List */}
        <div className="card">
          <div className="card-body">
            <div className="flex items-center justify-between mb-3">
              <h2 className="heading-3 text-navy">Students</h2>
              <span className="badge badge-neutral">{students.length}</span>
            </div>

            {/* Search */}
            <div className="relative mb-3">
              <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <circle cx="11" cy="11" r="8" />
                <line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="input pl-10"
                placeholder="Search..."
              />
            </div>

            {filtered.length === 0 ? (
              <p className="caption text-text-muted text-center py-8">No students found</p>
            ) : (
              <div className="space-y-0.5 max-h-[500px] overflow-y-auto">
                {filtered.map((s) => {
                  const grade = scoreToGrade(scoreToPercentage(s.performance_score));
                  return (
                    <button
                      key={s.student_id}
                      onClick={() => {
                        setSelected(s.student_id);
                        setRecommendations([]);
                      }}
                      className={`w-full text-left px-3 py-2.5 rounded-lg text-sm transition-all ${
                        selected === s.student_id
                          ? "bg-gold/10 border border-gold/20"
                          : "hover:bg-surface-elevated border border-transparent"
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2.5 min-w-0">
                          <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold shrink-0 ${
                            selected === s.student_id ? "bg-gold/20 text-gold" : "bg-navy/5 text-navy"
                          }`}>
                            {s.name.charAt(0)}
                          </div>
                          <div className="min-w-0">
                            <div className={`font-medium truncate ${selected === s.student_id ? "text-gold" : "text-navy"}`}>
                              {s.name}
                            </div>
                            <div className="caption text-text-muted font-mono">{s.student_id}</div>
                          </div>
                        </div>
                        <span className={`badge ${GRADE_COLORS[grade]} shrink-0 ml-2`}>
                          {grade}
                        </span>
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* Student Detail */}
        <div className="lg:col-span-2 space-y-5">
          {currentStudent ? (
            <>
              {/* Profile Card */}
              <div className="card">
                <div className="card-body">
                  <div className="flex items-start justify-between mb-5">
                    <div className="flex items-center gap-4">
                      <div className="w-14 h-14 rounded-2xl bg-navy/5 flex items-center justify-center text-navy text-xl font-bold">
                        {currentStudent.name.charAt(0)}
                      </div>
                      <div>
                        <h2 className="heading-1 text-navy">{currentStudent.name}</h2>
                        <p className="body-sm text-text-muted font-mono">{currentStudent.student_id}</p>
                      </div>
                    </div>
                    {(() => {
                      const grade = scoreToGrade(scoreToPercentage(currentStudent.performance_score));
                      return (
                        <span className={`grade-badge text-lg ${GRADE_COLORS[grade]}`}>
                          {grade}
                        </span>
                      );
                    })()}
                  </div>

                  {/* Stats Grid */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 p-4 bg-surface-elevated rounded-xl">
                    <div>
                      <div className="caption text-text-muted mb-1">Score</div>
                      <div className="heading-2 text-navy">
                        {scoreToPercentage(currentStudent.performance_score)}%
                      </div>
                    </div>
                    <div>
                      <div className="caption text-text-muted mb-1">Subject</div>
                      <div className="heading-2 text-navy">{currentStudent.current_topic}</div>
                    </div>
                    <div>
                      <div className="caption text-text-muted mb-1">Class</div>
                      <div className="heading-2 text-navy">{currentStudent.class_id || "N/A"}</div>
                    </div>
                    <div>
                      <div className="caption text-text-muted mb-1">Performance</div>
                      <div className="mt-1">
                        <div className="progress-bar">
                          <div
                            className={`progress-bar-fill ${
                              currentStudent.performance_score >= 0.75 ? "success" :
                              currentStudent.performance_score >= 0.4 ? "" : "danger"
                            }`}
                            style={{ width: `${currentStudent.performance_score * 100}%` }}
                          />
                        </div>
                      </div>
                    </div>
                  </div>

                  <button
                    onClick={() => getRecommendation(currentStudent.student_id)}
                    disabled={recLoading}
                    className="btn btn-secondary mt-4"
                  >
                    {recLoading ? (
                      <>
                        <div className="spinner spinner-sm" style={{ borderTopColor: 'white' }} />
                        Getting recommendations...
                      </>
                    ) : (
                      <>
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                        </svg>
                        Get AI Recommendations
                      </>
                    )}
                  </button>
                </div>
              </div>

              {/* Recommendations */}
              {recommendations.length > 0 && (
                <div className="card">
                  <div className="card-body">
                    <div className="flex items-center justify-between mb-4">
                      <div>
                        <h3 className="heading-2 text-navy">Recommended Content</h3>
                        <p className="caption text-text-muted mt-0.5">
                          AI-selected materials for {currentStudent.name}
                        </p>
                      </div>
                      <span className="badge badge-success">AI Powered</span>
                    </div>

                    <div className="space-y-3">
                      {recommendations.map((rec, i) => (
                        <div
                          key={rec.content_id}
                          className="flex items-center gap-4 p-4 bg-surface-elevated rounded-xl border border-border/50 hover:border-gold/30 transition-colors"
                        >
                          {/* Rank */}
                          <div className="w-10 h-10 rounded-xl bg-gold/10 flex items-center justify-center text-gold font-bold text-sm shrink-0">
                            {i + 1}
                          </div>

                          {/* Info */}
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1">
                              <span className="font-medium text-navy">{rec.title}</span>
                              <span className="badge badge-neutral">{rec.content_type}</span>
                            </div>
                            <div className="flex items-center gap-3">
                              <span className="caption text-text-muted">{rec.topic}</span>
                              <span className="caption text-text-muted">&middot;</span>
                              <span className="caption text-text-muted">Difficulty</span>
                              <div className="flex gap-0.5">
                                {[1, 2, 3, 4, 5].map((d) => (
                                  <div
                                    key={d}
                                    className="w-4 h-1.5 rounded-full"
                                    style={{
                                      background: d <= rec.difficulty ? "var(--color-gold)" : "#e2e8f0",
                                    }}
                                  />
                                ))}
                              </div>
                            </div>
                          </div>

                          {/* Stats */}
                          <div className="text-right shrink-0">
                            <div className="text-sm font-mono font-semibold text-navy">
                              {Math.round(rec.avg_reward * 100)}% reward
                            </div>
                            <div className="caption text-text-muted">
                              recommended {rec.times_recommended}x
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {/* Loading State */}
              {recLoading && (
                <div className="card">
                  <div className="card-body">
                    <div className="flex items-center justify-center py-8 gap-3">
                      <div className="spinner" />
                      <span className="body-sm text-text-muted">Generating recommendations...</span>
                    </div>
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="card">
              <div className="empty-state">
                <div className="empty-state-icon">
                  <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
                    <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                    <circle cx="9" cy="7" r="4" />
                  </svg>
                </div>
                <h3 className="heading-3 text-navy mb-1">Select a student</h3>
                <p className="body-sm text-text-muted">
                  Choose a student from the list to view their progress and recommendations
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
