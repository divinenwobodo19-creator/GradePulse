import type { Metadata } from "next";
import Link from "next/link";
import SignedInRedirect from "@/components/SignedInRedirect";
import {
  BrowserFrame, JsonLd, PublicFooter, PublicNav, SITE_URL, WHATSAPP_NUMBER, WHATSAPP_URL,
} from "@/components/PublicSite";

export const metadata: Metadata = {
  title: { absolute: "GradePulse: see every week which students are falling behind" },
  description:
    "GradePulse turns the weekly tests Nigerian secondary schools already give into a clear picture of every class on WAEC grade bands: who needs help, who is on track, who is ahead. Free for up to 40 students.",
  alternates: { canonical: "/" },
  // A page's openGraph replaces the layout's, so it is spelled out in full.
  openGraph: {
    type: "website",
    siteName: "GradePulse",
    locale: "en_NG",
    url: "/",
    title: "GradePulse: see every week which students are falling behind",
    description: "Weekly student performance on WAEC grade bands for Nigerian secondary schools. Free for up to 40 students.",
  },
};

const STEPS = [
  {
    title: "Enter the week's test in one sheet",
    body: "A teacher picks the class and subject and types each student's score, or imports the class list from Excel. A minute or two per class.",
  },
  {
    title: "See who needs help, every week",
    body: "GradePulse groups every class on WAEC grade bands: below 40% needs help, 40 to 74% is on track, 75% and above is ahead. You act while there is still time, not on results day.",
  },
  {
    title: "Follow each student and tell parents",
    body: "Every test is kept with its date, so you see whether a student is climbing or slipping. Print a progress sheet for each parent, with lines for the class teacher and parent to sign.",
  },
];

const FEATURES = [
  ["WAEC grade bands", "A1 to F9, the grades your teachers, students and parents already know."],
  ["Built for big classes", "Made for classes of 40 to 80 students, with every subject your school teaches."],
  ["Teachers see their own classes", "The school admin invites each teacher and gives them their classes; the admin sees the whole school."],
  ["Excel and CSV import", "Bring in a class list in one go, checked before anything is saved."],
  ["Runs in the web browser", "Works on the school's laptops and desktops. Nothing to install."],
  ["Your data stays yours", "Each school sees only its own data. Written for Nigeria's Data Protection Act 2023."],
];

const FAQS = [
  {
    q: "What does GradePulse cost?",
    a: "It is free for up to 40 students, about one class. For the whole school it is ₦500 per student per term, which adds printable class reports and parent progress sheets. Many schools add it to fees as a results fee.",
  },
  {
    q: "Do we need to install anything?",
    a: "No. GradePulse runs in the web browser on your school's computers. Teachers sign in with their email and password.",
  },
  {
    q: "How long does it take to set up?",
    a: "Most schools can start the same day: create the school account, import or type the class lists, invite the teachers and enter the first week's test.",
  },
  {
    q: "Who can see our students' data?",
    a: "Only your school's staff. Each teacher sees the classes they teach, and no other school can see anything of yours. We never sell data or use it for advertising.",
  },
  {
    q: "Can we see it before deciding?",
    a: `Yes. Message us on WhatsApp at ${WHATSAPP_NUMBER} for a free demo, or create an account and try it with one class.`,
  },
];

const STRUCTURED_DATA = [
  {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: "GradePulse",
    url: SITE_URL,
    applicationCategory: "EducationalApplication",
    operatingSystem: "Web browser",
    description: "Weekly student performance tracking on WAEC grade bands for Nigerian secondary schools.",
    offers: [
      { "@type": "Offer", name: "Free plan, up to 40 students", price: "0", priceCurrency: "NGN" },
      { "@type": "Offer", name: "Whole school, per student per term", price: "500", priceCurrency: "NGN" },
    ],
    publisher: {
      "@type": "Organization",
      name: "N-Library",
      address: { "@type": "PostalAddress", addressLocality: "Enugu", addressCountry: "NG" },
    },
  },
  {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: FAQS.map((f) => ({ "@type": "Question", name: f.q, acceptedAnswer: { "@type": "Answer", text: f.a } })),
  },
];

