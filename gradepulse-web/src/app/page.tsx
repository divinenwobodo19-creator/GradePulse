import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import SignedInRedirect from "@/components/SignedInRedirect";
import { JsonLd, PublicFooter, PublicNav, Screenshot, SITE_URL, WHATSAPP_NUMBER, WHATSAPP_URL } from "@/components/PublicSite";

export const metadata: Metadata = {
  title: { absolute: "GradePulse: see every week which students need help" },
  description:
    "GradePulse turns the weekly tests Nigerian secondary schools already give into a clear picture of every class on WAEC grade bands: who needs help, who is on track and who is ahead. Free for up to 40 students.",
  alternates: { canonical: "/" },
  // A page's openGraph replaces the layout's, so it is spelled out in full.
  openGraph: {
    type: "website",
    siteName: "GradePulse",
    locale: "en_NG",
    url: "/",
    title: "GradePulse: see every week which students need help",
    description: "Weekly student progress on WAEC grade bands for Nigerian secondary schools. Free for up to 40 students.",
  },
};

const STEPS = [
  {
    title: "Teachers enter the week's test",
    body: "Pick the class and the subject, then type each student's score into one sheet. A class of 60 takes a few minutes, and a class list can come straight from Excel.",
    image: { src: "/screens/score-sheet.webp", width: 1100, height: 924, alt: "The GradePulse score sheet for a sample JSS2A Mathematics class, with this week's scores typed in" },
  },
  {
    title: "You see who needs help in every class",
    body: "GradePulse sorts each class on WAEC grade bands. Below 40% needs help, 40 to 74% is on track, 75% and above is ahead. The list is ready on Monday morning, with weeks of term still left to act.",
    image: { src: "/screens/dashboard.webp", width: 1600, height: 1064, alt: "The GradePulse dashboard for a sample school: 9 students need help in Mathematics, 37 are on track and 14 are ahead" },
  },
  {
    title: "Parents get a progress sheet they can read",
    body: "Each student's latest score, average and grade in every subject, on one printed page with lines for the class teacher and the parent to sign.",
    image: { src: "/screens/parent-sheet.webp", width: 1100, height: 484, alt: "A printable parent progress sheet showing each subject's latest score, average and WAEC grade" },
  },
];

const BENEFITS = [
  ["WAEC grade bands", "A1 to F9, the grades your teachers, students and parents already use."],
  ["Made for big classes", "Classes of 40 to 80 students, with every subject your school teaches."],
  ["Each teacher sees their own classes", "The school admin invites teachers and gives them their classes. The admin sees the whole school."],
  ["Class lists from Excel", "Import a list in one go. GradePulse checks it before anything is saved."],
  ["Runs in the web browser", "Use it on the school's laptops and desktops, with nothing to install."],
  ["Your school's data stays private", "Only your own staff can see it. Written for Nigeria's Data Protection Act 2023."],
];

