import { describe, expect, it } from "vitest";
import { groupByStudent, overallAverage, summariseStudent, tierFor, type ScoreRow } from "../reports";

const row = (subject: string, score: number, student_id = "S1"): ScoreRow => ({
  student_id,
  subject,
  score,
  assessed_on: "2026-09-07",
  label: "",
});

describe("tierFor", () => {
  it("uses the triage bands", () => {
    expect(tierFor(0.39)).toBe("remediation");
    expect(tierFor(0.4)).toBe("on_track");
    expect(tierFor(0.749)).toBe("on_track");
    expect(tierFor(0.75)).toBe("ahead");
  });
});

describe("summariseStudent", () => {
  it("summarises each subject from oldest-first scores", () => {
    const [math] = summariseStudent([row("MATH", 0.3), row("MATH", 0.5), row("MATH", 0.7)], ["MATH"]);
    expect(math).toMatchObject({ subject: "MATH", tests: 3, latest: 0.7, grade: "C6", tier: "on_track", trend: "up" });
    expect(math.average).toBeCloseTo(0.5);
  });

  it("reports the trend of the latest test against the one before", () => {
    const trend = (...scores: number[]) => summariseStudent(scores.map((s) => row("MATH", s)), [])[0].trend;
    expect(trend(0.5)).toBeNull();
    expect(trend(0.5, 0.4)).toBe("down");
    expect(trend(0.5, 0.5)).toBe("same");
  });

  it("orders subjects by the school's list, then the rest alphabetically", () => {
    const rows = [row("YORUBA", 0.5), row("ENGLISH", 0.5), row("ART", 0.5), row("MATH", 0.5)];
    expect(summariseStudent(rows, ["MATH", "ENGLISH"]).map((s) => s.subject)).toEqual([
      "MATH",
      "ENGLISH",
      "ART",
      "YORUBA",
    ]);
  });

  it("returns nothing for a student with no scores", () => {
    expect(summariseStudent([], ["MATH"])).toEqual([]);
    expect(overallAverage([])).toBeNull();
  });
});

describe("overallAverage", () => {
  it("weights every subject equally, however many tests it has", () => {
    const summaries = summariseStudent([row("MATH", 1), row("MATH", 1), row("MATH", 1), row("ENGLISH", 0)], []);
    expect(overallAverage(summaries)).toBeCloseTo(0.5);
  });
});

describe("groupByStudent", () => {
  it("keeps each student's scores in their original order", () => {
    const grouped = groupByStudent([row("MATH", 0.1, "A"), row("MATH", 0.2, "B"), row("MATH", 0.3, "A")]);
    expect(grouped.get("A")?.map((r) => r.score)).toEqual([0.1, 0.3]);
    expect(grouped.get("B")?.map((r) => r.score)).toEqual([0.2]);
  });
});
