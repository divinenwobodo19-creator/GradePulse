"use client";

import Link from "next/link";
import { PublicFooter, PublicNav } from "@/components/PublicSite";
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
          <span className="text-ink">{feature}</span>
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
    <div className="site min-h-screen">
      {/* Nav */}
      <PublicNav />

      {/* Header */}
      <div className="text-center py-16 px-6">
        <span className="eyebrow mb-4">Pricing</span>
        <h1 className="text-ink mb-4">
          Start free. Pay per student, per term.
        </h1>
        <p className="text-lg text-ink-soft max-w-2xl mx-auto">
          Try GradePulse with one class for free. When the whole school joins, it pays for the students it has, once a
          term, the way it already sets fees.
        </p>
      </div>

      {/* Price */}
      <div className="max-w-6xl mx-auto px-6 pb-20">
        <div className="grid gap-6 md:grid-cols-2 max-w-4xl mx-auto">
          <div className="rounded-2xl border border-border p-8 text-center">
            <div className="font-serif text-2xl font-semibold text-ink">Free</div>
            <div className="mt-4 text-4xl font-extrabold text-ink">₦0</div>
            <div className="text-ink-soft text-sm mt-1">up to {free} students, about one class</div>
            <FeatureList features={FREE_FEATURES} />
            <Link href="/signup" className="btn-site btn-plain w-full mt-8">
              Start free
            </Link>
          </div>
          <div className="rounded-2xl border-2 border-forest p-8 text-center">
            <div className="font-serif text-2xl font-semibold text-ink">Whole school</div>
            <div className="mt-4 text-4xl font-extrabold text-ink">
              {price?.price_per_student ? `₦${price.price_per_student.toLocaleString()}` : "Contact us"}
            </div>
            {price?.price_per_student ? (
              <div className="text-ink-soft text-sm mt-1">per student, each term</div>
            ) : null}
            <FeatureList features={PAID_FEATURES} />
            <Link href="/signup" className="btn-site btn-gold w-full mt-8">
              Create your school account
            </Link>
          </div>
        </div>

        {/* FAQ */}
        <div className="mt-20 max-w-2xl mx-auto">
          <h2 className="text-ink text-center mb-10">
            Common questions
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
              <div key={faq.q} className="p-5 bg-paper-deep rounded-xl border border-border">
                <h3 className="text-ink">{faq.q}</h3>
                <p className="text-sm text-ink-soft mt-2">{faq.a}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Footer */}
      <PublicFooter />
    </div>
  );
}
