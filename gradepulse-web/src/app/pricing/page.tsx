"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { BillingPrice } from "@/lib/types";

const FREE_FEATURES = [
  "Every teacher and admin account the school needs",
  "Weekly tiers by subject and class on WAEC grade bands",
  "Score sheets, student test history and progress",
  "Class list import from Excel or CSV",
  "Each school\u2019s data private to its own staff",
];

const PAID_FEATURES = [
  "Every student in the school",
  "Printable class reports",
  "A progress sheet for every student to send home to parents",
  "Everything in the free plan",
];

function FeatureList({ features }: { features: string[] }) {
  return (
    <ul className="mt-6 space-y-3 text-left">
      {features.map((feature) => (
        <li key={feature} className="flex items-start gap-2.5 text-sm">
          <svg className="w-5 h-5 text-gold shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
          </svg>
          <span className="text-text-primary">{feature}</span>
        </li>
      ))}
    </ul>
  );
}

export default function PricingPage() {
  const [price, setPrice] = useState<BillingPrice | null>(null);
  const free = price?.free_students ?? 40;

  useEffect(() => {
    const controller = new AbortController();
    api.getBillingPrice(controller.signal).then(setPrice).catch(() => undefined);
    return () => controller.abort();
  }, []);

  return (
    <div className="min-h-screen bg-white">
      {/* Nav */}
      <nav className="border-b border-border px-6 py-4">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2.5">
            <Image src="/logo.png" alt="GradePulse" width={32} height={32} className="w-8 h-8 rounded-lg" />
            <span className="text-lg font-bold text-navy">GradePulse</span>
          </Link>
          <div className="flex items-center gap-4">
            <Link href="/login" className="body-sm text-text-secondary hover:text-navy transition-colors">
              Sign In
            </Link>
            <Link href="/signup" className="btn btn-primary btn-sm">
              Get Started
            </Link>
          </div>
        </div>
      </nav>

      {/* Header */}
      <div className="text-center py-16 px-6">
        <span className="badge badge-neutral mb-4">Pricing</span>
        <h1 className="heading-display text-navy mb-4">
          Start free. Pay per student, per term.
        </h1>
        <p className="body-lg text-text-secondary max-w-2xl mx-auto">
          Try GradePulse with one class for free. When the whole school joins, it pays for the students it has, once a
          term, the way it already sets fees.
        </p>
      </div>

      {/* Price */}
      <div className="max-w-6xl mx-auto px-6 pb-20">
        <div className="grid gap-6 md:grid-cols-2 max-w-4xl mx-auto">
          <div className="rounded-2xl border border-border p-8 text-center">
            <div className="heading-2 text-navy">Free</div>
            <div className="mt-4 text-4xl font-extrabold text-navy">₦0</div>
            <div className="text-text-secondary text-sm mt-1">up to {free} students, about one class</div>
            <FeatureList features={FREE_FEATURES} />
            <Link href="/signup" className="btn btn-secondary w-full mt-8">
              Start free
            </Link>
          </div>
          <div className="rounded-2xl border-2 border-gold p-8 text-center shadow-elevated">
            <div className="heading-2 text-navy">Whole school</div>
            <div className="mt-4 text-4xl font-extrabold text-navy">
              {price?.price_per_student ? `₦${price.price_per_student.toLocaleString()}` : "Contact us"}
            </div>
            {price?.price_per_student ? (
              <div className="text-text-secondary text-sm mt-1">per student, each term</div>
            ) : null}
            <FeatureList features={PAID_FEATURES} />
            <Link href="/signup" className="btn btn-primary w-full mt-8">
              Create your school account
            </Link>
          </div>
        </div>

        {/* FAQ */}
        <div className="mt-20 max-w-2xl mx-auto">
          <h2 className="heading-display text-navy text-center mb-10">
            Frequently Asked Questions
          </h2>
          <div className="space-y-6">
            {[
              {
                q: "How is the number of students counted?",
                a: "The school admin pays for the students on the school's roster for the term. If more join during the term, the admin pays for the extra students for the rest of that term.",
              },
              {
                q: "Can we try it before paying?",
                a: `Yes. The free plan covers up to ${free} students with no time limit, so you can run a class on it for as long as you like.`,
              },
              {
                q: "What happens if we don't renew?",
                a: "The paid plan keeps working for 14 days after the term ends. After that the school is back on the free plan: nothing is deleted and every score stays visible, but reports wait until the next payment, and so do new scores if the school has more students than the free plan covers.",
              },
              {
                q: "Do you charge for updates or support?",
                a: "No. All updates and support are included in your plan at no extra cost.",
              },
              {
                q: "What payment methods do you accept?",
                a: "Card, bank transfer and USSD, through Paystack. The school admin pays from the Billing page.",
              },
            ].map((faq) => (
              <div key={faq.q} className="p-5 bg-surface-elevated rounded-xl border border-border">
                <h3 className="heading-3 text-navy">{faq.q}</h3>
                <p className="body-sm text-text-secondary mt-2">{faq.a}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Footer */}
      <footer className="border-t border-border py-8 px-6 text-center">
        <p className="body-sm text-text-muted">&copy; 2026 GradePulse. All rights reserved.</p>
      </footer>
    </div>
  );
}
