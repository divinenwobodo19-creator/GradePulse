import type { Metadata } from "next";
import Link from "next/link";
import { JsonLd, PublicFooter, PublicNav, SITE_URL } from "@/components/PublicSite";

const TITLE = "How to spot students who are falling behind before exams";
const PUBLISHED = "2026-10-19";

export const metadata: Metadata = {
  title: TITLE,
  description:
    "A practical guide for Nigerian secondary school teachers and principals: use the weekly tests you already give to find struggling students early, act within the week, and keep parents informed.",
  alternates: { canonical: "/guides/spot-struggling-students" },
  openGraph: {
    type: "article",
    title: TITLE,
    description: "Use the weekly tests you already give to find struggling students early and act within the week.",
    url: "/guides/spot-struggling-students",
  },
};

const STRUCTURED_DATA = {
  "@context": "https://schema.org",
  "@type": "Article",
  headline: TITLE,
  datePublished: PUBLISHED,
  author: { "@type": "Organization", name: "GradePulse by N-Library" },
  publisher: { "@type": "Organization", name: "N-Library" },
  mainEntityOfPage: `${SITE_URL}/guides/spot-struggling-students`,
};

export default function SpotStrugglingStudentsGuide() {
  return (
    <div className="site min-h-screen">
      <JsonLd data={STRUCTURED_DATA} />
      <PublicNav />
      <main className="max-w-3xl mx-auto px-6 py-14">
        <article className="space-y-5 text-lg text-ink-soft [&_strong]:text-ink">
          <header>
            <p className="caption text-ink-muted mb-2">Guide · 19 October 2026 · 5-minute read</p>
            <h1 className="text-ink">{TITLE}</h1>
          </header>

          <p className="text-lg">
            Most schools learn that a student is failing when the term&apos;s results come out. By then the chance to
            help has passed. The good news is that your teachers already collect what you need: the weekly tests and
            class exercises. The trick is to look at them every week, not once a term.
          </p>

          <h2 className="text-ink pt-6">1. Use the tests you already give</h2>
          <p>
            You do not need new exams. A short weekly test in each subject, marked out of any total, is enough. Turn
            each score into a percentage so that a test out of 10 and a test out of 40 can be compared.
          </p>

          <h2 className="text-ink pt-6">2. Sort every class into three groups</h2>
          <p>Use the WAEC grade bands your teachers and parents already understand:</p>
          <ul className="list-disc pl-5 space-y-1">
            <li><strong>Needs help:</strong> below 40% (F9).</li>
            <li><strong>On track:</strong> 40% to 74% (E8 to B2).</li>
            <li><strong>Ahead:</strong> 75% and above (A1).</li>
          </ul>
          <p>
            Three groups are enough to act on. A class of 60 becomes, for example, eight students who need help this
            week, not 60 numbers in a register.
          </p>

          <h2 className="text-ink pt-6">3. Watch the direction, not just the average</h2>
          <p>
            A student averaging 55% who scored 68, 60, 52 and 41 in the last four tests is in more danger than one
            averaging 45% who has gone from 32 to 58. Look at each student&apos;s last few results in order. A steady
            fall over three weeks is the earliest warning you will get.
          </p>

          <h2 className="text-ink pt-6">4. Act within the week</h2>
          <p>Once you know who needs help, keep the response small and fast:</p>
          <ul className="list-disc pl-5 space-y-1">
            <li>Give the &quot;needs help&quot; group easier practice on the same topic before moving on.</li>
            <li>Pair a struggling student with one who is ahead for a short weekly session.</li>
            <li>Ask the subject teacher to check that group&apos;s work first in the next lesson.</li>
            <li>Look again after next week&apos;s test: did they move up a group?</li>
          </ul>

          <h2 className="text-ink pt-6">5. Tell parents early</h2>
          <p>
            Parents can help at home only if they know in time. A one-page progress sheet in the middle of the term,
            showing each subject&apos;s latest score, average and grade, starts that conversation weeks before the
            report card. Ask the class teacher and the parent to sign it.
          </p>

          <h2 className="text-ink pt-6">6. Keep it simple enough to keep doing</h2>
          <p>
            The method only works if it happens every week. A spreadsheet can do it for one class; for a whole school
            the adding up and sorting takes hours. That is the job{" "}
            <Link href="/" className="text-forest font-semibold hover:underline">GradePulse</Link> does: teachers
            enter the week&apos;s test in one sheet, and every class is sorted into the three groups automatically,
            with each student&apos;s history and a parent progress sheet ready to print. It is free for up to 40
            students. To work out a single student&apos;s grades, try our free{" "}
            <Link href="/waec-grade-calculator" className="text-forest font-semibold hover:underline">
              WAEC grade calculator
            </Link>
            .
          </p>
        </article>
      </main>
      <PublicFooter />
    </div>
  );
}