const FAQS = [
  {
    q: "What does GradePulse cost?",
    a: "It is free for up to 40 students, about one class. For the whole school it is ₦500 per student per term, which adds printable class reports and a progress sheet for every parent. Many schools include it in fees as a results fee.",
  },
  {
    q: "Do we need to install anything?",
    a: "No. GradePulse runs in the web browser on your school's computers. Teachers sign in with their email address and a password.",
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
    q: "What happens if we stop paying?",
    a: "Nothing is deleted. A paid term keeps working for 14 days after it ends, then the school returns to the free plan: every score stays visible, and printing reports waits until the next payment.",
  },
  {
    q: "Can we see it before deciding?",
    a: `Yes. Message us on WhatsApp at ${WHATSAPP_NUMBER} for a free demo at your school, or create an account and try it with one class.`,
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
    description: "Weekly student progress on WAEC grade bands for Nigerian secondary schools.",
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
    <div className="site min-h-screen">
      <SignedInRedirect />
      <JsonLd data={STRUCTURED_DATA} />
      <PublicNav />

      <main>
        {/* Hero: the promise on the left, a real Nigerian classroom on the right. */}
        <section className="max-w-6xl mx-auto px-6 pt-16 pb-20 grid gap-12 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)] items-center">
          <div>
            <p className="eyebrow mb-4">For private secondary schools in Nigeria</p>
            <h1 className="mb-6">Know which students need help this week, while there is still time to act</h1>
            <p className="lead mb-8">
              GradePulse turns the weekly tests your teachers already give into a clear picture of every class on
              WAEC grade bands. Each week you see who needs help, who is on track and who is ahead, subject by
              subject.
            </p>
            <div className="flex flex-wrap items-center gap-x-6 gap-y-4">
              <a href={WHATSAPP_URL} className="btn-site btn-gold">
                Book a free demo on WhatsApp
              </a>
              <Link href="/signup" className="link font-semibold">
                Start free with one class
              </Link>
            </div>
            <p className="text-sm text-ink-muted mt-6">
              Free for up to 40 students. ₦500 per student per term for the whole school. Made in Enugu.
            </p>
          </div>
          <figure>
            <Image
              src="/media/classroom-lagos.webp"
              alt="A secondary school student in uniform listening in class, pen in hand"
              width={1040}
              height={1300}
              priority
              className="w-full h-auto rounded-xl"
            />
            <figcaption className="text-xs text-ink-muted mt-2">A classroom in Lagos. Photograph: Doug Linstedt, Unsplash.</figcaption>
          </figure>
        </section>

        {/* The demo: real GradePulse screens, with sound and captions. */}
        <section className="bg-paper-deep" aria-labelledby="demo-heading">
          <div className="max-w-6xl mx-auto px-6 py-20 grid gap-12 md:grid-cols-[minmax(0,20rem)_minmax(0,1fr)] items-center">
            <video
              controls
              preload="none"
              playsInline
              poster="/media/gradepulse-demo-poster.jpg"
              width={540}
              height={960}
              className="w-full h-auto rounded-xl bg-ink"
              aria-label="A 40 second demo of GradePulse"
            >
              <source src="/media/gradepulse-demo.mp4" type="video/mp4" />
              <track kind="captions" src="/media/gradepulse-demo.en.vtt" srcLang="en" label="English" default />
            </video>
            <div className="measure">
              <h2 id="demo-heading" className="mb-4">See it in 40 seconds</h2>
              <p className="lead mb-6">Real GradePulse screens with a sample class, from the score sheet to the sheet that goes home.</p>
              <ol className="space-y-3 text-ink-soft list-decimal pl-5">
                <li>A teacher types this week&apos;s Mathematics scores for JSS2A.</li>
                <li>The dashboard shows the 9 students below 40% by name.</li>
                <li>One student&apos;s results over six weeks, rising from 32% to 62%.</li>
                <li>The progress sheet a parent receives.</li>
              </ol>
            </div>
          </div>
        </section>

        {/* The problem. */}
        <section className="max-w-6xl mx-auto px-6 py-20">
          <div className="measure">
            <h2 className="mb-4">Results day comes too late</h2>
            <p className="lead">
              Teachers give tests every week, but the scores stay in exercise books and registers, and nobody has time
              to add them up class by class. A student who started slipping in week three is found on results day,
              when the term is over. GradePulse does the adding up every week, so extra help reaches that student in
              week four.
            </p>
          </div>
        </section>

        {/* How it works: one row per step, screenshot beside the words. */}
        <section className="rule" aria-labelledby="how-heading">
          <div className="max-w-6xl mx-auto px-6 py-20">
            <h2 id="how-heading" className="mb-12">How a week with GradePulse works</h2>
            <ol className="space-y-20">
              {STEPS.map((step, i) => (
                <li
                  key={step.title}
                  className={`grid gap-8 items-center ${i % 2 === 1 ? "lg:grid-cols-[minmax(0,1.2fr)_minmax(0,0.8fr)]" : "lg:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]"}`}
                >
                  <div className={i % 2 === 1 ? "lg:order-2" : undefined}>
                    <p className="font-serif text-5xl text-forest mb-4 num" aria-hidden="true">{i + 1}</p>
                    <h3 className="mb-3">{step.title}</h3>
                    <p className="text-ink-soft">{step.body}</p>
                  </div>
                  <div className={i % 2 === 1 ? "lg:order-1" : undefined}>
                    <Screenshot {...step.image} />
                  </div>
                </li>
              ))}
            </ol>
          </div>
        </section>

        {/* What it is built for: a two column list. */}
        <section className="bg-paper-deep" aria-labelledby="built-heading">
          <div className="max-w-6xl mx-auto px-6 py-20">
            <h2 id="built-heading" className="mb-10">Made for how Nigerian schools work</h2>
            <dl className="grid gap-x-16 gap-y-8 md:grid-cols-2">
              {BENEFITS.map(([title, body]) => (
                <div key={title} className="rule pt-5">
                  <dt className="font-semibold text-ink mb-1">{title}</dt>
                  <dd className="text-ink-soft">{body}</dd>
                </div>
              ))}
            </dl>
          </div>
        </section>

        {/* Pricing in brief. */}
        <section className="max-w-6xl mx-auto px-6 py-20" aria-labelledby="price-heading">
          <h2 id="price-heading" className="mb-10">Two plans</h2>
          <div className="grid gap-6 md:grid-cols-2 max-w-4xl">
            <div className="border border-rule rounded-xl p-8 bg-white">
              <h3>Free</h3>
              <p className="text-4xl font-semibold text-ink mt-3 num">₦0</p>
              <p className="text-ink-soft mt-3">Up to 40 students, about one class, with score sheets, the weekly groups and each student&apos;s progress.</p>
            </div>
            <div className="border-2 border-forest rounded-xl p-8 bg-white">
              <h3>Whole school</h3>
              <p className="text-4xl font-semibold text-ink mt-3 num">
                ₦500 <span className="text-base font-normal text-ink-soft">per student, per term</span>
              </p>
              <p className="text-ink-soft mt-3">Every student, plus printable class reports and a progress sheet for every parent.</p>
            </div>
          </div>
          <p className="mt-6">
            <Link href="/pricing" className="link">Read the pricing details and common questions</Link>
          </p>
        </section>

        {/* Questions. */}
        <section className="rule" aria-labelledby="faq-heading">
          <div className="max-w-3xl mx-auto px-6 py-20">
            <h2 id="faq-heading" className="mb-8">Questions school owners ask</h2>
            <div className="divide-y divide-rule border-y border-rule">
              {FAQS.map((faq) => (
                <details key={faq.q} className="py-5">
                  <summary className="font-semibold text-ink cursor-pointer">{faq.q}</summary>
                  <p className="text-ink-soft mt-3">{faq.a}</p>
                </details>
              ))}
            </div>
          </div>
        </section>

        {/* Closing call to action, the same action as the top. */}
        <section className="bg-forest text-white">
          <div className="max-w-6xl mx-auto px-6 py-20 grid gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] items-center">
            <div>
              <h2 className="mb-4" style={{ color: "#ffffff" }}>See GradePulse with your own classes</h2>
              <p className="text-lg text-white/80 mb-8 max-w-md">
                We visit schools in Enugu and show it online anywhere in Nigeria, using your own classes and subjects.
              </p>
              <div className="flex flex-wrap gap-4">
                <a href={WHATSAPP_URL} className="btn-site btn-gold">
                  Book a free demo on WhatsApp
                </a>
                <Link href="/signup" className="btn-site btn-on-dark">
                  Start free with one class
                </Link>
              </div>
              <p className="text-sm text-white/70 mt-6">Or call or message {WHATSAPP_NUMBER}.</p>
            </div>
            <Image
              src="/media/classroom-lagos-wide.webp"
              alt="Students in uniform at their desks in a secondary school classroom"
              width={1600}
              height={900}
              className="w-full h-auto rounded-xl"
            />
          </div>
        </section>
      </main>

      <PublicFooter />
    </div>
  );
}
