import type { Metadata } from "next";
import { IBM_Plex_Mono, Public_Sans, Source_Serif_4 } from "next/font/google";
import { AuthProvider } from "@/lib/auth";
import "./globals.css";

// Text in Public Sans; public-page headings in Source Serif 4 (a serif
// headline over a sans body); IBM Plex Mono for IDs and codes.
const publicSans = Public_Sans({ variable: "--font-public-sans", subsets: ["latin"] });
const sourceSerif = Source_Serif_4({ variable: "--font-source-serif", subsets: ["latin"] });
const plexMono = IBM_Plex_Mono({ variable: "--font-plex-mono", subsets: ["latin"], weight: ["400", "600"] });

const SITE_DESCRIPTION =
  "See every week which students are falling behind, on WAEC grade bands. Built for Nigerian secondary schools.";

export const metadata: Metadata = {
  metadataBase: new URL("https://gradepulse.com.ng"),
  title: { default: "GradePulse", template: "%s · GradePulse" },
  description: SITE_DESCRIPTION,
  applicationName: "GradePulse",
  openGraph: {
    type: "website",
    siteName: "GradePulse",
    locale: "en_NG",
    title: "GradePulse: see every week which students are falling behind",
    description: SITE_DESCRIPTION,
  },
  twitter: { card: "summary_large_image" },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      className={`${publicSans.variable} ${sourceSerif.variable} ${plexMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
