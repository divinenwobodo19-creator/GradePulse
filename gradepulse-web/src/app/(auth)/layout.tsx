import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Sign in or create your school account",
  description: "Create your school's GradePulse account, free for up to 40 students, or sign in.",
};

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return children;
}
