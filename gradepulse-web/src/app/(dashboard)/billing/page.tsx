"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { BillingStatus } from "@/lib/types";

const naira = (amount: number) => `₦${amount.toLocaleString()}`;

function formatDate(iso: string | null) {
  return iso ? new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "long", year: "numeric" }) : "";
}

const STATE_TEXT: Record<string, { title: string; tone: string }> = {
  active: { title: "Paid for this term", tone: "badge-success" },
  over_limit: { title: "More students than paid for", tone: "badge-warning" },
  grace: { title: "Term ended: renew soon", tone: "badge-warning" },
  expired: { title: "Free plan", tone: "badge-neutral" },
  unpaid: { title: "Free plan", tone: "badge-neutral" },
  not_configured: { title: "Online payment not set up", tone: "badge-neutral" },
};

function planText(status: BillingStatus): string {
  const free = status.free_students;
  switch (status.state) {
    case "active":
      return `Paid for ${status.paid_students} students until ${formatDate(status.paid_until)}. Printable reports and parent progress sheets are included.`;
    case "over_limit":
      return `Paid for ${status.paid_students} students until ${formatDate(status.paid_until)}, but the school now has ${status.students}. Pay for the extra students before adding more.`;
    case "grace":
      return `The paid term ended on ${formatDate(status.paid_until)}. Everything keeps working until ${formatDate(status.grace_until)}; pay for the new term before then to keep reports and parent progress sheets.`;
    case "expired":
      return `The paid term has ended, so the school is on the free plan: up to ${free} students, without printable reports. Every score is still here. Pay for the new term to switch everything back on.`;
    case "unpaid":
      return `Your school is on the free plan: up to ${free} students, with score sheets, triage and progress. Pay for the term to cover the whole school and print class reports and parent progress sheets.`;
    default:
      return "Online payment has not been set up on this server. Contact GradePulse to pay.";
  }
}

// useSearchParams needs a Suspense boundary to prerender.
export default function BillingPage() {
  return (
    <Suspense>
      <Billing />
    </Suspense>
  );
}

