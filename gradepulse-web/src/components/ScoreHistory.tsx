"use client";

import { summariseStudent, toPercent, TIER_REMARKS, type ScoreRow, type SubjectSummary } from "@/lib/reports";
import { scoreToGrade } from "@/lib/types";

export interface StudentScore {
  subject: string;
  score: number; // 0–1
  assessed_on: string;
  label: string;
}

const TREND_TEXT = { up: "up from the test before", down: "down from the test before", same: "same as the test before" };

function formatDate(iso: string): string {
  const date = new Date(`${iso}T00:00:00`);
  return Number.isNaN(date.getTime())
    ? iso
    : date.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

// Scores over time on a 0–100% scale, with the 40% and 75% bands marked.
// Decorative: the same numbers are in the table beside it.
function Sparkline({ scores }: { scores: number[] }) {
  const width = 220;
  const height = 56;
  const pad = 6;
  const x = (i: number) => (scores.length === 1 ? width / 2 : pad + (i * (width - 2 * pad)) / (scores.length - 1));
  const y = (v: number) => pad + (1 - v) * (height - 2 * pad);
  const points = scores.map((v, i) => `${x(i)},${y(v)}`).join(" ");
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden="true" className="shrink-0">
      {[0.4, 0.75].map((band) => (
        <line key={band} x1={0} x2={width} y1={y(band)} y2={y(band)} stroke="var(--color-border-strong)" strokeDasharray="3 4" />
      ))}
      {scores.length > 1 && <polyline points={points} fill="none" stroke="var(--color-navy)" strokeWidth={2} />}
      {scores.map((v, i) => (
        <circle
          key={i}
          cx={x(i)}
          cy={y(v)}
          r={3}
          fill={v < 0.4 ? "var(--color-danger)" : v >= 0.75 ? "var(--color-success)" : "var(--color-navy)"}
        />
      ))}
    </svg>
  );
}

function SubjectHistory({ summary, tests }: { summary: SubjectSummary; tests: StudentScore[] }) {
  return (
    <div className="py-4 first:pt-0 last:pb-0">
      <div className="flex flex-wrap items-center justify-between gap-4 mb-3">
        <div>
          <h4 className="heading-3 text-navy">{summary.subject}</h4>
          <p className="caption text-text-muted">
            Average {toPercent(summary.average)}% ({summary.grade}) over {summary.tests} test
            {summary.tests !== 1 ? "s" : ""} · {TIER_REMARKS[summary.tier]}
            {summary.trend && ` · latest ${TREND_TEXT[summary.trend]}`}
          </p>
        </div>
        <Sparkline scores={tests.map((t) => t.score)} />
      </div>
      <table className="report-table">
        <caption className="sr-only">{summary.subject} test results, newest first</caption>
        <thead>
          <tr>
            <th scope="col">Date</th>
            <th scope="col">Test</th>
            <th scope="col" className="num">Score</th>
            <th scope="col">Grade</th>
          </tr>
        </thead>
        <tbody>
          {[...tests].reverse().map((t, i) => (
            <tr key={`${t.assessed_on}-${t.label}-${i}`}>
              <td>{formatDate(t.assessed_on)}</td>
              <td>{t.label || "—"}</td>
              <td className="num">{toPercent(t.score)}%</td>
              <td>{scoreToGrade(toPercent(t.score))}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// Every recorded test for one student, grouped by subject. `scores` must be
// oldest first, as GET /students/{id}/scores returns them.
export default function ScoreHistory({ scores, subjects }: { scores: StudentScore[]; subjects: string[] }) {
  if (scores.length === 0) {
    return <p className="body-sm text-text-muted">No test scores recorded yet. Enter them on the Scores page.</p>;
  }
  const rows: ScoreRow[] = scores.map((s) => ({ ...s, student_id: "" }));
  return (
    <div className="divide-y divide-border">
      {summariseStudent(rows, subjects).map((summary) => (
        <SubjectHistory
          key={summary.subject}
          summary={summary}
          tests={scores.filter((s) => s.subject === summary.subject)}
        />
      ))}
    </div>
  );
}
