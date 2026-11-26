"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import ReportCardSheet from "@/components/ReportCardSheet";
import { ApiError, api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatMark, incompleteCards, longDate, parseExamMark } from "@/lib/reportCards";
import { useSubjects } from "@/lib/subjects";
import type { ReportCardsResponse, ReportCommentInput, SchoolClass, Term, TermInput } from "@/lib/types";

type Tab = "exams" | "comments" | "print";

const TERM_NAMES = ["First Term", "Second Term", "Third Term"];

/** "2026/2027" for a date in September 2026 or later, "2025/2026" before. */
function currentSession(today = new Date()): string {
  const y = today.getFullYear();
  return today.getMonth() >= 8 ? `${y}/${y + 1}` : `${y - 1}/${y}`;
}

function emptyTerm(): TermInput {
  return { session: currentSession(), name: TERM_NAMES[0], starts_on: "", ends_on: "", next_term_begins: "", days_opened: 0 };
}

// ── Term set-up (admin) ─────────────────────────────────────────────────────

function TermForm({ initial, onSaved, onCancel, termId }: {
  initial: TermInput;
  termId?: string;
  onSaved: (term: Term) => void;
  onCancel?: () => void;
}) {
  const [form, setForm] = useState<TermInput>(initial);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const set = (key: keyof TermInput, value: string | number) => setForm((f) => ({ ...f, [key]: value }));

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (!form.starts_on || !form.ends_on) return setError("Enter the day the term starts and the day it ends.");
    if (form.ends_on < form.starts_on) return setError("The term must end after it starts.");
    setSaving(true);
    try {
      const body = { ...form, next_term_begins: form.next_term_begins || null, days_opened: Number(form.days_opened) || 0 };
      onSaved(termId ? await api.updateTerm(termId, body) : await api.createTerm(body));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save the term");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={submit} className="grid grid-cols-1 sm:grid-cols-3 gap-4">
      <div className="input-group">
        <label className="input-label" htmlFor="term-session">Session</label>
        <input id="term-session" className="input" value={form.session} maxLength={20} placeholder="2026/2027"
          onChange={(e) => set("session", e.target.value)} required />
      </div>
      <div className="input-group">
        <label className="input-label" htmlFor="term-name">Term</label>
        <select id="term-name" className="input select" value={form.name} onChange={(e) => set("name", e.target.value)}>
          {[...new Set([...TERM_NAMES, form.name])].map((n) => <option key={n} value={n}>{n}</option>)}
        </select>
      </div>
      <div className="input-group">
        <label className="input-label" htmlFor="term-days">Days school opened</label>
        <input id="term-days" type="number" min={0} max={366} className="input" value={form.days_opened ?? 0}
          onChange={(e) => set("days_opened", e.target.value)} />
      </div>
      <div className="input-group">
        <label className="input-label" htmlFor="term-start">Term starts</label>
        <input id="term-start" type="date" className="input" value={form.starts_on}
          onChange={(e) => set("starts_on", e.target.value)} required />
      </div>
      <div className="input-group">
        <label className="input-label" htmlFor="term-end">Term ends</label>
        <input id="term-end" type="date" className="input" value={form.ends_on}
          onChange={(e) => set("ends_on", e.target.value)} required />
      </div>
      <div className="input-group">
        <label className="input-label" htmlFor="term-next">Next term begins</label>
        <input id="term-next" type="date" className="input" value={form.next_term_begins ?? ""}
          onChange={(e) => set("next_term_begins", e.target.value)} />
      </div>
      <p className="caption text-text-muted sm:col-span-3">
        The weekly tests dated between the start and end of the term make up each student&apos;s CA.
      </p>
      {error && <p role="alert" className="caption text-danger sm:col-span-3">{error}</p>}
      <div className="flex gap-3 sm:col-span-3">
        <button type="submit" className="btn btn-primary" disabled={saving}>
          {saving ? "Saving…" : termId ? "Save term" : "Create term"}
        </button>
        {onCancel && <button type="button" className="btn btn-secondary" onClick={onCancel}>Cancel</button>}
      </div>
    </form>
  );
}

