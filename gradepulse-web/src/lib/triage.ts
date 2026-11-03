import type { TriageResult, TriageStudent } from "./types";

/** Percentage points, signed: "+12 pts", "−8 pts", "no change". */
export function pointsLabel(change: number | null | undefined): string {
  if (change === null || change === undefined) return "";
  const pts = Math.round(change * 100);
  if (pts === 0) return "no change";
  return pts > 0 ? `+${pts} pts` : `−${Math.abs(pts)} pts`;
}

/** What to show beside a student's score: how they moved since last week. */
export function movementLabel(s: TriageStudent): { text: string; tone: string } | null {
  switch (s.movement) {
    case "moved_into_help":
      return { text: `New this week, ${pointsLabel(s.change)}`, tone: "text-danger" };
    case "left_help":
      return { text: `Out of needs help, ${pointsLabel(s.change)}`, tone: "text-success" };
    case "falling":
      return { text: pointsLabel(s.change), tone: "text-danger" };
    case "rising":
      return { text: pointsLabel(s.change), tone: "text-success" };
    case "steady":
      return { text: pointsLabel(s.change), tone: "text-text-muted" };
    case "new":
      return { text: "First week", tone: "text-text-muted" };
    default:
      return null;
  }
}

/** "Fri 9 Oct" style date for the report's week. */
export function shortDate(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(`${iso}T00:00:00`);
  return d.toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" });
}

/** True when the report can compare with last week (someone has an earlier test). */
export function hasLastWeek(report: TriageResult): boolean {
  return Object.values(report.tiers).some((t) => t.students.some((s) => s.previous_score != null));
}

/** Score shown for a student: the recent average. */
export function currentScore(s: TriageStudent): number {
  return s.current_score ?? s.predicted_score ?? 0;
}
