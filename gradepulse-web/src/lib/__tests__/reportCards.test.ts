import { describe, expect, it } from "vitest";
import { WAEC_SCALE, formatMark, gradeKey, incompleteCards, longDate, ordinal, parseExamMark } from "../reportCards";
import type { ReportCard } from "../types";

describe("report card helpers", () => {
  it("writes positions as ordinals", () => {
    expect([1, 2, 3, 4, 11, 12, 13, 21, 22, 23, 101, 111].map(ordinal)).toEqual([
      "1st", "2nd", "3rd", "4th", "11th", "12th", "13th", "21st", "22nd", "23rd", "101st", "111th",
    ]);
  });

  it("prints marks without a needless .0", () => {
    expect(formatMark(45)).toBe("45");
    expect(formatMark(45.5)).toBe("45.5");
    expect(formatMark(null)).toBe("—");
  });

  it("turns a typed exam mark into the share the API stores", () => {
    expect(parseExamMark("45", 60)).toEqual({ ok: true, score: 0.75 });
    expect(parseExamMark(" 60 ", 60)).toEqual({ ok: true, score: 1 });
    expect(parseExamMark("", 60)).toEqual({ ok: true, score: null });
    expect(parseExamMark("61", 60).ok).toBe(false);
    expect(parseExamMark("-1", 60).ok).toBe(false);
    expect(parseExamMark("abc", 60).ok).toBe(false);
  });

  it("builds the WAEC grade key with ranges", () => {
    const key = gradeKey(WAEC_SCALE);
    expect(key[0]).toEqual({ grade: "A1", range: "75–100", remark: "Excellent" });
    expect(key[1].range).toBe("70–74");
    expect(key[key.length - 1]).toEqual({ grade: "F9", range: "0–39", remark: "Fail" });
  });

  it("prints dates in full", () => {
    expect(longDate("2027-01-11")).toBe("11 January 2027");
    expect(longDate("")).toBe("");
  });

  it("lists the cards that still lack a part", () => {
    const card = (name: string, missing: string[]) => ({ name, missing }) as unknown as ReportCard;
    expect(incompleteCards([card("Ada", ["ENGLISH"]), card("Bayo", [])])).toEqual([
      { name: "Ada", missing: ["ENGLISH"] },
    ]);
  });
});
