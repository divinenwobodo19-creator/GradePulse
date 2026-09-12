"use client";

import Link from "next/link";

const plans = [
  {
    name: "Free",
    price: "₦0",
    period: "forever",
    description: "Perfect for trying GradePulse with a single class",
    features: [
      "1 teacher account",
      "Up to 30 students",
      "1 school",
      "AI-powered recommendations",
      "Student triage",
      "Score entry",
      "Progress tracking",
      "Offline HTML tool",
    ],
    cta: "Get Started Free",
    ctaStyle: "bg-white text-navy border-2 border-navy hover:bg-navy hover:text-white",
    highlighted: false,
  },
  {
    name: "Starter",
    price: "₦5,000",
    period: "/month",
    description: "For teachers managing multiple classes",
    features: [
      "1 teacher account",
      "Up to 150 students",
      "3 schools",
      "Everything in Free",
      "Multi-class management",
      "Printable reports",
      "Priority support",
      "Data ingestion (CSV/Excel)",
    ],
    cta: "Start Starter Plan",
    ctaStyle: "bg-gold text-navy hover:bg-gold-light",
    highlighted: true,
  },
  {
    name: "School",
    price: "₦15,000",
    period: "/month",
    description: "For schools with multiple teachers",
    features: [
      "Up to 10 teacher accounts",
      "Up to 500 students",
      "Unlimited schools",
      "Everything in Starter",
      "Admin dashboard",
      "School-wide analytics",
      "Bulk student import",
      "Dedicated support",
    ],
    cta: "Contact Us",
    ctaStyle: "bg-navy text-white hover:bg-navy-light",
    highlighted: false,
  },
];

export default function PricingPage() {
  return (
    <div className="min-h-screen bg-white">
      {/* Nav */}
      <nav className="border-b border-border px-6 py-4">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2.5">
            <img src="/logo.png" alt="GradePulse" className="w-8 h-8 rounded-lg" />
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
          Simple, transparent pricing
        </h1>
        <p className="body-lg text-text-secondary max-w-2xl mx-auto">
          Start free. Upgrade when you need more. No hidden fees, no surprises.
        </p>
      </div>

      {/* Plans */}
      <div className="max-w-6xl mx-auto px-6 pb-20">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 items-start">
          {plans.map((plan) => (
            <div
              key={plan.name}
              className={`relative rounded-2xl border-2 p-8 transition-all ${
                plan.highlighted
                  ? "border-gold shadow-elevated scale-[1.02]"
                  : "border-border hover:border-border-strong hover:shadow-card"
              }`}
            >
              {plan.highlighted && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2 badge badge-warning text-xs px-3 py-1">
                  MOST POPULAR
                </div>
              )}

              <h2 className="heading-2 text-navy">{plan.name}</h2>
              <div className="mt-4 flex items-baseline gap-1">
                <span className="text-4xl font-extrabold text-navy">{plan.price}</span>
                <span className="text-text-secondary text-sm">{plan.period}</span>
              </div>
              <p className="mt-2 body-sm text-text-secondary">{plan.description}</p>

              <ul className="mt-6 space-y-3">
                {plan.features.map((feature) => (
                  <li key={feature} className="flex items-start gap-2.5 text-sm">
                    <svg
                      className="w-5 h-5 text-gold shrink-0 mt-0.5"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                      strokeWidth={2}
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                    </svg>
                    <span className="text-text-primary">{feature}</span>
                  </li>
                ))}
              </ul>

              <Link
                href="/signup"
                className={`mt-8 block text-center py-3 rounded-lg font-semibold text-sm transition ${plan.ctaStyle}`}
              >
                {plan.cta}
              </Link>
            </div>
          ))}
        </div>

        {/* FAQ */}
        <div className="mt-20 max-w-2xl mx-auto">
          <h2 className="heading-display text-navy text-center mb-10">
            Frequently Asked Questions
          </h2>
          <div className="space-y-6">
            {[
              {
                q: "Can I switch plans later?",
                a: "Yes. Upgrade or downgrade anytime. Your data is always preserved.",
              },
              {
                q: "Is there a free trial for paid plans?",
                a: "The Free plan is free forever. No trial needed — use it as long as you want.",
              },
              {
                q: "Do you charge for updates or support?",
                a: "No. All updates and support are included in your plan at no extra cost.",
              },
              {
                q: "What payment methods do you accept?",
                a: "Bank transfer, card payments, and USSD. Details provided after signup.",
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
