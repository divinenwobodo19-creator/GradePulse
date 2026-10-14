import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import ScoreHistory from "../ScoreHistory";

const result = (subject: string, score: number, assessed_on: string, label = "") => ({
  subject,
  score,
  assessed_on,
  label,
});

describe("ScoreHistory", () => {
  it("says so when there are no scores", () => {
    expect(renderToStaticMarkup(<ScoreHistory scores={[]} subjects={["MATH"]} />)).toContain(
      "No test scores recorded yet"
    );
  });

  it("groups by subject in the school's order and lists tests newest first", () => {
    const html = renderToStaticMarkup(
      <ScoreHistory
        subjects={["MATH", "ENGLISH"]}
        scores={[
          result("ENGLISH", 0.8, "2026-09-07", "Week 1 test"),
          result("MATH", 0.3, "2026-09-07", "Week 1 test"),
          result("MATH", 0.5, "2026-09-14", "Week 2 test"),
        ]}
      />
    );
    expect(html.indexOf(">MATH<")).toBeLessThan(html.indexOf(">ENGLISH<"));
    expect(html.indexOf("Week 2 test")).toBeLessThan(html.indexOf("Week 1 test"));
    expect(html).toContain("Average 40% (E8) over 2 tests");
    expect(html).toContain("latest up from the test before");
    expect(html).toContain("<svg");
  });
});
