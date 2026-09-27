import { describe, expect, it } from "vitest";
import { getStudentClassId, scoreToGrade, scoreToPercentage, type Student } from "../types";

const baseStudent: Student = {
  student_id: "S1",
  name: "Ada Okonkwo",
  performance_score: 0.82,
  current_topic: "MATH",
};

describe("getStudentClassId", () => {
  it("prefers an explicit class_id", () => {
    expect(getStudentClassId({ ...baseStudent, class_id: "CLASS-9" })).toBe("CLASS-9");
  });

  it("falls back to metadata.class_id when class_id is absent", () => {
    expect(getStudentClassId({ ...baseStudent, metadata: { class_id: "CLASS-2" } })).toBe(
      "CLASS-2"
    );
  });

  it("treats null and non-string metadata values as unassigned", () => {
    expect(getStudentClassId({ ...baseStudent, class_id: null })).toBeNull();
    expect(getStudentClassId({ ...baseStudent, metadata: { class_id: 42 } })).toBeNull();
    expect(getStudentClassId(baseStudent)).toBeNull();
  });
});

describe("grade boundaries", () => {
  it("maps percentages to the documented grade levels", () => {
    expect(scoreToGrade(100)).toBe("A1");
    expect(scoreToGrade(75)).toBe("A1");
    expect(scoreToGrade(74)).toBe("B2");
    expect(scoreToGrade(70)).toBe("B2");
    expect(scoreToGrade(69)).toBe("B3");
    expect(scoreToGrade(65)).toBe("B3");
    expect(scoreToGrade(64)).toBe("C4");
    expect(scoreToGrade(60)).toBe("C4");
    expect(scoreToGrade(59)).toBe("C5");
    expect(scoreToGrade(55)).toBe("C5");
    expect(scoreToGrade(54)).toBe("C6");
    expect(scoreToGrade(50)).toBe("C6");
    expect(scoreToGrade(49)).toBe("D7");
    expect(scoreToGrade(45)).toBe("D7");
    expect(scoreToGrade(44)).toBe("E8");
    expect(scoreToGrade(40)).toBe("E8");
    expect(scoreToGrade(39)).toBe("F9");
    expect(scoreToGrade(0)).toBe("F9");
  });

  it("converts normalized scores to whole percentages", () => {
    expect(scoreToPercentage(0)).toBe(0);
    expect(scoreToPercentage(0.5)).toBe(50);
    expect(scoreToPercentage(0.826)).toBe(83);
    expect(scoreToPercentage(1)).toBe(100);
  });
});
