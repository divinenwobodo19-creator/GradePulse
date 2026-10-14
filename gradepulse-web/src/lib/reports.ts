import { scoreToGrade, type GradeLevel } from "./types";

export interface ScoreRow {
  student_id: string;
  subject: string;
  score: number; // 0–1
  assessed_on: string;
  label: string;
}

export type Tier = "remediation" | "on_track" | "ahead";

export interface SubjectSummary {
  subject: string;
  tests: number;
  latest: number;
  average: number;
  grade: GradeLevel;
  tier: Tier;
  // Latest test against the one before it; null with fewer than two tests.
  trend: "up" | "down" | "same" | null;
}

export const TIER_REMARKS: Record<Tier, string> = {
  remediation: "Needs extra help",
  on_track: "On track",
  ahead: "Ahead of class",
};

// Same bands as the triage report: below 40% / 40–74% / 75% and above.
export function tierFor(average: number): Tier {
  if (average < 0.4) return "remediation";
  if (average < 0.75) return "on_track";
  return "ahead";
}

export function toPercent(score: number): number {
  return Math.round(score * 100);
}

function mean(values: number[]): number {
  return values.reduce((sum, v) => sum + v, 0) / values.length;
}

// One row per subject the student has a score in. `rows` must be oldest first
// (the API returns them that way). Subjects follow `subjectOrder`, with any
// subject not on that list after it, alphabetically.
export function summariseStudent(rows: ScoreRow[], subjectOrder: string[]): SubjectSummary[] {
  const bySubject = new Map<string, number[]>();
  for (const row of rows) {
    const scores = bySubject.get(row.subject) ?? [];
    scores.push(row.score);
    bySubject.set(row.subject, scores);
  }

  const rank = (subject: string) => {
    const index = subjectOrder.indexOf(subject);
    return index === -1 ? subjectOrder.length : index;
  };

  return [...bySubject.entries()]
    .sort(([a], [b]) => rank(a) - rank(b) || a.localeCompare(b))
    .map(([subject, scores]) => {
      const latest = scores[scores.length - 1];
      const previous = scores.length > 1 ? scores[scores.length - 2] : null;
      const average = mean(scores);
      return {
        subject,
        tests: scores.length,
        latest,
        average,
        grade: scoreToGrade(toPercent(average)),
        tier: tierFor(average),
        trend: previous === null ? null : latest > previous ? "up" : latest < previous ? "down" : "same",
      };
    });
}

// Mean of the subject averages, so a subject with many tests does not outweigh the rest.
export function overallAverage(summaries: SubjectSummary[]): number | null {
  return summaries.length > 0 ? mean(summaries.map((s) => s.average)) : null;
}

export function groupByStudent(rows: ScoreRow[]): Map<string, ScoreRow[]> {
  const grouped = new Map<string, ScoreRow[]>();
  for (const row of rows) {
    const list = grouped.get(row.student_id) ?? [];
    list.push(row);
    grouped.set(row.student_id, list);
  }
  return grouped;
}
