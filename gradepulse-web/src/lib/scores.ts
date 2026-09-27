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
