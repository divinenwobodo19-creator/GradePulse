"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { IngestResult } from "@/lib/types";

const TEMPLATE_CSV =
  "student_id,name,class_label\n" +
  "ADM001,Adebayo Olawale,JSS1A\n" +
  "ADM002,Chidinma Eze,JSS1A\n";
const TEMPLATE_HREF = `data:text/csv;charset=utf-8,${encodeURIComponent(TEMPLATE_CSV)}`;
const MAX_MESSAGES = 8;

function MessageList({ title, tone, items }: { title: string; tone: string; items: string[] }) {
  if (items.length === 0) return null;
  return (
    <div>
      <div className={`caption font-semibold ${tone}`}>
        {title} ({items.length})
      </div>
      <ul className="mt-1 space-y-0.5 caption text-text-secondary list-disc pl-5">
        {items.slice(0, MAX_MESSAGES).map((item, i) => (
          <li key={i}>{item}</li>
        ))}
        {items.length > MAX_MESSAGES && <li>and {items.length - MAX_MESSAGES} more</li>}
      </ul>
    </div>
  );
}

// Two steps so nothing is saved by surprise: check the file, then import it.
export default function RosterImportDialog({ onClose, onImported }: {
  onClose: () => void;
  onImported: (studentCount: number) => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [checked, setChecked] = useState<IngestResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !busy) onClose();
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [busy, onClose]);

  const run = async (dryRun: boolean) => {
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      const result = await api.importRoster(file, dryRun);
      if (dryRun) setChecked(result);
      else onImported(result.report.stats.students_valid ?? 0);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not read that file");
    } finally {
      setBusy(false);
    }
  };

  const stats = checked?.report.stats;
  const valid = stats?.students_valid ?? 0;

  return (
    <div className="modal-overlay" onClick={() => !busy && onClose()}>
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="import-roster-title"
        className="modal-content"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="px-6 py-5 border-b border-border">
          <h2 id="import-roster-title" className="heading-2 text-navy">Import a Class List</h2>
          <p className="caption text-text-muted mt-1">
            A CSV or Excel file with one student per row. It needs <strong>student_id</strong> and{" "}
            <strong>name</strong> columns; <strong>class_label</strong> puts each student in a class and creates
            the class if it is new.{" "}
            <a href={TEMPLATE_HREF} download="gradepulse-class-list.csv" className="text-gold font-semibold">
              Download a template
            </a>
          </p>
        </div>

        <div className="px-6 py-5 space-y-4">
          <div className="input-group">
            <label className="input-label" htmlFor="roster-file">File</label>
            <input
              id="roster-file"
              type="file"
              accept=".csv,.xlsx,.xls"
              onChange={(e) => {
                setFile(e.target.files?.[0] ?? null);
                setChecked(null);
                setError("");
              }}
              className="input"
            />
          </div>

          {error && (
            <div role="alert" className="bg-danger-light border border-danger/20 text-danger px-4 py-3 rounded-lg text-sm">
              {error}
            </div>
          )}

          {checked && stats && (
            <div role="status" className="p-4 bg-surface-elevated rounded-xl space-y-3">
              <p className="body-sm text-navy">
                <strong>{valid}</strong> of {stats.students_read ?? 0} rows are ready to import
                {(stats.students_skipped ?? 0) > 0 && <>, {stats.students_skipped} will be skipped</>}.
              </p>
              <MessageList title="Problems" tone="text-danger" items={checked.report.errors} />
              <MessageList title="Notes" tone="text-text-secondary" items={checked.report.warnings} />
            </div>
          )}

          <div className="flex justify-end gap-3 pt-2">
            <button type="button" onClick={onClose} disabled={busy} className="btn btn-ghost">
              Cancel
            </button>
            {checked && valid > 0 ? (
              <button type="button" onClick={() => run(false)} disabled={busy} aria-busy={busy} className="btn btn-primary">
                {busy ? "Importing..." : `Import ${valid} Student${valid !== 1 ? "s" : ""}`}
              </button>
            ) : (
              <button type="button" onClick={() => run(true)} disabled={busy || !file} aria-busy={busy} className="btn btn-primary">
                {busy ? "Checking..." : "Check File"}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
