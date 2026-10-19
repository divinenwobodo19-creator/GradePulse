import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import GradeCalculator, { REMARKS, parseScore } from "../GradeCalculator";
import { scoreToGrade } from "@/lib/types";

describe("GradeCalculator", () => {
  it("reads a score only when it is a number within the maximum", () => {
    expect(parseScore("22", 30)).toBe(22);
    expect(parseScore("12.5", 30)).toBe(12.5);
    expect(parseScore("", 30)).toBeNull();
    expect(parseScore("31", 30)).toBeNull();
    expect(parseScore("-1", 30)).toBeNull();
    expect(parseScore("abc", 70)).toBeNull();
  });

  it("matches the worked example on the page: 22 + 41 is a C4, a credit", () => {
    const total = parseScore("22", 30)! + parseScore("41", 70)!;
    expect(total).toBe(63);
    expect(scoreToGrade(total)).toBe("C4");
    expect(REMARKS.C4).toBe("Credit");
    expect(REMARKS.F9).toBe("Fail");
  });

  it("starts with the core subjects and the CA 30 + exam 70 split", () => {
    const html = renderToStaticMarkup(<GradeCalculator />);
    expect(html).toContain("Mathematics");
    expect(html).toContain("CA (out of 30)");
    expect(html).toContain("Exam (out of 70)");
  });
});

describe("GradeCalculator layouts", () => {
  it("renders a card per subject for phones and the table for larger screens", () => {
    const html = renderToStaticMarkup(<GradeCalculator />);
    expect(html).toContain('class="md:hidden space-y-3"');
    expect(html).toContain("hidden md:block");
    expect(html).toContain("Enter both scores to see the grade");
    // Three starting subjects, each in both layouts.
    expect(html.match(/aria-label="Subject"/g)).toHaveLength(6);
  });
});
