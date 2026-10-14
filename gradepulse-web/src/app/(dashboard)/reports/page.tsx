"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useSubjects } from "@/lib/subjects";
import {
  TIER_REMARKS,
  groupByStudent,
  overallAverage,
  summariseStudent,
  toPercent,
  type ScoreRow,
  type SubjectSummary,
} from "@/lib/reports";
import { scoreToGrade, getStudentClassId, type SchoolClass, type Student } from "@/lib/types";

type View = "class" | "students";

const TREND_MARK = { up: "▲", down: "▼", same: "=" } as const;

function formatToday(): string {
  return new Date().toLocaleDateString(undefined, { day: "numeric", month: "long", year: "numeric" });
}

interface StudentReport {
  student: Student;
  classLabel: string;
  subjects: SubjectSummary[];
  overall: number | null;
}

function ReportHeader({ school, title, detail }: { school: string; title: string; detail: string }) {
  return (
    <div className="flex items-start justify-between gap-4 mb-5">
      <div>
        <div className="caption font-semibold text-text-secondary uppercase tracking-wider">{school}</div>
        <h2 className="heading-1 text-navy">{title}</h2>
        <p className="body-sm text-text-secondary">{detail}</p>
      </div>
      <div className="caption text-text-muted text-right shrink-0">
        {formatToday()}
        <div>GradePulse</div>
      </div>
    </div>
  );
}

