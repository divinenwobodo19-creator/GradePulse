import Image from "next/image";
import Link from "next/link";

// Shared pieces of the public (signed-out) pages: header, footer and the
// WhatsApp contact that every page points to. Styling comes from the .site
// rules in globals.css: flat colours, a serif for headings, no motion.

export const WHATSAPP_NUMBER = "0803 698 9732";
export const WHATSAPP_URL =
  "https://wa.me/2348036989732?text=" + encodeURIComponent("Hello, I'd like a demo of GradePulse for my school.");
export const SITE_URL = "https://gradepulse.com.ng";

export function PublicNav() {
  return (
    <header className="border-b border-rule bg-paper">
      <nav className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between gap-6" aria-label="Main">
        <Link href="/" className="flex items-center gap-3">
          <Image src="/logo.png" alt="" width={32} height={32} className="w-8 h-8 rounded-md" />
          <span className="text-lg font-semibold text-ink">GradePulse</span>
        </Link>
        <div className="flex items-center gap-4 sm:gap-6 text-sm whitespace-nowrap">
          <Link href="/pricing" className="hidden sm:inline text-ink-soft hover:text-ink">
            Pricing
          </Link>
          <Link href="/waec-grade-calculator" className="hidden md:inline text-ink-soft hover:text-ink">
            WAEC grade calculator
          </Link>
          <Link href="/login" className="text-ink-soft hover:text-ink">
            Sign in
          </Link>
          <a href={WHATSAPP_URL} className="btn-site btn-gold text-sm py-2 px-4">
            Book a demo
          </a>
        </div>
      </nav>
    </header>
  );
}

export function PublicFooter() {
  return (
    <footer className="border-t border-rule bg-paper">
      <div className="max-w-6xl mx-auto px-6 py-12 grid gap-8 sm:grid-cols-[minmax(0,1fr)_auto]">
        <div className="text-sm text-ink-soft space-y-1">
          <p className="font-semibold text-ink">GradePulse</p>
          <p>A product of N-Library, Enugu, Nigeria.</p>
          <p>
            WhatsApp{" "}
            <a href={WHATSAPP_URL} className="link">
              {WHATSAPP_NUMBER}
            </a>
          </p>
        </div>
        <ul className="text-sm space-y-2">
          <li><Link href="/pricing" className="text-ink-soft hover:text-ink">Pricing</Link></li>
          <li><Link href="/waec-grade-calculator" className="text-ink-soft hover:text-ink">WAEC grade calculator</Link></li>
          <li><Link href="/guides/spot-struggling-students" className="text-ink-soft hover:text-ink">Spotting struggling students early</Link></li>
          <li><Link href="/privacy" className="text-ink-soft hover:text-ink">Privacy policy</Link></li>
        </ul>
      </div>
      <div className="max-w-6xl mx-auto px-6 pb-10 text-xs text-ink-muted">
        © 2026 GradePulse, a product of N-Library. Classroom photograph by Doug Linstedt on Unsplash.
      </div>
    </footer>
  );
}

/** A screenshot of GradePulse in a plain frame. */
export function Screenshot({ src, alt, width, height, priority = false }: {
  src: string; alt: string; width: number; height: number; priority?: boolean;
}) {
  return (
    <div className="frame">
      <Image src={src} alt={alt} width={width} height={height} priority={priority} className="w-full h-auto" />
    </div>
  );
}

/** Structured data for search engines, as a JSON-LD script tag. */
export function JsonLd({ data }: { data: object }) {
  return <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(data) }} />;
}
