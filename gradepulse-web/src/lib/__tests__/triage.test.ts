import { describe, expect, it } from "vitest";
import { currentScore, hasLastWeek, movementLabel, pointsLabel } from "../triage";
import type { TriageResult, TriageStudent } from "../types";

const student = (extra: Partial<TriageStudent>): TriageStudent => ({
  student_id: "S1",
  name: "Ada",
  predicted_score: 0.3,
  attempts: 2,
  ...extra,
});

describe("pointsLabel", () => {
  it("shows signed percentage points", () => {
    expect(pointsLabel(0.12)).toBe("+12 pts");
    expect(pointsLabel(-0.08)).toBe("−8 pts");
    expect(pointsLabel(0.001)).toBe("no change");
    expect(pointsLabel(null)).toBe("");
  });
});

describe("movementLabel", () => {
  it("flags students who moved into needs help", () => {
    expect(movementLabel(student({ movement: "moved_into_help", change: -0.2 }))).toEqual({
      text: "New this week, −20 pts",
      tone: "text-danger",
    });
  });
  it("marks a first week without a comparison", () => {
    expect(movementLabel(student({ movement: "new", change: null }))?.text).toBe("First week");
  });
  it("shows nothing for an older server", () => {
    expect(movementLabel(student({}))).toBeNull();
  });
});

describe("hasLastWeek and currentScore", () => {
  const report = (students: TriageStudent[]): TriageResult => ({
    subject: "MATH",
    total_students: students.length,
    tiers: { remediation: { students, count: students.length, recommended_difficulty: 1, note: "" } },
    scope: "assessed_only",
  });
  it("is false until someone has an earlier test", () => {
    expect(hasLastWeek(report([student({ previous_score: null })]))).toBe(false);
    expect(hasLastWeek(report([student({ previous_score: 0.5 })]))).toBe(true);
  });
  it("prefers the recent average", () => {
    expect(currentScore(student({ current_score: 0.45 }))).toBe(0.45);
    expect(currentScore(student({}))).toBe(0.3);
  });
});
