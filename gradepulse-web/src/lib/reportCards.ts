// Helpers for term report cards: marks typed by teachers, ordinal positions,
// the grade key and dates as printed on a card.
import type { GradeBand, ReportCard } from "./types";

/** 1 → "1st", 2 → "2nd", 11 → "11th", 22 → "22nd". */
export function ordinal(n: number): string {
  const tens = n % 100;
  if (tens >= 11 && tens <= 13) return `${n}th`;
  switch (n % 10) {
    case 1:
      return `${n}st`;
    case 2:
      return `${n}nd`;
    case 3:
      return `${n}rd`;
    default:
      return `${n}th`;
  }
}

/** A mark as printed: whole numbers without ".0", otherwise one decimal. */
export function formatMark(mark: number | null | undefined): string {
  if (mark === null || mark === undefined) return "—";
  return Number.isInteger(mark) ? String(mark) : mark.toFixed(1);
}

/**
 * What a teacher typed in an exam box, as the 0–1 share the API stores.
 * "" means clear it (null); anything that is not a number between 0 and the
 * exam's full mark is an error.
 */
export function parseExamMark(
  text: string,
  examWeight: number
): { ok: true; score: number | null } | { ok: false; error: string } {
  const trimmed = text.trim();
  if (trimmed === "") return { ok: true, score: null };
  const mark = Number(trimmed);
  if (!Number.isFinite(mark) || mark < 0 || mark > examWeight) {
    return { ok: false, error: `Enter a mark from 0 to ${examWeight}` };
  }
  return { ok: true, score: Math.round((mark / examWeight) * 10000) / 10000 };
}

/** The grade key printed under the table, e.g. "A1 75–100 Excellent". */
export function gradeKey(scale: GradeBand[]): { grade: string; range: string; remark: string }[] {
  const bands = [...scale].sort((a, b) => b.min - a.min);
  return bands.map((band, i) => {
    const upper = i === 0 ? 100 : bands[i - 1].min - (Number.isInteger(bands[i - 1].min) ? 1 : 0.1);
    return { grade: band.grade, range: `${formatMark(band.min)}–${formatMark(upper)}`, remark: band.remark };
  });
}

/** "2027-01-11" → "11 January 2027" (as printed on the card). */
export function longDate(iso: string): string {
  if (!iso) return "";
  const [y, m, d] = iso.split("-").map(Number);
  if (!y || !m || !d) return iso;
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  });
}

/** Students whose card still lacks a part, with the subjects missing. */
export function incompleteCards(cards: ReportCard[]): { name: string; missing: string[] }[] {
  return cards.filter((c) => c.missing.length > 0).map((c) => ({ name: c.name, missing: c.missing }));
}

/** The WAEC scale, for the "reset" button in Settings. Mirrors the server default. */
export const WAEC_SCALE: GradeBand[] = [
  { grade: "A1", min: 75, remark: "Excellent" },
  { grade: "B2", min: 70, remark: "Very good" },
  { grade: "B3", min: 65, remark: "Good" },
  { grade: "C4", min: 60, remark: "Credit" },
  { grade: "C5", min: 55, remark: "Credit" },
  { grade: "C6", min: 50, remark: "Credit" },
  { grade: "D7", min: 45, remark: "Pass" },
  { grade: "E8", min: 40, remark: "Pass" },
  { grade: "F9", min: 0, remark: "Fail" },
];
