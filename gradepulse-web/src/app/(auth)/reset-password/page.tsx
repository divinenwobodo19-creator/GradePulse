"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";

// Mirrors PASSWORD_MIN_LENGTH in linucb_brain/api/schemas.py.
const PASSWORD_MIN_LENGTH = 10;

// useSearchParams needs a Suspense boundary to prerender.
export default function ResetPasswordPage() {
  return (
    <Suspense>
      <ResetPasswordForm />
    </Suspense>
  );
}

function ResetPasswordForm() {
  const router = useRouter();
  // A reset link is /reset-password?code=CODE.
  const searchParams = useSearchParams();
  const [code, setCode] = useState(() => searchParams.get("code") ?? "");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [done, setDone] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (password.length < PASSWORD_MIN_LENGTH) {
      setError(`Password must be at least ${PASSWORD_MIN_LENGTH} characters`);
      return;
    }
    if (password !== confirm) {
      setError("The two passwords do not match");
      return;
    }
    setSaving(true);
    try {
      await api.resetPassword(code.trim(), password);
      setDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not reset the password");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center p-8 bg-white">
      <div className="w-full max-w-[400px]">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-navy tracking-tight">Set a new password</h1>
          <p className="text-text-secondary text-sm mt-1.5">
            Use the reset link your school admin gave you. It works once and expires after 24 hours.
          </p>
        </div>

        {done ? (
          <div role="status" className="space-y-5">
            <p className="body text-navy">Your password has been changed. You can sign in with it now.</p>
            <button type="button" onClick={() => router.replace("/login")} className="btn btn-primary btn-lg w-full">
              Go to Sign In
            </button>
          </div>
        ) : (
          <>
            {error && (
              <div role="alert" aria-live="assertive" className="bg-danger-light border border-danger/20 text-danger px-4 py-3 rounded-lg text-sm mb-6">
                {error}
              </div>
            )}
            <form onSubmit={handleSubmit} className="space-y-5">
              <div className="input-group">
                <label className="input-label" htmlFor="reset-code">Reset code</label>
                <input
                  id="reset-code"
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  required
                  autoComplete="off"
                  className="input font-mono"
                />
              </div>
              <div className="input-group">
                <label className="input-label" htmlFor="reset-password">New password</label>
                <input
                  id="reset-password"
                  type="password"
                  autoComplete="new-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  minLength={PASSWORD_MIN_LENGTH}
                  className="input"
                  placeholder={`At least ${PASSWORD_MIN_LENGTH} characters`}
                />
              </div>
              <div className="input-group">
                <label className="input-label" htmlFor="reset-confirm">Repeat new password</label>
                <input
                  id="reset-confirm"
                  type="password"
                  autoComplete="new-password"
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  required
                  className="input"
                />
              </div>
              <button type="submit" disabled={saving} aria-busy={saving} className="btn btn-primary btn-lg w-full">
                {saving ? "Saving..." : "Set Password"}
              </button>
            </form>
            <p className="mt-8 text-center text-sm text-text-secondary">
              <Link href="/login" className="text-gold font-semibold hover:text-gold-dark transition-colors">
                Back to sign in
              </Link>
            </p>
          </>
        )}
      </div>
    </div>
  );
}
