import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Pricing: free for 40 students, ₦500 per student per term",
  description:
    "GradePulse is free for up to 40 students. For the whole school it is ₦500 per student per term, with printable class reports and parent progress sheets.",
  alternates: { canonical: "/pricing" },
  openGraph: {
    title: "GradePulse pricing: free for 40 students, ₦500 per student per term",
    description: "Start free with one class. Pay per student, per term for the whole school.",
    url: "/pricing",
  },
};

export default function PricingLayout({ children }: { children: React.ReactNode }) {
  return children;
}