// ── Exam scores and subject remarks ─────────────────────────────────────────

function ExamSheet({ data, termId, subjects, subject, onSubject, onSaved, version }: {
  data: ReportCardsResponse;
  termId: string;
  subjects: string[];
  subject: string;
  onSubject: (subject: string) => void;
  onSaved: () => void;
  version: number;
}) {
  // A fresh table (and draft) for each subject and each reload of the cards.
  // The subject itself lives in the page, so it stays put after a save.
  const current = subjects.includes(subject) ? subject : subjects[0] ?? "";
  return <ExamRows key={`${current}-${version}`} data={data} termId={termId} subjects={subjects} subject={current}
    onSubject={onSubject} onSaved={onSaved} />;
}

function ExamRows({ data, termId, subjects, subject, onSubject, onSaved }: {
  data: ReportCardsResponse;
  termId: string;
  subjects: string[];
  subject: string;
  onSubject: (subject: string) => void;
  onSaved: () => void;
}) {
  const rows = useMemo(() => data.cards.map((card) => ({
    card,
    row: card.subjects.find((s) => s.subject === subject) ?? null,
  })), [data, subject]);
  const [draft, setDraft] = useState<Record<string, { mark: string; remark: string }>>(() =>
    Object.fromEntries(rows.map(({ card, row }) => [card.student_id, {
      mark: row?.exam === null || row?.exam === undefined ? "" : String(row.exam),
      remark: row?.teacher_remark ?? "",
    }])));
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const examWeight = data.settings.exam_weight;

  async function save() {
    const exams: { student_id: string; score: number | null }[] = [];
    const remarks: { student_id: string; subject: string; remark: string }[] = [];
    for (const { card, row } of rows) {
      const entry = draft[card.student_id];
      if (!entry) continue;
      const before = row?.exam === null || row?.exam === undefined ? "" : String(row.exam);
      if (entry.mark.trim() !== before) {
        const parsed = parseExamMark(entry.mark, examWeight);
        if (!parsed.ok) return setMessage({ kind: "error", text: `${card.name}: ${parsed.error}.` });
        exams.push({ student_id: card.student_id, score: parsed.score });
      }
      if (entry.remark.trim() !== (row?.teacher_remark ?? "")) {
        remarks.push({ student_id: card.student_id, subject, remark: entry.remark.trim() });
      }
    }
    if (exams.length === 0 && remarks.length === 0) return setMessage({ kind: "ok", text: "Nothing has changed." });
    setSaving(true);
    try {
      if (exams.length) await api.saveExamScores(termId, subject, exams);
      if (remarks.length) await api.saveSubjectRemarks(termId, remarks);
      setMessage({ kind: "ok", text: `Saved ${subject} for ${new Set([...exams, ...remarks].map((e) => e.student_id)).size} students.` });
      onSaved();
    } catch (err) {
      setMessage({ kind: "error", text: err instanceof Error ? err.message : "Could not save" });
    } finally {
      setSaving(false);
    }
  }

  if (examWeight === 0) {
    return <p className="body-sm text-text-muted">Your school counts the CA as the whole mark (Settings, Report cards), so there is no exam to enter.</p>;
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-4">
        <div className="input-group">
          <label className="input-label" htmlFor="exam-subject">Subject</label>
          <select id="exam-subject" className="input select w-auto min-w-[180px]" value={subject}
            onChange={(e) => onSubject(e.target.value)}>
            {subjects.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        <p className="caption text-text-muted">
          Enter each exam mark out of {examWeight}. The CA (out of {data.settings.ca_weight}) comes from this term&apos;s weekly tests.
          Leave a box empty for a student who did not sit the exam.
        </p>
      </div>
      <div className="overflow-x-auto">
        <table className="report-table">
          <thead>
            <tr>
              <th scope="col">Student</th>
              <th scope="col" className="num">Tests</th>
              <th scope="col" className="num">CA ({data.settings.ca_weight})</th>
              <th scope="col" className="num">Exam ({examWeight})</th>
              <th scope="col" className="num">Total</th>
              <th scope="col">Grade</th>
              <th scope="col">Teacher&apos;s remark (optional)</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ card, row }) => (
              <tr key={card.student_id}>
                <th scope="row">{card.name}</th>
                <td className="num">{row?.tests ?? 0}</td>
                <td className="num">{formatMark(row?.ca)}</td>
                <td className="num">
                  <input
                    aria-label={`${card.name} exam mark out of ${examWeight}`}
                    inputMode="decimal"
                    className="input text-right py-1"
                    style={{ width: "5.5rem" }}
                    value={draft[card.student_id]?.mark ?? ""}
                    onChange={(e) => setDraft((d) => ({ ...d, [card.student_id]: { ...d[card.student_id], mark: e.target.value } }))}
                  />
                </td>
                <td className="num font-semibold">{formatMark(row?.total)}</td>
                <td>{row?.grade || "—"}</td>
                <td>
                  <input
                    aria-label={`${card.name} remark in ${subject}`}
                    className="input py-1 min-w-[200px]"
                    maxLength={120}
                    placeholder={row?.grade_remark || ""}
                    value={draft[card.student_id]?.remark ?? ""}
                    onChange={(e) => setDraft((d) => ({ ...d, [card.student_id]: { ...d[card.student_id], remark: e.target.value } }))}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex items-center gap-4">
        <button type="button" className="btn btn-primary" onClick={save} disabled={saving || rows.length === 0}>
          {saving ? "Saving…" : `Save ${subject}`}
        </button>
        {message && (
          <p role={message.kind === "error" ? "alert" : "status"}
            className={`body-sm ${message.kind === "error" ? "text-danger" : "text-success"}`}>{message.text}</p>
        )}
      </div>
    </div>
  );
}

