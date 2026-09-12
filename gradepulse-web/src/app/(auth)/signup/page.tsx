"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth";

export default function SignupPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [schoolName, setSchoolName] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { signup } = useAuth();
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (password.length < 6) {
      setError("Password must be at least 6 characters");
      return;
    }
    setLoading(true);
    try {
      await signup(email, password, schoolName || "My School");
      router.push("/dashboard");
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
              <img src="/logo.png" alt="GradePulse" className="w-14 h-14 rounded-2xl shadow-lg" />
              <span className="text-4xl font-extrabold tracking-tight">GradePulse</span>
            </div>

            <p className="text-lg text-white/60 leading-relaxed mb-12">
              Start making data-driven decisions for your students today
            </p>

            {/* Feature List */}
            <div className="space-y-4 text-left max-w-xs mx-auto mb-12">
              {[
                { icon: "01", text: "AI-powered performance triaging" },
                { icon: "02", text: "Personalized content recommendations" },
                { icon: "03", text: "Real-time student progress tracking" },
                { icon: "04", text: "LinUCB + Neural Hybrid engine" },
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
            <img src="/logo.png" alt="GradePulse" className="w-9 h-9 rounded-xl" />
            <span className="text-xl font-bold text-navy">GradePulse</span>
          </div>

          {/* Header */}
          <div className="mb-8">
            <h1 className="text-2xl font-bold text-navy tracking-tight">Create your account</h1>
            <p className="text-text-secondary text-sm mt-1.5">Get started with GradePulse in seconds</p>
          </div>

          {/* Error */}
          {error && (
            <div className="bg-danger-light border border-danger/20 text-danger px-4 py-3 rounded-lg text-sm mb-6 flex items-center gap-2">
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
              <label className="input-label">School Name</label>
              <input
                type="text"
                value={schoolName}
                onChange={(e) => setSchoolName(e.target.value)}
                className="input"
                placeholder="Lagos Model School"
              />
              <span className="input-hint">Optional - can be added later</span>
            </div>

            <div className="input-group">
              <label className="input-label">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="input"
                placeholder="teacher@school.edu.ng"
              />
            </div>

            <div className="input-group">
              <label className="input-label">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="input"
                placeholder="At least 6 characters"
              />
              {password.length > 0 && password.length < 6 && (
                <span className="text-xs text-danger mt-1">Password must be at least 6 characters</span>
              )}
            </div>

            <button
              type="submit"
              disabled={loading}
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
          </p>
        </div>
      </div>
    </div>
  );
}
