import Image from "next/image";
import Link from "next/link";

// Shared pieces of the public (signed-out) pages: header, footer and the
// WhatsApp contact that every page points to.

export const WHATSAPP_NUMBER = "0803 698 9732";
export const WHATSAPP_URL =
  "https://wa.me/2348036989732?text=" + encodeURIComponent("Hello, I'd like a demo of GradePulse for my school.");
export const SITE_URL = "https://gradepulse.com.ng";

export function PublicNav() {
  return (
    <nav className="border-b border-border px-6 py-4 bg-white">
      <div className="max-w-6xl mx-auto flex items-center justify-between gap-4">
        <Link href="/" className="flex items-center gap-2.5">
          <Image src="/logo.png" alt="GradePulse" width={32} height={32} className="w-8 h-8 rounded-lg" />
          <span className="text-lg font-bold text-navy">GradePulse</span>
        </Link>
        <div className="flex items-center gap-5">
          <Link href="/pricing" className="hidden sm:inline body-sm text-text-secondary hover:text-navy transition-colors">
            Pricing
          </Link>
          <Link
            href="/waec-grade-calculator"
            className="hidden md:inline body-sm text-text-secondary hover:text-navy transition-colors"
          >
            WAEC grade calculator
          </Link>
          <Link href="/login" className="body-sm text-text-secondary hover:text-navy transition-colors">
            Sign in
          </Link>
          <Link href="/signup" className="btn btn-primary btn-sm">
            Start free
          </Link>
        </div>
      </div>
    </nav>
  );
}

export function PublicFooter() {
  return (
    <footer className="border-t border-border py-10 px-6 bg-white">
      <div className="max-w-6xl mx-auto flex flex-col sm:flex-row gap-6 justify-between">
        <div>
          <div className="font-bold text-navy">GradePulse</div>
          <p className="body-sm text-text-muted mt-1">
            A product of N-Library, Enugu, Nigeria.
            <br />
            WhatsApp:{" "}
            <a href={WHATSAPP_URL} className="underline hover:text-navy">
              {WHATSAPP_NUMBER}
            </a>
          </p>
        </div>
        <ul className="body-sm text-text-secondary space-y-1.5">
          <li><Link href="/pricing" className="hover:text-navy">Pricing</Link></li>
          <li><Link href="/waec-grade-calculator" className="hover:text-navy">WAEC grade calculator</Link></li>
          <li><Link href="/guides/spot-struggling-students" className="hover:text-navy">Spotting struggling students early</Link></li>
          <li><Link href="/privacy" className="hover:text-navy">Privacy policy</Link></li>
        </ul>
      </div>
      <p className="max-w-6xl mx-auto body-sm text-text-muted mt-8">&copy; 2026 GradePulse, a product of N-Library.</p>
    </footer>
  );
}

/** A screenshot shown inside a simple browser window, so it reads as software on a computer. */
export function BrowserFrame({ src, alt, width, height, priority = false }: {
  src: string; alt: string; width: number; height: number; priority?: boolean;
}) {
  return (
    <div className="rounded-xl overflow-hidden border border-border shadow-elevated bg-white">
      <div className="flex items-center gap-1.5 px-3 py-2 bg-surface-elevated border-b border-border" aria-hidden="true">
        <span className="w-2.5 h-2.5 rounded-full bg-[#ff5f57]" />
        <span className="w-2.5 h-2.5 rounded-full bg-[#febc2e]" />
        <span className="w-2.5 h-2.5 rounded-full bg-[#28c840]" />
        <span className="ml-3 text-[11px] text-text-muted">gradepulse.com.ng</span>
      </div>
      <Image src={src} alt={alt} width={width} height={height} priority={priority} className="w-full h-auto" />
    </div>
  );
}

/** Structured data for search engines, as a JSON-LD script tag. */
export function JsonLd({ data }: { data: object }) {
  return <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(data) }} />;
}
