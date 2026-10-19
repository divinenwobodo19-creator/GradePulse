import Image from "next/image";
import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Privacy policy · GradePulse",
  description: "How GradePulse, a product of N-Library, handles school, teacher and student data.",
};

const UPDATED = "17 October 2026";

const SECTIONS: { heading: string; body: React.ReactNode }[] = [
  {
    heading: "Who we are",
    body: (
      <p>
        GradePulse is a product of N-Library, based in Enugu, Nigeria. It helps schools see each week which students
        need help, from the test scores their teachers enter. This policy explains what data GradePulse holds and how
        we protect it, in line with the Nigeria Data Protection Act 2023 (NDPA).
      </p>
    ),
  },
  {
    heading: "The school decides; we process for the school",
    body: (
      <p>
        Each school that uses GradePulse decides what student data to enter and what it is used for. Under the NDPA
        the school is the <strong>data controller</strong> and N-Library is its <strong>data processor</strong>: we
        use the data only to run GradePulse for that school, on its instructions. Schools that would like a written
        data processing agreement can ask us for one.
      </p>
    ),
  },
  {
    heading: "What we hold",
    body: (
      <ul>
        <li>
          <strong>School staff accounts:</strong> the email address and password of each admin and teacher. Passwords
          are stored only as a one-way hash (bcrypt), so nobody at N-Library can read them.
        </li>
        <li>
          <strong>Student records the school enters:</strong> names, the school&apos;s own student IDs, classes, and
          test scores with their dates.
        </li>
        <li>
          <strong>Payments:</strong> the number of students paid for, the amount, the date and the receipt email.
          Card and bank details are handled by Paystack and never reach GradePulse.
        </li>
        <li>
          <strong>Technical logs:</strong> the time and address of requests, kept to keep the service running and
          secure.
        </li>
      </ul>
    ),
  },
  {
    heading: "What we do not do",
    body: (
      <ul>
        <li>We do not sell data, show advertising, or share student data with anyone outside the school.</li>
        <li>We do not use student data to train AI models.</li>
        <li>One school can never see another school&apos;s data, and a teacher sees only the classes they teach.</li>
      </ul>
    ),
  },
  {
    heading: "Children's data",
    body: (
      <p>
        Most students in GradePulse are children. Schools enter their data as part of the education they already
        provide, and remain responsible for telling parents and guardians how student information is used, as the
        NDPA requires. Parents who want to see, correct or remove their child&apos;s data should ask the school; we
        will help the school do it.
      </p>
    ),
  },
  {
    heading: "Who else is involved",
    body: (
      <ul>
        <li>
          <strong>Cloudflare</strong> carries and protects traffic between your browser and GradePulse. Its network
          spans many countries, so data in transit may pass outside Nigeria; it is encrypted all the way.
        </li>
        <li>
          <strong>Paystack</strong> processes payments.
        </li>
      </ul>
    ),
  },
  {
    heading: "How we protect it",
    body: (
      <ul>
        <li>All connections are encrypted (HTTPS).</li>
        <li>Every request is checked against the school and, for teachers, the classes it belongs to.</li>
        <li>Sign-in attempts are rate-limited, and administrative tools need a separate operator key.</li>
        <li>The data is backed up regularly, and the backups are encrypted when stored away from the server.</li>
      </ul>
    ),
  },
  {
    heading: "How long we keep it",
    body: (
      <p>
        We keep a school&apos;s data while it uses GradePulse, so its history of scores is there term after term. A
        school can ask us to delete its data, or a single student&apos;s, at any time; we do so within 30 days, and
        it also leaves our rolling backups within that time.
      </p>
    ),
  },
  {
    heading: "If something goes wrong",
    body: (
      <p>
        If we learn of a breach that affects personal data, we will tell the affected schools without undue delay
        and notify the Nigeria Data Protection Commission within 72 hours where the NDPA requires it.
      </p>
    ),
  },
  {
    heading: "Your rights and how to reach us",
    body: (
      <p>
        Under the NDPA you can ask to see, correct or delete personal data, or object to how it is used. School
        staff can contact us directly; parents and students should start with their school. Reach N-Library on
        WhatsApp at <strong>0803 698 9732</strong>. You can also complain to the Nigeria Data Protection Commission.
        If this policy changes, we will update the date at the top and tell schools of any important change.
      </p>
    ),
  },
];

export default function PrivacyPage() {
  return (
    <div className="min-h-screen bg-white">
      <nav className="border-b border-border px-6 py-4">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2.5">
            <Image src="/logo.png" alt="GradePulse" width={32} height={32} className="w-8 h-8 rounded-lg" />
            <span className="text-lg font-bold text-navy">GradePulse</span>
          </Link>
          <Link href="/pricing" className="body-sm text-text-secondary hover:text-navy transition-colors">
            Pricing
          </Link>
        </div>
      </nav>

      <main className="max-w-3xl mx-auto px-6 py-16">
        <h1 className="heading-display text-navy mb-2">Privacy policy</h1>
        <p className="body-sm text-text-muted mb-10">Last updated {UPDATED}</p>
        <div className="space-y-8">
          {SECTIONS.map((section) => (
            <section key={section.heading}>
              <h2 className="heading-2 text-navy mb-3">{section.heading}</h2>
              <div className="body text-text-secondary space-y-3 [&_ul]:list-disc [&_ul]:pl-5 [&_ul]:space-y-2">
                {section.body}
              </div>
            </section>
          ))}
        </div>
      </main>

      <footer className="border-t border-border py-8 px-6 text-center">
        <p className="body-sm text-text-muted">&copy; 2026 GradePulse, a product of N-Library.</p>
      </footer>
    </div>
  );
}
