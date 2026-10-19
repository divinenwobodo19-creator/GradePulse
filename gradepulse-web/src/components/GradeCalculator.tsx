"use client";

import { useState } from "react";
import { scoreToGrade, type GradeLevel } from "@/lib/types";

export const REMARKS: Record<GradeLevel, string> = {
  A1: "Excellent", B2: "Very good", B3: "Good", C4: "Credit", C5: "Credit", C6: "Credit",
  D7: "Pass", E8: "Pass", F9: "Fail",
};

const SPLITS = [
  { label: "CA 30 + Exam 70", ca: 30, exam: 70 },
  { label: "CA 40 + Exam 60", ca: 40, exam: 60 },
];

interface Row { id: number; subject: string; ca: string; exam: string }

const START: Row[] = [
  { id: 1, subject: "Mathematics", ca: "", exam: "" },
  { id: 2, subject: "English Language", ca: "", exam: "" },
  { id: 3, subject: "Basic Science", ca: "", exam: "" },
];

/** A score typed into a box: a number within 0..max, or null while empty or invalid. */
export function parseScore(value: string, max: number): number | null {
  if (value.trim() === "") return null;
  const n = Number(value);
  return Number.isFinite(n) && n >= 0 && n <= max ? n : null;
}

export default function GradeCalculator() {
  const [split, setSplit] = useState(0);
  const [rows, setRows] = useState<Row[]>(START);
  const { ca: caMax, exam: examMax } = SPLITS[split];

  const results = rows.map((row) => {
    const ca = parseScore(row.ca, caMax);
    const exam = parseScore(row.exam, examMax);
    const invalid = (row.ca !== "" && ca === null) || (row.exam !== "" && exam === null);
    const total = ca !== null && exam !== null ? ca + exam : null;
    return { row, invalid, total, grade: total !== null ? scoreToGrade(total) : null };
  });
  const totals = results.map((r) => r.total).filter((t): t is number => t !== null);
  const average = totals.length ? totals.reduce((a, b) => a + b, 0) / totals.length : null;

  const update = (id: number, field: keyof Row, value: string) =>
    setRows((rs) => rs.map((r) => (r.id === id ? { ...r, [field]: value } : r)));

  return (
    <div className="card">
      <div className="card-body space-y-5">
        <fieldset className="flex flex-wrap items-center gap-4">
          <legend className="input-label mb-2">How your school splits the marks</legend>
          {SPLITS.map((s, i) => (
            <label key={s.label} className="flex items-center gap-2 body-sm text-text-primary cursor-pointer">
              <input type="radio" name="split" checked={split === i} onChange={() => setSplit(i)} />
              {s.label}
            </label>
          ))}
        </fieldset>

        {/* Phones: one card per subject, so every box and the result fit the screen. */}
        <ul className="md:hidden space-y-3" aria-label="Subjects">
          {results.map(({ row, invalid, total, grade }) => (
            <li key={row.id} className="rounded-xl border border-border p-4 space-y-3">
              <div className="flex items-center gap-2">
                <input
                  aria-label="Subject"
                  value={row.subject}
                  placeholder="Subject"
                  onChange={(e) => update(row.id, "subject", e.target.value)}
                  className="input flex-1 min-w-0"
                />
                <button
                  type="button"
                  onClick={() => setRows((rs) => rs.filter((r) => r.id !== row.id))}
                  className="w-10 h-10 shrink-0 body text-text-muted hover:text-danger"
                  aria-label={`Remove ${row.subject}`}
                >
                  ✕
                </button>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <label className="input-group">
                  <span className="input-label">CA (out of {caMax})</span>
                  <input
                    inputMode="decimal"
                    value={row.ca}
                    onChange={(e) => update(row.id, "ca", e.target.value)}
                    className="input text-right"
                  />
                </label>
                <label className="input-group">
                  <span className="input-label">Exam (out of {examMax})</span>
                  <input
                    inputMode="decimal"
                    value={row.exam}
                    onChange={(e) => update(row.id, "exam", e.target.value)}
                    className="input text-right"
                  />
                </label>
              </div>
              <p className="body text-navy min-h-[1.5rem]" aria-live="polite">
                {invalid ? (
                  <span className="text-danger body-sm">Check the scores</span>
                ) : total !== null && grade ? (
                  <>
                    Total <strong>{total.toFixed(0)}%</strong> · <strong>{grade}</strong> · {REMARKS[grade]}
                  </>
                ) : (
                  <span className="body-sm text-text-muted">Enter both scores to see the grade</span>
                )}
              </p>
            </li>
          ))}
        </ul>

        {/* Larger screens: the table. */}
        <div className="hidden md:block overflow-x-auto">
          <table className="report-table w-full">
            <thead>
              <tr>
                <th scope="col">Subject</th>
                <th scope="col" className="num">CA (out of {caMax})</th>
                <th scope="col" className="num">Exam (out of {examMax})</th>
                <th scope="col" className="num">Total %</th>
                <th scope="col">Grade</th>
                <th scope="col">Remark</th>
                <th scope="col"><span className="sr-only">Remove</span></th>
              </tr>
            </thead>
            <tbody>
              {results.map(({ row, invalid, total, grade }) => (
                <tr key={row.id}>
                  <td>
                    <input
                      aria-label="Subject"
                      value={row.subject}
                      onChange={(e) => update(row.id, "subject", e.target.value)}
                      className="input min-w-[150px]"
                    />
                  </td>
                  <td className="num">
                    <input
                      aria-label={`${row.subject} CA score`}
                      inputMode="decimal"
                      value={row.ca}
                      onChange={(e) => update(row.id, "ca", e.target.value)}
                      className="input w-24 text-right"
                    />
                  </td>
                  <td className="num">
                    <input
                      aria-label={`${row.subject} exam score`}
                      inputMode="decimal"
                      value={row.exam}
                      onChange={(e) => update(row.id, "exam", e.target.value)}
                      className="input w-24 text-right"
                    />
                  </td>
                  <td className="num font-semibold">{invalid ? "—" : total !== null ? total.toFixed(0) : ""}</td>
                  <td className="font-semibold">{invalid ? "" : grade}</td>
                  <td>
                    {invalid ? (
                      <span className="text-danger body-sm">Check the scores</span>
                    ) : grade ? (
                      REMARKS[grade]
                    ) : (
                      ""
                    )}
                  </td>
                  <td>
                    <button
                      type="button"
                      onClick={() => setRows((rs) => rs.filter((r) => r.id !== row.id))}
                      className="body-sm text-text-muted hover:text-danger"
                      aria-label={`Remove ${row.subject}`}
                    >
                      ✕
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-4">
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() =>
              setRows((rs) => [...rs, { id: Math.max(0, ...rs.map((r) => r.id)) + 1, subject: "", ca: "", exam: "" }])
            }
          >
            Add a subject
          </button>
          {average !== null && (
            <p className="body text-navy" aria-live="polite">
              Average over {totals.length} subject{totals.length !== 1 ? "s" : ""}:{" "}
              <strong>{average.toFixed(1)}%</strong> ({scoreToGrade(average)}, {REMARKS[scoreToGrade(average)]})
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