function Billing() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  // Paystack sends the admin back to /billing?reference=...
  const searchParams = useSearchParams();
  const returnedReference = searchParams.get("reference") ?? searchParams.get("trxref");
  const verifiedRef = useRef<string | null>(null);

  const [status, setStatus] = useState<BillingStatus | null>(null);
  const [students, setStudents] = useState("");
  const [receiptEmail, setReceiptEmail] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [paying, setPaying] = useState(false);

  useEffect(() => {
    if (authLoading || user?.role !== "admin") return;
    const controller = new AbortController();

    async function load() {
      try {
        if (returnedReference && verifiedRef.current !== returnedReference) {
          verifiedRef.current = returnedReference;
          const result = await api.verifyPayment(returnedReference);
          setStatus(result);
          setNotice(
            result.payment_status === "success"
              ? "Payment received. Thank you."
              : result.payment_status === "pending"
                ? "Paystack has not confirmed this payment yet. Refresh in a minute."
                : "That payment did not go through. Nothing was charged for this term."
          );
          router.replace("/billing");
          return;
        }
        setStatus(await api.getBilling(controller.signal));
      } catch (err) {
        if (!controller.signal.aborted) setError(err instanceof Error ? err.message : "Could not load billing");
      }
    }

    void load();
    return () => controller.abort();
  }, [authLoading, user?.role, returnedReference, router]);

  if (authLoading) return <div role="status" className="h-48 skeleton" />;

  if (user?.role !== "admin") {
    return (
      <div className="page-shell max-w-3xl">
        <h1 className="heading-display text-navy">Billing</h1>
        <p className="body text-text-secondary">Only your school admin can see and pay for GradePulse.</p>
      </div>
    );
  }

  // A new term covers the whole school; a top-up during a term can be any size.
  const minStudents = status && !status.top_up ? Math.max(1, status.students) : 1;
  const suggested = status?.top_up ? Math.max(1, status.students - status.paid_students) : minStudents;
  const count = Math.max(1, Math.floor(Number(students || suggested)));
  const tooFew = count < minStudents;
  const price = status?.price_per_student ?? 0;
  const state = status ? STATE_TEXT[status.state] : null;

  const handlePay = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setPaying(true);
    try {
      const { authorization_url } = await api.startCheckout(count, receiptEmail.trim() || undefined);
      window.location.assign(authorization_url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start the payment");
      setPaying(false);
    }
  };

  return (
    <div className="page-shell max-w-3xl">
      <div className="page-header">
        <div className="page-header-left">
          <h1 className="heading-display text-navy">Billing</h1>
          <p className="body text-text-secondary">
            GradePulse is paid per student, per term. Payment is made securely through Paystack (card, bank transfer
            or USSD).
          </p>
        </div>
      </div>

      {notice && (
        <div role="status" className="bg-success-light border border-success/20 text-navy px-4 py-3 rounded-lg text-sm">
          {notice}
        </div>
      )}
      {error && (
        <div role="alert" className="bg-danger-light border border-danger/20 text-danger px-4 py-3 rounded-lg text-sm">
          {error}
        </div>
      )}

      {!status ? (
        <div className="h-48 skeleton" />
      ) : (
        <>
          <div className="card">
            <div className="card-body space-y-3">
              <div className="flex items-center justify-between gap-3">
                <h2 className="heading-2 text-navy">This term</h2>
                {state && <span className={`badge ${state.tone}`}>{state.title}</span>}
              </div>
              <p className="body text-text-secondary">{planText(status)}</p>
              <p className="caption text-text-muted">The school has {status.students} students now.</p>
            </div>
          </div>

          {status.configured && (
            <div className="card">
              <div className="card-body">
                <h2 className="heading-2 text-navy mb-1">{status.top_up ? "Add students to this term" : "Pay for a term"}</h2>
                <p className="caption text-text-muted mb-4">
                  {status.top_up
                    ? `${naira(price)} per extra student. They are covered until ${formatDate(status.paid_until)}, when this term ends.`
                    : `${naira(price)} per student, for every student in the school. One payment covers ${status.term_days} days.`}
                </p>
                <form onSubmit={handlePay} className="flex flex-wrap items-end gap-4">
                  <div className="input-group">
                    <label className="input-label" htmlFor="bill-students">Number of students</label>
                    <input
                      id="bill-students"
                      type="number"
                      min={minStudents}
                      step={1}
                      inputMode="numeric"
                      value={students === "" ? String(suggested) : students}
                      onChange={(e) => setStudents(e.target.value)}
                      className="input w-40"
                    />
                  </div>
                  <div className="input-group flex-1 min-w-[220px]">
                    <label className="input-label" htmlFor="bill-email">Receipt email</label>
                    <input
                      id="bill-email"
                      type="email"
                      value={receiptEmail}
                      onChange={(e) => setReceiptEmail(e.target.value)}
                      placeholder={user?.email ?? "bursar@school.ng"}
                      className="input"
                      autoComplete="email"
                    />
                  </div>
                  <div className="pb-2">
                    <div className="caption text-text-muted">Total</div>
                    <div className="heading-2 text-navy">{naira(count * price)}</div>
                  </div>
                  <button type="submit" disabled={paying || tooFew} aria-busy={paying} className="btn btn-primary ml-auto">
                    {paying ? "Opening Paystack..." : "Pay with Paystack"}
                  </button>
                </form>
                {tooFew && (
                  <p role="alert" className="caption text-danger mt-3">
                    A term covers every student in the school: pay for at least {minStudents}.
                  </p>
                )}
              </div>
            </div>
          )}

          {status.payments.length > 0 && (
            <div className="card">
              <div className="card-body">
                <h2 className="heading-2 text-navy mb-3">Payments</h2>
                <table className="report-table">
                  <thead>
                    <tr>
                      <th scope="col">Paid on</th>
                      <th scope="col" className="num">Students</th>
                      <th scope="col" className="num">Amount</th>
                      <th scope="col">Covers until</th>
                      <th scope="col">Reference</th>
                    </tr>
                  </thead>
                  <tbody>
                    {status.payments.map((p) => (
                      <tr key={p.reference}>
                        <td>{formatDate(p.paid_at)}</td>
                        <td className="num">{p.students}</td>
                        <td className="num">{naira(p.amount_naira)}</td>
                        <td>{formatDate(p.period_end)}</td>
                        <td className="font-mono text-xs">{p.reference}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