function ClassSummary({ school, classLabel, reports, columns }: {
  school: string;
  classLabel: string;
  reports: StudentReport[];
  columns: string[];
}) {
  return (
    <section className="card report-sheet">
      <div className="card-body">
        <ReportHeader
          school={school}
          title="Class Report"
          detail={`${classLabel} · ${reports.length} student${reports.length !== 1 ? "s" : ""} · average score and grade per subject`}
        />
        <div className="overflow-x-auto">
          <table className="report-table">
            <thead>
              <tr>
                <th scope="col">Student</th>
                {columns.map((subject) => (
                  <th key={subject} scope="col" className="num">{subject}</th>
                ))}
                <th scope="col" className="num">Overall</th>
                <th scope="col">Needs help in</th>
              </tr>
            </thead>
            <tbody>
              {reports.map(({ student, subjects, overall }) => {
                const bySubject = new Map(subjects.map((s) => [s.subject, s]));
                const weak = subjects.filter((s) => s.tier === "remediation").map((s) => s.subject);
                return (
                  <tr key={student.student_id}>
                    <th scope="row">{student.name}</th>
                    {columns.map((subject) => {
                      const summary = bySubject.get(subject);
                      return (
                        <td key={subject} className="num">
                          {summary ? `${toPercent(summary.average)}% ${summary.grade}` : "—"}
                        </td>
                      );
                    })}
                    <td className="num font-semibold">
                      {overall === null ? "—" : `${toPercent(overall)}% ${scoreToGrade(toPercent(overall))}`}
                    </td>
                    <td>{weak.length > 0 ? weak.join(", ") : "—"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <p className="caption text-text-muted mt-3">
          Grades follow WAEC bands: A1 75% and above, B2–E8 40–74%, F9 below 40%. “Needs help in” lists subjects
          where the average is below 40%.
        </p>
      </div>
    </section>
  );
}

function StudentSheet({ school, report }: { school: string; report: StudentReport }) {
  const { student, classLabel, subjects, overall } = report;
  return (
    <section className="card report-sheet">
      <div className="card-body">
        <ReportHeader
          school={school}
          title={student.name}
          detail={`Progress report · ${classLabel || "No class"} · ID ${student.student_id}`}
        />

        {subjects.length === 0 ? (
          <p className="body-sm text-text-muted">No test scores have been recorded for this student yet.</p>
        ) : (
          <>
            <table className="report-table">
              <thead>
                <tr>
                  <th scope="col">Subject</th>
                  <th scope="col" className="num">Tests</th>
                  <th scope="col" className="num">Latest</th>
                  <th scope="col" className="num">Average</th>
                  <th scope="col">Grade</th>
                  <th scope="col">Remark</th>
                </tr>
              </thead>
              <tbody>
                {subjects.map((s) => (
                  <tr key={s.subject}>
                    <th scope="row">{s.subject}</th>
                    <td className="num">{s.tests}</td>
                    <td className="num">
                      {toPercent(s.latest)}%{s.trend && <span className="ml-1 text-text-muted">{TREND_MARK[s.trend]}</span>}
                    </td>
                    <td className="num">{toPercent(s.average)}%</td>
                    <td>{s.grade}</td>
                    <td>{TIER_REMARKS[s.tier]}</td>
                  </tr>
                ))}
              </tbody>
              {overall !== null && (
                <tfoot>
                  <tr>
                    <th scope="row" colSpan={3}>Overall average</th>
                    <td className="num font-semibold">{toPercent(overall)}%</td>
                    <td className="font-semibold">{scoreToGrade(toPercent(overall))}</td>
                    <td />
                  </tr>
                </tfoot>
              )}
            </table>
            <p className="caption text-text-muted mt-3">
              ▲, ▼ and = show whether the latest test was higher, lower or the same as the one before. Grades follow
              WAEC bands: A1 75% and above, F9 below 40%.
            </p>
          </>
        )}

        <div className="grid grid-cols-2 gap-10 mt-10 caption text-text-secondary">
          <div className="border-t border-border-strong pt-2">Class teacher</div>
          <div className="border-t border-border-strong pt-2">Parent / guardian</div>
        </div>
      </div>
    </section>
  );
}

export default function ReportsPage() {
  const { user, loading: authLoading } = useAuth();
  const schoolSubjects = useSubjects();
  const [classes, setClasses] = useState<SchoolClass[]>([]);
  const [students, setStudents] = useState<Student[]>([]);
  const [scores, setScores] = useState<ScoreRow[]>([]);
  const [classId, setClassId] = useState("");
  // /reports?view=students opens straight on the progress sheets.
  const [view, setView] = useState<View>(() =>
    typeof window !== "undefined" && new URLSearchParams(window.location.search).get("view") === "students"
      ? "students"
      : "class"
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (authLoading || !user) return;

    let cancelled = false;
    const controller = new AbortController();
    async function load() {
      try {
        const [nextClasses, nextStudents, nextScores] = await Promise.all([
          user?.school_id ? api.getClasses(user.school_id, controller.signal) : Promise.resolve([]),
          api.getStudents(undefined, undefined, controller.signal),
          api.getSchoolScores(undefined, controller.signal),
        ]);
        if (!cancelled) {
          setClasses(nextClasses);
          setStudents(nextStudents);
          setScores(nextScores);
        }
      } catch (err) {
        if (!cancelled && !(err instanceof Error && err.name === "AbortError")) {
          setError(err instanceof Error ? err.message : "Failed to load reports");
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

  const reports = useMemo<StudentReport[]>(() => {
    const byStudent = groupByStudent(scores);
    return students
      .filter((s) => !classId || getStudentClassId(s) === classId)
      .map((student) => {
        const subjects = summariseStudent(byStudent.get(student.student_id) ?? [], schoolSubjects);
        return {
          student,
          classLabel: classes.find((c) => c.class_id === getStudentClassId(student))?.label ?? "",
          subjects,
          overall: overallAverage(subjects),
        };
      });
  }, [students, scores, classes, classId, schoolSubjects]);

  // Columns: subjects anyone in the selection has a score in, in the school's order.
  const columns = useMemo(() => {
    const seen = new Set(reports.flatMap((r) => r.subjects.map((s) => s.subject)));
    const listed = schoolSubjects.filter((s) => seen.has(s));
    const extra = [...seen].filter((s) => !schoolSubjects.includes(s)).sort();
    return [...listed, ...extra];
  }, [reports, schoolSubjects]);

  const school = user?.school_name || "Your school";
  const classLabel = classId ? classes.find((c) => c.class_id === classId)?.label ?? "Class" : "All classes";

  if (authLoading || loading) {
    return (
      <div role="status" aria-live="polite" className="space-y-6">
        <div className="h-8 w-48 skeleton" />
        <div className="h-16 skeleton" />
        <div className="h-64 skeleton" />
      </div>
    );
  }

  return (
    <div className="page-shell">
      <div className="page-header no-print">
        <div className="page-header-left">
          <h1 className="heading-display text-navy">Reports</h1>
          <p className="body text-text-secondary">
            A class summary for the teacher, or one progress sheet per student to send home
          </p>
        </div>
        <button
          type="button"
          onClick={() => window.print()}
          disabled={reports.length === 0}
          className="btn btn-primary"
        >
          Print
        </button>
      </div>

      {error && (
        <div role="alert" aria-live="assertive" className="no-print bg-danger-light border border-danger/20 text-danger px-4 py-3 rounded-lg text-sm">
          {error}
        </div>
      )}

      <div className="card no-print">
        <div className="card-body flex flex-wrap items-end gap-4">
          <div className="input-group">
            <label className="input-label" htmlFor="report-class">Class</label>
            <select
              id="report-class"
              value={classId}
              onChange={(e) => setClassId(e.target.value)}
              className="input select w-auto min-w-[160px]"
            >
              <option value="">All classes</option>
              {classes.map((c) => (
                <option key={c.class_id} value={c.class_id}>{c.label}</option>
              ))}
            </select>
          </div>
          <div className="input-group">
            <label className="input-label" htmlFor="report-view">Report</label>
            <select
              id="report-view"
              value={view}
              onChange={(e) => setView(e.target.value as View)}
              className="input select w-auto min-w-[220px]"
            >
              <option value="class">Class summary (one page)</option>
              <option value="students">Student progress sheets (one each)</option>
            </select>
          </div>
          <p className="caption text-text-muted ml-auto">
            {reports.length} student{reports.length !== 1 ? "s" : ""} · printing leaves out the menu and these controls
          </p>
        </div>
      </div>

      {reports.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <h3 className="heading-3 text-navy mb-1">No students to report on</h3>
            <p className="body-sm text-text-muted">
              {classId ? "This class has no students yet." : "Add students and enter scores first."}
            </p>
          </div>
        </div>
      ) : view === "class" ? (
        <ClassSummary school={school} classLabel={classLabel} reports={reports} columns={columns} />
      ) : (
        reports.map((report) => (
          <StudentSheet key={report.student.student_id} school={school} report={report} />
        ))
      )}
    </div>
  );
}
