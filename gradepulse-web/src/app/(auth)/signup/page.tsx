"use client";

import Image from "next/image";
import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth";

// Mirrors PASSWORD_MIN_LENGTH in linucb_brain/api/schemas.py.
const PASSWORD_MIN_LENGTH = 8;

// useSearchParams needs a Suspense boundary to prerender.
export default function SignupPage() {
  return (
    <Suspense>
      <SignupForm />
    </Suspense>
  );
}

function SignupForm() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [schoolName, setSchoolName] = useState("");
  // An admin's invite link is /signup?invite=CODE.
  const searchParams = useSearchParams();
  const [inviteCode, setInviteCode] = useState(() => searchParams.get("invite") ?? "");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { user, loading: authLoading, signup } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!authLoading && user) router.replace("/dashboard");
  }, [authLoading, router, user]);

  const joining = inviteCode.trim().length > 0;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (password.length < PASSWORD_MIN_LENGTH) {
      setError(`Password must be at least ${PASSWORD_MIN_LENGTH} characters`);
      return;
    }
    setLoading(true);
    try {
      await signup(email, password, schoolName || "My School", inviteCode.trim() || undefined);
      router.replace("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Signup failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen">
      {/* Left Panel - Branding */}
      <div className="hidden lg:flex lg:w-[55%] bg-navy relative overflow-hidden">
        {/* Background Pattern */}
        <div className="absolute inset-0 opacity-[0.03]" style={{
          backgroundImage: `radial-gradient(circle at 1px 1px, white 1px, transparent 0)`,
          backgroundSize: '32px 32px'
        }} />

        {/* Gradient Orbs */}
        <div className="absolute top-1/3 -right-32 w-96 h-96 bg-gold/10 rounded-full blur-3xl" />
        <div className="absolute bottom-1/3 left-0 w-80 h-80 bg-gold/5 rounded-full blur-3xl" />

        <div className="relative z-10 flex flex-col items-center justify-center w-full p-16 text-white">
          <div className="max-w-md text-center">
            {/* Logo */}
            <div className="flex items-center justify-center gap-3 mb-8">
              <Image src="/logo.png" alt="GradePulse" width={56} height={56} className="w-14 h-14 rounded-2xl shadow-lg" />
              <span className="text-4xl font-extrabold tracking-tight">GradePulse</span>
            </div>

            <p className="text-lg text-white/60 leading-relaxed mb-12">
              Start making data-driven decisions for your students today
            </p>

            {/* Feature List */}
            <div className="space-y-4 text-left max-w-xs mx-auto mb-12">
              {[
                { icon: "01", text: "Weekly tiers on WAEC grade bands" },
                { icon: "02", text: "Grades that update with every test" },
                { icon: "03", text: "Progress tracking for every student" },
                { icon: "04", text: "Invite your teachers with one link" },
              ].map((feature) => (
                <div key={feature.icon} className="flex items-center gap-4">
                  <div className="w-8 h-8 rounded-lg bg-gold/15 flex items-center justify-center text-gold text-xs font-bold shrink-0">
                    {feature.icon}
                  </div>
                  <span className="text-sm text-white/50">{feature.text}</span>
                </div>
              ))}
            </div>

            {/* Bottom Tagline */}
            <div className="pt-8 border-t border-white/10">
              <p className="text-sm text-white/30 italic">
                &ldquo;Built for the Nigerian education system&rdquo;
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Right Panel - Form */}
      <div className="flex-1 flex items-center justify-center p-8 bg-white">
        <div className="w-full max-w-[400px]">
          {/* Mobile Logo */}
          <div className="lg:hidden flex items-center gap-2.5 mb-10">
            <Image src="/logo.png" alt="GradePulse" width={36} height={36} className="w-9 h-9 rounded-xl" />
            <span className="text-xl font-bold text-navy">GradePulse</span>
          </div>

          {/* Header */}
          <div className="mb-8">
            <h1 className="text-2xl font-bold text-navy tracking-tight">Create your account</h1>
            <p className="text-text-secondary text-sm mt-1.5">Get started with GradePulse in seconds</p>
          </div>

          {/* Error */}
          {error && (
             <div role="alert" aria-live="assertive" className="bg-danger-light border border-danger/20 text-danger px-4 py-3 rounded-lg text-sm mb-6 flex items-center gap-2">
              <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="8" x2="12" y2="12" />
                <line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
              {error}
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-5">
            {!joining && (
              <div className="input-group">
                <label className="input-label" htmlFor="signup-school">School Name</label>
                <input
                  id="signup-school"
                  name="school"
                  type="text"
                  autoComplete="organization"
                  value={schoolName}
                  onChange={(e) => setSchoolName(e.target.value)}
                  className="input"
                  placeholder="Lagos Model School"
                />
                <span className="input-hint">Creates a new school with you as its admin</span>
              </div>
            )}

            <div className="input-group">
              <label className="input-label" htmlFor="signup-invite">Invite Code</label>
              <input
                id="signup-invite"
                name="invite_code"
                type="text"
                autoComplete="off"
                value={inviteCode}
                onChange={(e) => setInviteCode(e.target.value)}
                className="input font-mono"
                placeholder="Only if your school admin sent you one"
              />
              <span className="input-hint">
                {joining ? "You will join your school as a teacher" : "Leave blank to set up a new school"}
              </span>
            </div>

            <div className="input-group">
               <label className="input-label" htmlFor="signup-email">Email</label>
               <input
                 id="signup-email"
                 name="email"
                 type="email"
                 autoComplete="email"
                 value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="input"
                placeholder="teacher@school.edu.ng"
              />
            </div>

            <div className="input-group">
               <label className="input-label" htmlFor="signup-password">Password</label>
               <input
                 id="signup-password"
                 name="password"
                 type="password"
                 autoComplete="new-password"
                 aria-describedby="signup-password-hint"
                 value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={PASSWORD_MIN_LENGTH}
                className="input"
                placeholder={`At least ${PASSWORD_MIN_LENGTH} characters`}
              />
              {password.length > 0 && password.length < PASSWORD_MIN_LENGTH && (
                 <span id="signup-password-hint" className="text-xs text-danger mt-1">Password must be at least {PASSWORD_MIN_LENGTH} characters</span>
              )}
            </div>

            <button
               type="submit"
               disabled={loading}
               aria-busy={loading}
               className="btn btn-primary btn-lg w-full"
            >
              {loading ? (
                <>
                  <div className="spinner spinner-sm" style={{ borderTopColor: 'var(--color-navy)' }} />
                  Creating account...
                </>
              ) : (
                "Create Account"
              )}
            </button>
          </form>

          {/* Footer */}
          <p className="mt-8 text-center text-sm text-text-secondary">
            Already have an account?{" "}
            <Link href="/login" className="text-gold font-semibold hover:text-gold-dark transition-colors">
              Sign in
            </Link>
            {" · "}
            <Link href="/pricing" className="text-gold font-semibold hover:text-gold-dark transition-colors">
              Pricing
            </Link>
          </p>
          <p className="mt-3 text-center text-xs text-text-muted">
            By creating an account you agree to how we handle your school&apos;s data in our{" "}
            <Link href="/privacy" className="underline hover:text-navy">
              privacy policy
            </Link>
            .
          </p>
        </div>
      </div>
    </div>
  );
}