export default function Home() {
  return (
    <div className="min-h-screen bg-white">
      <SignedInRedirect />
      <JsonLd data={STRUCTURED_DATA} />
      <PublicNav />

      <main>
        {/* Hero */}
        <section className="px-6 pt-16 pb-14 bg-surface-elevated">
          <div className="max-w-6xl mx-auto grid gap-12 lg:grid-cols-[1fr_1.15fr] items-center">
            <div>
              <span className="badge badge-neutral mb-4">For Nigerian secondary schools</span>
              <h1 className="heading-display text-navy mb-5">See every week which students are falling behind</h1>
              <p className="body-lg text-text-secondary mb-8">
                Don&apos;t wait for exam results. GradePulse turns the weekly tests your teachers already give into a
                clear picture of every class, on WAEC grade bands: who needs help, who is on track and who is ahead.
              </p>
              <div className="flex flex-wrap gap-3">
                <Link href="/signup" className="btn btn-primary btn-lg">
                  Start free
                </Link>
                <a href={WHATSAPP_URL} className="btn btn-secondary btn-lg">
                  Book a free demo on WhatsApp
                </a>
              </div>
              <p className="body-sm text-text-muted mt-4">
                Free for up to 40 students. Runs in the web browser on your school&apos;s computers.
              </p>
            </div>
            <BrowserFrame
              src="/screens/dashboard.webp"
              alt="The GradePulse dashboard for a sample school: 9 students need help in Mathematics, 37 are on track and 14 are ahead"
              width={1600}
              height={1064}
              priority
            />
          </div>
        </section>

        {/* Problem */}
        <section className="px-6 py-16">
          <div className="max-w-3xl mx-auto text-center">
            <h2 className="heading-1 text-navy mb-4">Most schools find out a student is failing on results day</h2>
            <p className="body-lg text-text-secondary">
              By then the term is over. Teachers already give weekly tests, but the scores sit in exercise books and
              registers, and nobody has time to add them up class by class. GradePulse does that every week, so extra
              help reaches a student while it can still change the result.
            </p>
          </div>
        </section>

        {/* How it works */}
        <section className="px-6 py-16 bg-surface-elevated" id="how-it-works">
          <div className="max-w-6xl mx-auto">
            <h2 className="heading-1 text-navy text-center mb-12">How it works</h2>
            <ol className="grid gap-8 md:grid-cols-3">
              {STEPS.map((step, i) => (
                <li key={step.title} className="card">
                  <div className="card-body">
                    <div className="w-9 h-9 rounded-full bg-gold text-navy font-bold flex items-center justify-center mb-4">
                      {i + 1}
                    </div>
                    <h3 className="heading-3 text-navy mb-2">{step.title}</h3>
                    <p className="body-sm text-text-secondary">{step.body}</p>
                  </div>
                </li>
              ))}
            </ol>
            <div className="grid gap-8 lg:grid-cols-2 mt-12 items-start">
              <figure>
                <BrowserFrame
                  src="/screens/progress.webp"
                  alt="A sample student's Mathematics results rising from 32% to 62% over six weekly tests"
                  width={900}
                  height={1007}
                />
                <figcaption className="caption text-text-muted mt-2 text-center">
                  Every test, every subject, with its grade
                </figcaption>
              </figure>
              <figure>
                <BrowserFrame
                  src="/screens/parent-sheet.webp"
                  alt="A printable parent progress sheet showing each subject's latest score, average and WAEC grade"
                  width={1100}
                  height={484}
                />
                <figcaption className="caption text-text-muted mt-2 text-center">
                  A progress sheet for every parent, ready to print
                </figcaption>
              </figure>
            </div>
          </div>
        </section>

        {/* Features */}
        <section className="px-6 py-16">
          <div className="max-w-6xl mx-auto">
            <h2 className="heading-1 text-navy text-center mb-12">Built for how Nigerian schools work</h2>
            <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
              {FEATURES.map(([title, body]) => (
                <div key={title} className="p-5 rounded-xl border border-border">
                  <h3 className="heading-3 text-navy mb-1.5">{title}</h3>
                  <p className="body-sm text-text-secondary">{body}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Pricing teaser */}
        <section className="px-6 py-16 bg-surface-elevated">
          <div className="max-w-4xl mx-auto grid gap-6 md:grid-cols-2">
            <div className="rounded-2xl border border-border bg-white p-8">
              <h2 className="heading-2 text-navy">Free</h2>
              <p className="text-3xl font-extrabold text-navy mt-2">₦0</p>
              <p className="body-sm text-text-secondary mt-2">
                Up to 40 students, about one class: score sheets, weekly grouping and student progress.
              </p>
            </div>
            <div className="rounded-2xl border-2 border-gold bg-white p-8">
              <h2 className="heading-2 text-navy">Whole school</h2>
              <p className="text-3xl font-extrabold text-navy mt-2">
                ₦500 <span className="body-sm font-normal text-text-secondary">per student, per term</span>
              </p>
              <p className="body-sm text-text-secondary mt-2">
                Every student, plus printable class reports and a progress sheet for every parent.
              </p>
            </div>
          </div>
          <p className="text-center mt-6">
            <Link href="/pricing" className="font-semibold text-gold-dark hover:underline">
              See pricing and common questions
            </Link>
          </p>
        </section>

        {/* FAQ */}
        <section className="px-6 py-16">
          <div className="max-w-2xl mx-auto">
            <h2 className="heading-1 text-navy text-center mb-10">Questions school owners ask</h2>
            <div className="space-y-4">
              {FAQS.map((faq) => (
                <details key={faq.q} className="p-5 rounded-xl border border-border bg-surface-elevated">
                  <summary className="heading-3 text-navy cursor-pointer">{faq.q}</summary>
                  <p className="body-sm text-text-secondary mt-2">{faq.a}</p>
                </details>
              ))}
            </div>
          </div>
        </section>

        {/* Closing call to action */}
        <section className="px-6 py-16 bg-navy text-white text-center">
          <h2 className="heading-1 mb-3">See GradePulse with your own classes</h2>
          <p className="body-lg text-white/75 mb-8 max-w-xl mx-auto">
            Book a free demo for your school in Enugu or anywhere in Nigeria.
          </p>
          <div className="flex flex-wrap justify-center gap-3">
            <a href={WHATSAPP_URL} className="btn btn-primary btn-lg">
              WhatsApp {WHATSAPP_NUMBER}
            </a>
            <Link href="/signup" className="btn btn-lg bg-white/10 text-white hover:bg-white/20">
              Start free
            </Link>
          </div>
        </section>
      </main>

      <PublicFooter />
    </div>
  );
}
