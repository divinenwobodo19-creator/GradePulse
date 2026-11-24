"use client";

// Settings → Report cards (admins): the CA/exam split, grading scale,
// positions, and the school details printed at the top of every card.
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { WAEC_SCALE } from "@/lib/reportCards";
import type { GradeBand, ReportSettings } from "@/lib/types";

export default function ReportSettingsCard() {
  const [settings, setSettings] = useState<ReportSettings | null>(null);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ kind: "ok" | "error"; text: string } | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    api.getReportSettings(controller.signal)
      .then(setSettings)
      .catch((err) => {
        if (!(err instanceof Error && err.name === "AbortError")) {
          setMessage({ kind: "error", text: err instanceof Error ? err.message : "Could not load report settings" });
        }
      });
    return () => controller.abort();
  }, []);

  if (!settings) {
    return (
      <div className="card"><div className="card-body">
        <h2 className="heading-2 text-navy">Report cards</h2>
        {message ? <p className="caption text-danger">{message.text}</p> : <div className="h-24 skeleton mt-3" />}
      </div></div>
    );
  }

  const update = (changes: Partial<ReportSettings>) => setSettings((s) => (s ? { ...s, ...changes } : s));
  const setBand = (i: number, changes: Partial<GradeBand>) =>
    update({ grade_scale: settings.grade_scale.map((b, j) => (j === i ? { ...b, ...changes } : b)) });

  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!settings) return;
    setSaving(true);
    setMessage(null);
    try {
      const saved = await api.saveReportSettings({
        ...settings,
        ca_weight: Number(settings.ca_weight),
        grade_scale: settings.grade_scale.map((b) => ({ ...b, grade: b.grade.trim(), min: Number(b.min) })),
      });
      setSettings(saved);
      setMessage({ kind: "ok", text: "Report card settings saved." });
    } catch (err) {
      setMessage({ kind: "error", text: err instanceof Error ? err.message : "Could not save" });
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="card">
      <div className="card-body">
        <div className="mb-4">
          <h2 className="heading-2 text-navy">Report cards</h2>
          <p className="caption text-text-muted">
            How end-of-term totals are worked out and graded, and the school details printed on every card.
          </p>
        </div>

        <form onSubmit={save} className="space-y-5">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="input-group">
              <label className="input-label" htmlFor="rs-ca">CA share of the total</label>
              <div className="flex items-center gap-2">
                <input id="rs-ca" type="number" min={0} max={100} className="input w-24" value={settings.ca_weight}
                  onChange={(e) => update({ ca_weight: Number(e.target.value) })} required />
                <span className="body-sm text-text-secondary">CA + {100 - (Number(settings.ca_weight) || 0)} exam = 100</span>
              </div>
            </div>
            <label className="flex items-center gap-2 body-sm self-end pb-2">
              <input type="checkbox" checked={settings.show_positions}
                onChange={(e) => update({ show_positions: e.target.checked })} />
              Show class positions (1st, 2nd, 3rd…) on report cards
            </label>
            <div className="input-group sm:col-span-2">
              <label className="input-label" htmlFor="rs-address">School address</label>
              <input id="rs-address" className="input" maxLength={300} value={settings.address}
                placeholder="e.g. 12 Ogui Road, Enugu" onChange={(e) => update({ address: e.target.value })} />
            </div>
            <div className="input-group">
              <label className="input-label" htmlFor="rs-principal">Principal&apos;s name</label>
              <input id="rs-principal" className="input" maxLength={120} value={settings.principal_name}
                placeholder="e.g. Mrs N. Okafor" onChange={(e) => update({ principal_name: e.target.value })} />
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="input-label">Grading scale</span>
              <button type="button" className="btn btn-secondary btn-sm" onClick={() => update({ grade_scale: WAEC_SCALE })}>
                Reset to WAEC
              </button>
            </div>
            <table className="report-table">
              <thead>
                <tr>
                  <th scope="col">Grade</th>
                  <th scope="col" className="num">From (total)</th>
                  <th scope="col">Remark</th>
                  <th scope="col"><span className="sr-only">Remove</span></th>
                </tr>
              </thead>
              <tbody>
                {settings.grade_scale.map((band, i) => (
                  <tr key={i}>
                    <td><input aria-label={`Grade ${i + 1} name`} className="input py-1 w-20" maxLength={4} value={band.grade}
                      onChange={(e) => setBand(i, { grade: e.target.value })} required /></td>
                    <td className="num"><input aria-label={`Grade ${i + 1} lowest total`} type="number" min={0} max={100} step="any"
                      className="input py-1 w-20 text-right" value={band.min}
                      onChange={(e) => setBand(i, { min: Number(e.target.value) })} required /></td>
                    <td><input aria-label={`Grade ${i + 1} remark`} className="input py-1" maxLength={30} value={band.remark}
                      onChange={(e) => setBand(i, { remark: e.target.value })} /></td>
                    <td>
                      {settings.grade_scale.length > 2 && (
                        <button type="button" aria-label={`Remove grade ${band.grade || i + 1}`}
                          className="text-text-muted hover:text-danger"
                          onClick={() => update({ grade_scale: settings.grade_scale.filter((_, j) => j !== i) })}>×</button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="flex items-center justify-between mt-2">
              <p className="caption text-text-muted">A total gets the highest grade it reaches. One grade must start at 0.</p>
              {settings.grade_scale.length < 15 && (
                <button type="button" className="btn btn-secondary btn-sm"
                  onClick={() => update({ grade_scale: [...settings.grade_scale, { grade: "", min: 0, remark: "" }] })}>
                  Add grade
                </button>
              )}
            </div>
          </div>

          <div className="flex items-center gap-4">
            <button type="submit" className="btn btn-primary" disabled={saving}>{saving ? "Saving…" : "Save report card settings"}</button>
            {message && (
              <p role={message.kind === "error" ? "alert" : "status"}
                className={`body-sm ${message.kind === "error" ? "text-danger" : "text-success"}`}>{message.text}</p>
            )}
          </div>
        </form>
      </div>
    </div>
  );
}