// ── Attendance and comments ─────────────────────────────────────────────────

function CommentsSheet({ data, termId, isAdmin, onSaved }: {
  data: ReportCardsResponse;
  termId: string;
  isAdmin: boolean;
  onSaved: () => void;
}) {
  const [draft, setDraft] = useState<Record<string, { days: string; form: string; principal: string }>>(() =>
    Object.fromEntries(data.cards.map((c) => [c.student_id, {
      days: c.days_present === null ? "" : String(c.days_present),
      form: c.form_teacher_comment,
      principal: c.principal_comment,
    }])));
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const daysOpened = data.term.days_opened;

  async function save() {
    const entries: ReportCommentInput[] = [];
    for (const card of data.cards) {
      const d = draft[card.student_id];
      if (!d) continue;
      const entry: ReportCommentInput = { student_id: card.student_id };
      const before = card.days_present === null ? "" : String(card.days_present);
      if (d.days.trim() !== before) {
        const days = d.days.trim() === "" ? null : Number(d.days);
        if (days !== null && (!Number.isInteger(days) || days < 0 || days > (daysOpened || 366))) {
          return setMessage({ kind: "error", text: `${card.name}: days present must be a whole number from 0 to ${daysOpened || 366}.` });
        }
        entry.days_present = days;
      }
      if (d.form.trim() !== card.form_teacher_comment) entry.form_teacher_comment = d.form.trim();
      if (isAdmin && d.principal.trim() !== card.principal_comment) entry.principal_comment = d.principal.trim();
      if (Object.keys(entry).length > 1) entries.push(entry);
    }
    if (entries.length === 0) return setMessage({ kind: "ok", text: "Nothing has changed." });
    setSaving(true);
    try {
      await api.saveReportComments(termId, entries);
      setMessage({ kind: "ok", text: `Saved for ${entries.length} student${entries.length === 1 ? "" : "s"}.` });
      onSaved();
    } catch (err) {
      setMessage({ kind: "error", text: err instanceof Error ? err.message : "Could not save" });
    } finally {
      setSaving(false);
    }
  }

  const set = (id: string, key: "days" | "form" | "principal", value: string) =>
    setDraft((d) => ({ ...d, [id]: { ...d[id], [key]: value } }));

  return (
    <div className="space-y-4">
      <p className="caption text-text-muted">
        Attendance {daysOpened > 0 ? `out of ${daysOpened} days school opened` : "(set the days school opened on the term)"}, the
        form teacher&apos;s comment{isAdmin ? " and the principal's comment" : ". The principal's comment is added by a school admin"}.
      </p>
      <div className="overflow-x-auto">
        <table className="report-table">
          <thead>
            <tr>
              <th scope="col">Student</th>
              <th scope="col" className="num">Days present</th>
              <th scope="col">Form teacher&apos;s comment</th>
              <th scope="col">Principal&apos;s comment</th>
            </tr>
          </thead>
          <tbody>
            {data.cards.map((card) => (
              <tr key={card.student_id}>
                <th scope="row">{card.name}</th>
                <td className="num">
                  <input aria-label={`${card.name} days present`} inputMode="numeric" className="input text-right py-1" style={{ width: "5.5rem" }}
                    value={draft[card.student_id]?.days ?? ""} onChange={(e) => set(card.student_id, "days", e.target.value)} />
                </td>
                <td>
                  <textarea aria-label={`${card.name} form teacher's comment`} className="input py-1 min-w-[220px]" rows={2}
                    maxLength={300} value={draft[card.student_id]?.form ?? ""}
                    onChange={(e) => set(card.student_id, "form", e.target.value)} />
                </td>
                <td>
                  {isAdmin ? (
                    <textarea aria-label={`${card.name} principal's comment`} className="input py-1 min-w-[220px]" rows={2}
                      maxLength={300} value={draft[card.student_id]?.principal ?? ""}
                      onChange={(e) => set(card.student_id, "principal", e.target.value)} />
                  ) : (
                    <span className="body-sm text-text-secondary">{card.principal_comment || "—"}</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex items-center gap-4">
        <button type="button" className="btn btn-primary" onClick={save} disabled={saving || data.cards.length === 0}>
          {saving ? "Saving…" : "Save comments"}
        </button>
        {message && (
          <p role={message.kind === "error" ? "alert" : "status"}
            className={`body-sm ${message.kind === "error" ? "text-danger" : "text-success"}`}>{message.text}</p>
        )}
      </div>
    </div>
  );
}

// ── The page ────────────────────────────────────────────────────────────────

export default function ReportCardsPage() {
  const { user, loading: authLoading } = useAuth();
  const isAdmin = user?.role === "admin";
  const subjects = useSubjects();
  const [terms, setTerms] = useState<Term[]>([]);
  const [classes, setClasses] = useState<SchoolClass[]>([]);
  const [termId, setTermId] = useState("");
  const [classId, setClassId] = useState("");
  const [data, setData] = useState<ReportCardsResponse | null>(null);
  const [version, setVersion] = useState(0); // bumps on every load, so edit tables start from the saved values
  const [tab, setTab] = useState<Tab>("exams");
  const [examSubject, setExamSubject] = useState("");
  const [termFormOpen, setTermFormOpen] = useState<"new" | "edit" | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [locked, setLocked] = useState("");

  useEffect(() => {
    if (authLoading || !user) return;
    const controller = new AbortController();
    Promise.all([
      api.getTerms(controller.signal),
      user.school_id ? api.getClasses(user.school_id, controller.signal) : Promise.resolve([] as SchoolClass[]),
    ])
      .then(([nextTerms, nextClasses]) => {
        setTerms(nextTerms);
        setClasses(nextClasses);
        setTermId((id) => id || nextTerms[0]?.term_id || "");
        setClassId((id) => id || nextClasses[0]?.class_id || "");
      })
      .catch((err) => {
        if (!(err instanceof Error && err.name === "AbortError")) setError(err instanceof Error ? err.message : "Could not load terms");
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, [authLoading, user]);

  // Bump to re-fetch the cards (after a save).
  const [reloadTick, setReloadTick] = useState(0);
  const reload = useCallback(() => setReloadTick((t) => t + 1), []);

  useEffect(() => {
    if (!termId || !classId) return;
    const controller = new AbortController();
    api.getReportCards(termId, classId, controller.signal)
      .then((next) => {
        setError("");
        setData(next);
        setVersion((v) => v + 1);
      })
      .catch((err) => {
        if (err instanceof ApiError && err.status === 402) setLocked(err.message);
        else if (!(err instanceof Error && err.name === "AbortError")) setError(err instanceof Error ? err.message : "Could not load report cards");
      });
    return () => controller.abort();
  }, [termId, classId, reloadTick]);

  const term = terms.find((t) => t.term_id === termId);
  const incomplete = useMemo(() => (data ? incompleteCards(data.cards) : []), [data]);

  function termSaved(saved: Term) {
    setTerms((list) => {
      const others = list.filter((t) => t.term_id !== saved.term_id);
      return [saved, ...others].sort((a, b) => b.starts_on.localeCompare(a.starts_on));
    });
    setTermId(saved.term_id);
    setTermFormOpen(null);
    reload();
  }

  if (authLoading || loading) {
    return (
      <div role="status" aria-live="polite" className="space-y-6">
        <div className="h-8 w-48 skeleton" />
        <div className="h-16 skeleton" />
        <div className="h-64 skeleton" />
      </div>
    );
  }

  return (
    <div className="page-shell">
      <div className="page-header no-print">
        <div className="page-header-left">
          <h1 className="heading-display text-navy">Report cards</h1>
          <p className="body text-text-secondary">
            End-of-term results: the weekly tests become the CA, add the exam and comments, then print a card for every student
          </p>
        </div>
        {tab === "print" && data && data.cards.length > 0 && !locked && (
          <button type="button" className="btn btn-primary" onClick={() => window.print()}>Print all cards</button>
        )}
      </div>

      {locked && (
        <div className="card">
          <div className="empty-state">
            <h3 className="heading-3 text-navy mb-1">Report cards come with a paid term</h3>
            <p className="body-sm text-text-muted max-w-md mx-auto">{locked}</p>
            {isAdmin && <Link href="/billing" className="btn btn-primary mt-4">Go to Billing</Link>}
          </div>
        </div>
      )}

      {error && (
        <div role="alert" className="no-print bg-danger-light border border-danger/20 text-danger px-4 py-3 rounded-lg text-sm">{error}</div>
      )}

      {!locked && terms.length === 0 && (
        <div className="card no-print">
          <div className="card-body">
            <h2 className="heading-2 text-navy mb-1">Set up the term</h2>
            {isAdmin ? (
              <>
                <p className="body-sm text-text-secondary mb-4">
                  Tell GradePulse when this term runs. Its weekly tests become the CA on each report card.
                </p>
                <TermForm initial={emptyTerm()} onSaved={termSaved} />
              </>
            ) : (
              <p className="body-sm text-text-secondary">Ask your school admin to set up the term in Report cards.</p>
            )}
          </div>
        </div>
      )}

      {!locked && terms.length > 0 && (
        <>
          <div className="card no-print">
            <div className="card-body space-y-4">
              <div className="flex flex-wrap items-end gap-4">
                <div className="input-group">
                  <label className="input-label" htmlFor="rc-term">Term</label>
                  <select id="rc-term" className="input select w-auto min-w-[220px]" value={termId}
                    onChange={(e) => setTermId(e.target.value)}>
                    {terms.map((t) => <option key={t.term_id} value={t.term_id}>{t.name} · {t.session}</option>)}
                  </select>
                </div>
                <div className="input-group">
                  <label className="input-label" htmlFor="rc-class">Class</label>
                  <select id="rc-class" className="input select w-auto min-w-[160px]" value={classId}
                    onChange={(e) => setClassId(e.target.value)}>
                    {classes.length === 0 && <option value="">No classes yet</option>}
                    {classes.map((c) => <option key={c.class_id} value={c.class_id}>{c.label}</option>)}
                  </select>
                </div>
                {isAdmin && (
                  <div className="flex gap-2 ml-auto">
                    <button type="button" className="btn btn-secondary" onClick={() => setTermFormOpen(termFormOpen === "edit" ? null : "edit")}>
                      Edit term
                    </button>
                    <button type="button" className="btn btn-secondary" onClick={() => setTermFormOpen(termFormOpen === "new" ? null : "new")}>
                      New term
                    </button>
                  </div>
                )}
              </div>
              {term && (
                <p className="caption text-text-muted">
                  {longDate(term.starts_on)} to {longDate(term.ends_on)}
                  {term.next_term_begins && ` · next term begins ${longDate(term.next_term_begins)}`}
                  {term.days_opened > 0 && ` · school opened ${term.days_opened} days`}
                </p>
              )}
              {isAdmin && termFormOpen && (
                <div className="border-t border-border pt-4">
                  <TermForm
                    key={`${termFormOpen}-${termId}`}
                    initial={termFormOpen === "edit" && term
                      ? { session: term.session, name: term.name, starts_on: term.starts_on, ends_on: term.ends_on,
                          next_term_begins: term.next_term_begins, days_opened: term.days_opened }
                      : emptyTerm()}
                    termId={termFormOpen === "edit" ? termId : undefined}
                    onSaved={termSaved}
                    onCancel={() => setTermFormOpen(null)}
                  />
                </div>
              )}
            </div>
          </div>

          {classes.length === 0 ? (
            <div className="card"><div className="empty-state">
              <h3 className="heading-3 text-navy mb-1">No classes yet</h3>
              <p className="body-sm text-text-muted">Add classes and students first.</p>
            </div></div>
          ) : data && (
            <>
              <div role="tablist" aria-label="Report card steps" className="flex flex-wrap gap-2 no-print">
                {([["exams", "1. Exam scores & remarks"], ["comments", "2. Attendance & comments"], ["print", "3. Preview & print"]] as const).map(([key, label]) => (
                  <button key={key} type="button" role="tab" aria-selected={tab === key}
                    className={`btn ${tab === key ? "btn-primary" : "btn-secondary"}`} onClick={() => setTab(key)}>
                    {label}
                  </button>
                ))}
              </div>

              {data.cards.length === 0 ? (
                <div className="card"><div className="empty-state">
                  <h3 className="heading-3 text-navy mb-1">No students in {data.class.label}</h3>
                  <p className="body-sm text-text-muted">Add students to this class first.</p>
                </div></div>
              ) : tab === "exams" ? (
                <div className="card no-print"><div className="card-body">
                  <ExamSheet data={data} termId={termId} subjects={subjects} subject={examSubject}
                    onSubject={setExamSubject} onSaved={reload} version={version} />
                </div></div>
              ) : tab === "comments" ? (
                <div className="card no-print"><div className="card-body">
                  <CommentsSheet key={`comments-${version}`} data={data} termId={termId} isAdmin={isAdmin} onSaved={reload} />
                </div></div>
              ) : (
                <>
                  {incomplete.length > 0 && (
                    <div role="status" className="no-print bg-warning-light border border-warning/30 px-4 py-3 rounded-lg body-sm">
                      <strong>{incomplete.length} card{incomplete.length === 1 ? " is" : "s are"} not complete yet.</strong> A
                      subject without both its CA and exam shows no total, and the student is left out of the class position.
                      <ul className="mt-1 list-disc pl-5">
                        {incomplete.slice(0, 8).map((c) => <li key={c.name}>{c.name}: {c.missing.join(", ")}</li>)}
                        {incomplete.length > 8 && <li>and {incomplete.length - 8} more</li>}
                      </ul>
                    </div>
                  )}
                  {data.cards.map((card) => <ReportCardSheet key={card.student_id} data={data} card={card} />)}
                </>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}
