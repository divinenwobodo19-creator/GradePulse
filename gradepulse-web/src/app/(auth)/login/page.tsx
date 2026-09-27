"use client";

import Image from "next/image";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { user, loading: authLoading, login } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!authLoading && user) router.replace("/dashboard");
  }, [authLoading, router, user]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(email, password);
      router.replace("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
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
        <div className="absolute top-1/4 -left-32 w-96 h-96 bg-gold/10 rounded-full blur-3xl" />
        <div className="absolute bottom-1/4 right-0 w-80 h-80 bg-gold/5 rounded-full blur-3xl" />

        <div className="relative z-10 flex flex-col items-center justify-center w-full p-16 text-white">
          <div className="max-w-md text-center">
            {/* Logo */}
            <div className="flex items-center justify-center gap-3 mb-8">
              <Image src="/logo.png" alt="GradePulse" width={56} height={56} className="w-14 h-14 rounded-2xl shadow-lg" />
              <span className="text-4xl font-extrabold tracking-tight">GradePulse</span>
            </div>

            <p className="text-lg text-white/60 leading-relaxed mb-12">
              AI-powered student performance intelligence built for Nigerian schools
            </p>

            {/* Feature Pills */}
            <div className="space-y-3 text-left max-w-xs mx-auto mb-12">
              {[
                "LinUCB + Neural Hybrid recommendation engine",
                "Automated performance triage by subject",
                "Real-time brain state persistence",
              ].map((feature) => (
                <div key={feature} className="flex items-center gap-3">
                  <div className="w-5 h-5 rounded-full bg-gold/20 flex items-center justify-center shrink-0">
                    <div className="w-1.5 h-1.5 rounded-full bg-gold" />
                  </div>
                  <span className="text-sm text-white/50">{feature}</span>
                </div>
              ))}
            </div>

            {/* Stats */}
            <div className="grid grid-cols-3 gap-6 pt-8 border-t border-white/10">
              {[
                { value: "94%", label: "Accuracy" },
                { value: "3,120", label: "Sessions" },
                { value: "5x", label: "Faster" },
              ].map((stat) => (
                <div key={stat.label} className="text-center">
                  <div className="text-2xl font-bold text-gold">{stat.value}</div>
                  <div className="text-xs text-white/40 mt-1 uppercase tracking-wider">{stat.label}</div>
                </div>
              ))}
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
            <h1 className="text-2xl font-bold text-navy tracking-tight">Welcome back</h1>
            <p className="text-text-secondary text-sm mt-1.5">Sign in to your teacher portal</p>
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
            <div className="input-group">
               <label className="input-label" htmlFor="login-email">Email</label>
               <input
                 id="login-email"
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
               <label className="input-label" htmlFor="login-password">Password</label>
               <input
                 id="login-password"
                 name="password"
                 type="password"
                 autoComplete="current-password"
                 value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="input"
                placeholder="Enter your password"
              />
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
                  Signing in...
                </>
              ) : (
                "Sign In"
              )}
            </button>
          </form>

          {/* Footer */}
          <p className="mt-8 text-center text-sm text-text-secondary">
            Don&apos;t have an account?{" "}
            <Link href="/signup" className="text-gold font-semibold hover:text-gold-dark transition-colors">
              Create one
            </Link>
          </p>

          {process.env.NODE_ENV !== "production" && (
            <div className="mt-6 p-4 bg-surface-elevated rounded-lg border border-border">
              <p className="text-xs font-medium text-text-secondary mb-2">Demo Credentials</p>
              <div className="space-y-1">
                <p className="text-xs text-text-muted font-mono">demo@gradepulse.com / demo1234</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
