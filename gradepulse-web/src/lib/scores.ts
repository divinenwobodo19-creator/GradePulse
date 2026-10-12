export const SCORE_MIN_PERCENT = 0;
export const SCORE_MAX_PERCENT = 100;

export interface ScoreValidation {
  valid: boolean;
  normalized: number | null;
}

export function validateScorePercent(value: string | number): ScoreValidation {
  if (typeof value === "string" && value.trim() === "") {
    return { valid: false, normalized: null };
  }

  const numeric = typeof value === "number" ? value : Number(value.trim());
  if (!Number.isFinite(numeric)) {
    return { valid: false, normalized: null };
  }
  if (numeric < SCORE_MIN_PERCENT || numeric > SCORE_MAX_PERCENT) {
    return { valid: false, normalized: null };
  }

  return { valid: true, normalized: numeric / 100 };
}

export function percentToScore(percent: string | number): number {
  const { normalized } = validateScorePercent(percent);
  if (normalized === null) {
    throw new RangeError(`Score must be between ${SCORE_MIN_PERCENT} and ${SCORE_MAX_PERCENT}`);
  }
  return normalized;
}

export function scoreToPercent(score: number): number {
  if (!Number.isFinite(score)) return 0;
  return Math.round(Math.min(1, Math.max(0, score)) * 100);
}

// Always a non-empty string so a genuine 0% score is never rendered as an empty field.
export function scoreToInputValue(score: number): string {
  return String(scoreToPercent(score));
}

type ScoredStudent = { performance_score: number; grade_history?: Record<string, number[]> };

export const NO_SCORE_LABEL = "—";

// A student with no recorded scores only has a placeholder performance_score,
// so screens show a dash for them instead of a made-up percentage.
export function hasScores(student: ScoredStudent): boolean {
  return Object.values(student.grade_history ?? {}).some((scores) => scores.length > 0);
}

export function latestSubjectScore(student: ScoredStudent, subject: string): number | null {
  const scores = student.grade_history?.[subject];
  return scores && scores.length > 0 ? scores[scores.length - 1] : null;
}

export function overallPercentLabel(student: ScoredStudent): string {
  return hasScores(student) ? `${scoreToPercent(student.performance_score)}%` : NO_SCORE_LABEL;
}

export function todayIsoDate(now: Date = new Date()): string {
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 10);
}
