import type { Metadata } from "next";
import Link from "next/link";
import GradeCalculator from "@/components/GradeCalculator";
import { JsonLd, PublicFooter, PublicNav, SITE_URL, WHATSAPP_URL } from "@/components/PublicSite";

export const metadata: Metadata = {
  title: "WAEC grade calculator: CA and exam to A1 to F9",
  description:
    "Free WAEC grade calculator for Nigerian teachers and students. Add continuous assessment (CA) and exam scores, and get the total, the WAEC grade from A1 to F9, the remark and the average across subjects.",
  alternates: { canonical: "/waec-grade-calculator" },
  openGraph: {
    title: "Free WAEC grade calculator: CA + exam to A1 to F9",
    description: "Add CA and exam scores, get the total, the WAEC grade and the remark for every subject.",
    url: "/waec-grade-calculator",
  },
};

const BANDS = [
  ["A1", "75 to 100", "Excellent"],
  ["B2", "70 to 74", "Very good"],
  ["B3", "65 to 69", "Good"],
  ["C4", "60 to 64", "Credit"],
  ["C5", "55 to 59", "Credit"],
  ["C6", "50 to 54", "Credit"],
  ["D7", "45 to 49", "Pass"],
  ["E8", "40 to 44", "Pass"],
  ["F9", "0 to 39", "Fail"],
];

const STRUCTURED_DATA = {
  "@context": "https://schema.org",
  "@type": "WebApplication",
  name: "WAEC grade calculator",
  url: `${SITE_URL}/waec-grade-calculator`,
  applicationCategory: "EducationalApplication",
  operatingSystem: "Web browser",
  offers: { "@type": "Offer", price: "0", priceCurrency: "NGN" },
  publisher: { "@type": "Organization", name: "GradePulse by N-Library" },
};

export default function WaecGradeCalculatorPage() {
  return (
    <div className="site min-h-screen">
      <JsonLd data={STRUCTURED_DATA} />
      <PublicNav />
      <main className="max-w-4xl mx-auto px-6 py-14 space-y-12">
        <header>
          <h1 className="text-ink mb-3">WAEC grade calculator</h1>
          <p className="text-lg text-ink-soft">
            Add each subject&apos;s continuous assessment (CA) and exam score to get the total, the WAEC grade from A1
            to F9 and the remark, plus the average across subjects. Free to use; nothing you type leaves your browser.
          </p>
        </header>

        <GradeCalculator />

        <section>
          <h2 className="text-ink mb-3">How WAEC grades are worked out</h2>
          <p className="body text-ink-soft mb-5">
            Schools add the continuous assessment and the exam to get a total out of 100, then read the grade from the
            bands below. These are the bands most Nigerian secondary schools use for WAEC-style grading. A credit is C6
            or better, and most university admissions ask for five credits, including English and Mathematics.
          </p>
          <table className="report-table w-full max-w-lg">
            <thead>
              <tr>
                <th scope="col">Grade</th>
                <th scope="col" className="num">Total score</th>
                <th scope="col">Remark</th>
              </tr>
            </thead>
            <tbody>
              {BANDS.map(([grade, range, remark]) => (
                <tr key={grade}>
                  <td className="font-semibold">{grade}</td>
                  <td className="num">{range}</td>
                  <td>{remark}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        <section>
          <h2 className="text-ink mb-3">Example</h2>
          <p className="body text-ink-soft">
            A student scores 22 out of 30 in CA and 41 out of 70 in the exam. The total is 22 + 41 = 63, which falls in
            60 to 64: a <strong>C4</strong>, a credit. With a CA of 40 and an exam of 60, a student with 30 and 28 also
            totals 58: a <strong>C5</strong>.
          </p>
        </section>

        <section className="rounded-2xl bg-paper-deep border border-border p-8">
          <h2 className="text-ink mb-2">Grading a whole class every week?</h2>
          <p className="body text-ink-soft mb-5">
            GradePulse does this for every student in every subject, each week, and shows which students need help
            before the exam: below 40% needs help, 40 to 74% is on track, 75% and above is ahead. It is free for up to
            40 students.
          </p>
          <div className="flex flex-wrap gap-3">
            <Link href="/signup" className="btn-site btn-gold">
              Start free
            </Link>
            <Link href="/" className="btn-site btn-plain">
              See how GradePulse works
            </Link>
            <a href={WHATSAPP_URL} className="btn-site btn-plain">
              Ask on WhatsApp
            </a>
          </div>
        </section>
      </main>
      <PublicFooter />
    </div>
  );
}
