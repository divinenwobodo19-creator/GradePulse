import { describe, expect, it } from "vitest";
import {
  percentToScore,
  scoreToInputValue,
  scoreToPercent,
  validateScorePercent,
} from "../scores";

describe("validateScorePercent", () => {
  it("accepts whole percentages inside the valid range", () => {
    expect(validateScorePercent("0")).toEqual({ valid: true, normalized: 0 });
    expect(validateScorePercent("100")).toEqual({ valid: true, normalized: 1 });
    expect(validateScorePercent(64)).toEqual({ valid: true, normalized: 0.64 });
  });

  it("trims whitespace and accepts decimal percentages", () => {
    expect(validateScorePercent(" 72.5 ")).toEqual({ valid: true, normalized: 0.725 });
  });

  it("rejects blank, non-numeric and out-of-range input", () => {
    expect(validateScorePercent("")).toEqual({ valid: false, normalized: null });
    expect(validateScorePercent("   ")).toEqual({ valid: false, normalized: null });
    expect(validateScorePercent("abc")).toEqual({ valid: false, normalized: null });
    expect(validateScorePercent("-1")).toEqual({ valid: false, normalized: null });
    expect(validateScorePercent("101")).toEqual({ valid: false, normalized: null });
    expect(validateScorePercent(Number.NaN)).toEqual({ valid: false, normalized: null });
    expect(validateScorePercent(Number.POSITIVE_INFINITY)).toEqual({
      valid: false,
      normalized: null,
    });
  });
});

describe("percentToScore", () => {
  it("converts percentages to the 0-1 API range", () => {
    expect(percentToScore("80")).toBe(0.8);
    expect(percentToScore(0)).toBe(0);
    expect(percentToScore("100")).toBe(1);
  });

  it("throws for invalid percentages so invalid values are never sent", () => {
    expect(() => percentToScore("")).toThrow(RangeError);
    expect(() => percentToScore("120")).toThrow(RangeError);
  });
});

describe("scoreToPercent", () => {
  it("rounds normalized scores to whole percentages", () => {
    expect(scoreToPercent(0.5)).toBe(50);
    expect(scoreToPercent(0.665)).toBe(67);
    expect(scoreToPercent(1)).toBe(100);
    expect(scoreToPercent(0)).toBe(0);
  });

  it("clamps out-of-band and non-finite scores", () => {
    expect(scoreToPercent(1.4)).toBe(100);
    expect(scoreToPercent(-0.2)).toBe(0);
    expect(scoreToPercent(Number.NaN)).toBe(0);
  });
});

describe("scoreToInputValue", () => {
  it("renders a genuine 0% score instead of an empty field", () => {
    expect(scoreToInputValue(0)).toBe("0");
    expect(scoreToInputValue(0.004)).toBe("0");
  });

  it("round-trips through percentToScore without losing the value", () => {
    for (const score of [0, 0.34, 0.5, 0.88, 1]) {
      expect(percentToScore(scoreToInputValue(score))).toBeCloseTo(score, 10);
    }
  });
});
