import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { AuthProvider } from "@/lib/auth";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

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
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
