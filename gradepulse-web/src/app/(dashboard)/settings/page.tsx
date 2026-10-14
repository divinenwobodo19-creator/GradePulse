"use client";

import { useState, useEffect, useRef } from "react";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import type { BrainSummary, Invite, Member, SchoolClass } from "@/lib/types";
import { rememberSubjects, useSubjects } from "@/lib/subjects";

// Mirrors PASSWORD_MIN_LENGTH in linucb_brain/api/schemas.py.
const PASSWORD_MIN_LENGTH = 8;

export default function SettingsPage() {
  const { user, loading: authLoading, logout } = useAuth();
  const [toast, setToast] = useState<{ type: string; message: string } | null>(null);
  const [summary, setSummary] = useState<BrainSummary | null>(null);
  const [apiStatus, setApiStatus] = useState<"checking" | "online" | "offline">("checking");
  const [error, setError] = useState("");
  const [invites, setInvites] = useState<Invite[]>([]);
  const [inviting, setInviting] = useState(false);
  const [members, setMembers] = useState<Member[]>([]);
  const [schoolClasses, setSchoolClasses] = useState<SchoolClass[]>([]);
  const [assigning, setAssigning] = useState("");
  // The reset link just created for a teacher; shown once so it can be copied.
  const [resetLink, setResetLink] = useState<{ memberId: string; url: string } | null>(null);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [changingPassword, setChangingPassword] = useState(false);
  const loadedSubjects = useSubjects();
  // Set once the admin edits the list here; until then show what was loaded.
  const [editedSubjects, setEditedSubjects] = useState<string[] | null>(null);
  const subjects = editedSubjects ?? loadedSubjects;
  const [newSubject, setNewSubject] = useState("");
  const [savingSubjects, setSavingSubjects] = useState(false);
  const isAdmin = user?.role === "admin";
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const showToast = (type: string, message: string) => {
    if (toastTimer.current) clearTimeout(toastTimer.current);
    setToast({ type, message });
    toastTimer.current = setTimeout(() => setToast(null), 3000);
  };

  useEffect(() => {
    return () => {
      if (toastTimer.current) clearTimeout(toastTimer.current);
    };
  }, []);

  useEffect(() => {
    if (authLoading || !user) return;

    let cancelled = false;
    const controller = new AbortController();
    async function load() {
      const [summaryResult, healthResult] = await Promise.allSettled([
        api.summary(controller.signal),
        api.health(controller.signal),
      ]);
      if (cancelled) return;

      if (summaryResult.status === "fulfilled") {
        setSummary(summaryResult.value);
      } else {
        setError(summaryResult.reason instanceof Error ? summaryResult.reason.message : "Failed to load system summary");
      }

      setApiStatus(
        healthResult.status === "fulfilled" && healthResult.value.status === "alive"
          ? "online"
          : "offline"
      );
    }

    void load();
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [authLoading, user]);

  const schoolId = user?.school_id ?? "";

  useEffect(() => {
    if (authLoading || !isAdmin) return;

    const controller = new AbortController();
    api.listMembers(controller.signal).then(setMembers).catch(() => undefined);
    if (schoolId) {
      api.getClasses(schoolId, controller.signal).then(setSchoolClasses).catch(() => undefined);
    }
    api
      .listInvites(controller.signal)
      .then(setInvites)
      .catch((err) => {
        if (!controller.signal.aborted) {
          setError(err instanceof Error ? err.message : "Failed to load invites");
        }
      });
    return () => controller.abort();
  }, [authLoading, isAdmin, schoolId]);

  const saveSubjects = async (next: string[]) => {
    setSavingSubjects(true);
    try {
      const saved = (await api.setSubjects(next)).subjects;
      setEditedSubjects(saved);
      rememberSubjects(user?.school_id ?? "", saved);
      return true;
    } catch (err) {
      showToast("error", err instanceof Error ? err.message : "Could not save subjects");
      return false;
    } finally {
      setSavingSubjects(false);
    }
  };

  const handleAddSubject = async (e: React.FormEvent) => {
    e.preventDefault();
    const name = newSubject.trim();
    if (!name) return;
    if (await saveSubjects([...subjects, name])) setNewSubject("");
  };

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (newPassword.length < PASSWORD_MIN_LENGTH) {
      showToast("error", `The new password must be at least ${PASSWORD_MIN_LENGTH} characters`);
      return;
    }
    setChangingPassword(true);
    try {
      await api.changePassword(currentPassword, newPassword);
      setCurrentPassword("");
      setNewPassword("");
      showToast("success", "Password changed. Other devices have been signed out.");
    } catch (err) {
      showToast("error", err instanceof Error ? err.message : "Could not change the password");
    } finally {
      setChangingPassword(false);
    }
  };

  const toggleMemberClass = async (member: Member, classId: string) => {
    const next = member.class_ids.includes(classId)
      ? member.class_ids.filter((id) => id !== classId)
      : [...member.class_ids, classId];
    setAssigning(member.id);
    try {
      const updated = await api.setMemberClasses(member.id, next);
      setMembers((prev) => prev.map((m) => (m.id === updated.id ? updated : m)));
    } catch (err) {
      showToast("error", err instanceof Error ? err.message : "Could not update classes");
    } finally {
      setAssigning("");
    }
  };

  const handleResetMember = async (member: Member) => {
    try {
      const { code } = await api.createMemberPasswordReset(member.id);
      setResetLink({
        memberId: member.id,
        url: `${window.location.origin}/reset-password?code=${encodeURIComponent(code)}`,
      });
    } catch (err) {
      showToast("error", err instanceof Error ? err.message : "Could not create a reset link");
    }
  };

  const copyText = async (text: string, message: string) => {
    try {
      await navigator.clipboard.writeText(text);
      showToast("success", message);
    } catch {
      showToast("error", "Could not copy. Select the text and copy it by hand.");
    }
  };

  const inviteLink = (code: string) => `${window.location.origin}/signup?invite=${encodeURIComponent(code)}`;

  const handleCreateInvite = async () => {
    setInviting(true);
    try {
      const invite = await api.createInvite();
      setInvites((prev) => [invite, ...prev]);
      showToast("success", "Invite created. Send the link to your teacher.");
    } catch (err) {
      showToast("error", err instanceof Error ? err.message : "Could not create invite");
    } finally {
      setInviting(false);
    }
  };

  const handleCopyInvite = async (code: string) => {
    try {
      await navigator.clipboard.writeText(inviteLink(code));
      showToast("success", "Invite link copied");
    } catch {
      showToast("error", "Could not copy. Select the code and copy it by hand.");
    }
  };

  const handleRevokeInvite = async (code: string) => {
    try {
      await api.revokeInvite(code);
      setInvites((prev) => prev.filter((i) => i.code !== code));
      showToast("success", "Invite revoked");
    } catch (err) {
      showToast("error", err instanceof Error ? err.message : "Could not revoke invite");
    }
  };

  return (
    <div className="page-shell max-w-3xl">
      {toast && (
        <div role="status" aria-live="polite" aria-atomic="true" className={`toast toast-${toast.type}`}>
          {toast.type === "success" && (
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
            </svg>
          )}
          {toast.message}
        </div>
      )}

      {/* Header */}
      <div className="page-header">
        <div className="page-header-left">
          <h1 className="heading-display text-navy">Settings</h1>
          <p className="body text-text-secondary">
            Manage your account and system preferences
          </p>
        </div>
      </div>

      {error && (
        <div role="alert" aria-live="assertive" className="bg-danger-light border border-danger/20 text-danger px-4 py-3 rounded-lg text-sm">
          {error}
        </div>
      )}

      {/* Account Section */}
      <div className="card">
        <div className="card-body">
          <div className="flex items-center gap-3 mb-5">
            <div className="w-10 h-10 rounded-xl bg-navy/5 flex items-center justify-center">
              <svg className="w-5 h-5 text-navy" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                <circle cx="12" cy="7" r="4" />
              </svg>
            </div>
            <div>
              <h2 className="heading-2 text-navy">Account</h2>
              <p className="caption text-text-muted">Your account information</p>
            </div>
          </div>

          <div className="space-y-0 divide-y divide-border">
            <div className="flex items-center justify-between py-3.5">
              <span className="body text-text-secondary">Email</span>
              <span className="body font-medium text-navy">{user?.email}</span>
            </div>
            <div className="flex items-center justify-between py-3.5">
              <span className="body text-text-secondary">School</span>
              <span className="body font-medium text-navy">{user?.school_name || "Not set"}</span>
            </div>
            <div className="flex items-center justify-between py-3.5">
              <span className="body text-text-secondary">Role</span>
              <span className="badge badge-neutral">{isAdmin ? "School admin" : "Teacher"}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Change password */}
      <div className="card">
        <div className="card-body">
          <div className="mb-4">
            <h2 className="heading-2 text-navy">Change Password</h2>
            <p className="caption text-text-muted">Changing it signs you out on every other device</p>
          </div>
          <form onSubmit={handleChangePassword} className="flex flex-wrap items-end gap-3">
            <div className="input-group flex-1 min-w-[180px]">
              <label className="input-label" htmlFor="current-password">Current password</label>
              <input
                id="current-password"
                type="password"
                autoComplete="current-password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                required
                className="input"
              />
            </div>
            <div className="input-group flex-1 min-w-[180px]">
              <label className="input-label" htmlFor="new-password">New password</label>
              <input
                id="new-password"
                type="password"
                autoComplete="new-password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
                minLength={PASSWORD_MIN_LENGTH}
                className="input"
                placeholder={`At least ${PASSWORD_MIN_LENGTH} characters`}
              />
            </div>
            <button type="submit" disabled={changingPassword} aria-busy={changingPassword} className="btn btn-primary">
              {changingPassword ? "Saving..." : "Change"}
            </button>
          </form>
        </div>
      </div>

      {/* Subjects (admin only) */}
      {isAdmin && (
        <div className="card">
          <div className="card-body">
            <div className="mb-4">
              <h2 className="heading-2 text-navy">Subjects</h2>
              <p className="caption text-text-muted">
                The subjects your teachers can enter scores for. Removing one hides it from the lists; scores
                already entered are kept.
              </p>
            </div>

            <ul className="flex flex-wrap gap-2 mb-4">
              {subjects.map((subject) => (
                <li key={subject} className="badge badge-neutral flex items-center gap-1.5">
                  {subject}
                  {subjects.length > 1 && (
                    <button
                      type="button"
                      onClick={() => saveSubjects(subjects.filter((s) => s !== subject))}
                      disabled={savingSubjects}
                      aria-label={`Remove ${subject}`}
                      className="text-text-muted hover:text-danger transition-colors"
                    >
                      ×
                    </button>
                  )}
                </li>
              ))}
            </ul>

            <form onSubmit={handleAddSubject} className="flex flex-wrap items-end gap-3">
              <div className="input-group flex-1 min-w-[200px]">
                <label className="input-label" htmlFor="new-subject">Add a subject</label>
                <input
                  id="new-subject"
                  value={newSubject}
                  maxLength={40}
                  onChange={(e) => setNewSubject(e.target.value)}
                  className="input"
                  placeholder="e.g. Basic Science"
                  autoComplete="off"
                />
              </div>
              <button type="submit" disabled={savingSubjects || !newSubject.trim()} className="btn btn-primary">
                Add
              </button>
            </form>
          </div>
        </div>
      )}

      {/* Teachers (admin only) */}
      {isAdmin && (
        <div className="card">
          <div className="card-body">
            <div className="flex items-center justify-between gap-3 mb-5">
              <div>
                <h2 className="heading-2 text-navy">Invite a Teacher</h2>
                <p className="caption text-text-muted">
                  Each link lets one teacher join {user?.school_name || "your school"} and expires after 7 days
                </p>
              </div>
              <button
                type="button"
                onClick={handleCreateInvite}
                disabled={inviting}
                aria-busy={inviting}
                className="btn btn-primary"
              >
                {inviting ? "Creating..." : "Create Invite"}
              </button>
            </div>

            {invites.length === 0 ? (
              <p className="caption text-text-muted">No pending invites</p>
            ) : (
              <ul className="space-y-2">
                {invites.map((invite) => (
                  <li key={invite.code} className="flex flex-wrap items-center justify-between gap-3 p-4 bg-surface-elevated rounded-xl">
                    <div className="min-w-0">
                      <div className="font-mono text-sm text-navy break-all">{invite.code}</div>
                      <div className="caption text-text-muted mt-0.5">
                        Expires {new Date(invite.expires_at).toLocaleDateString()}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <button type="button" onClick={() => handleCopyInvite(invite.code)} className="btn btn-secondary btn-sm">
                        Copy Link
                      </button>
                      <button
                        type="button"
                        onClick={() => handleRevokeInvite(invite.code)}
                        aria-label={`Revoke invite ${invite.code}`}
                        className="btn btn-ghost btn-sm text-danger"
                      >
                        Revoke
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}

      {/* People in the school (admin only) */}
      {isAdmin && members.length > 0 && (
        <div className="card">
          <div className="card-body">
            <div className="mb-4">
              <h2 className="heading-2 text-navy">People</h2>
              <p className="caption text-text-muted">
                Tick the classes each teacher teaches; they see only those students, scores and reports. If a
                teacher forgets their password, create a reset link (it works once and expires after 24 hours).
              </p>
            </div>
            <ul className="divide-y divide-border">
              {members.map((member) => (
                <li key={member.id} className="py-3">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="min-w-0">
                      <div className="body font-medium text-navy truncate">{member.email}</div>
                      <div className="caption text-text-muted">
                        {member.role === "admin" ? "School admin" : "Teacher"}
                        {member.id === user?.id && " (you)"}
                      </div>
                    </div>
                    {member.id !== user?.id && (
                      <button type="button" onClick={() => handleResetMember(member)} className="btn btn-secondary btn-sm">
                        Reset Password
                      </button>
                    )}
                  </div>
                  {member.role === "teacher" && (
                    <fieldset className="mt-2" disabled={assigning === member.id}>
                      <legend className="caption text-text-secondary mb-1">Classes</legend>
                      {schoolClasses.length === 0 ? (
                        <p className="caption text-text-muted">Add classes on the Classes page first.</p>
                      ) : (
                        <div className="flex flex-wrap gap-x-4 gap-y-1">
                          {schoolClasses.map((cls) => (
                            <label key={cls.class_id} className="flex items-center gap-1.5 body-sm text-navy">
                              <input
                                type="checkbox"
                                checked={member.class_ids.includes(cls.class_id)}
                                onChange={() => toggleMemberClass(member, cls.class_id)}
                              />
                              {cls.label}
                            </label>
                          ))}
                        </div>
                      )}
                      {schoolClasses.length > 0 && member.class_ids.length === 0 && (
                        <p className="caption text-danger mt-1">No classes yet, so this teacher sees no students.</p>
                      )}
                    </fieldset>
                  )}
                  {resetLink?.memberId === member.id && (
                    <div role="status" className="mt-3 p-3 bg-surface-elevated rounded-lg">
                      <div className="caption text-text-secondary mb-1">
                        Send this link to {member.email}. It is shown only once.
                      </div>
                      <div className="flex flex-wrap items-center gap-2">
                        <code className="font-mono text-xs text-navy break-all flex-1 min-w-0">{resetLink.url}</code>
                        <button
                          type="button"
                          onClick={() => copyText(resetLink.url, "Reset link copied")}
                          className="btn btn-primary btn-sm"
                        >
                          Copy Link
                        </button>
                      </div>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {/* System */}
      <div className="card">
        <div className="card-body">
          <div className="flex items-center gap-3 mb-5">
            <div className="w-10 h-10 rounded-xl bg-info/10 flex items-center justify-center">
              <svg className="w-5 h-5 text-info" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
              </svg>
            </div>
            <div>
              <h2 className="heading-2 text-navy">System</h2>
              <p className="caption text-text-muted">Connection and school totals</p>
            </div>
          </div>

          <div className="space-y-4">
            {/* API Status */}
            <div className="flex items-center justify-between p-4 bg-surface-elevated rounded-xl">
              <div>
                <h3 className="body font-medium text-navy">Connection</h3>
                <p className="caption text-text-muted mt-0.5">
                  Whether GradePulse can reach its server
                </p>
              </div>
               <span className={`flex items-center gap-2 badge ${apiStatus === "online" ? "badge-success" : apiStatus === "offline" ? "badge-danger" : "badge-neutral"}`}>
                 <span className={`status-dot ${apiStatus === "online" ? "active" : ""}`} />
                 {apiStatus === "online" ? "Connected" : apiStatus === "offline" ? "Unavailable" : "Checking"}
               </span>
            </div>

            {/* Student Count */}
            {summary && (
              <div className="flex items-center justify-between p-4 bg-surface-elevated rounded-xl">
                <div>
                  <h3 className="body font-medium text-navy">Students</h3>
                  <p className="caption text-text-muted mt-0.5">
                    In your school
                  </p>
                </div>
                <span className="heading-2 text-navy">{summary.student_count}</span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Danger Zone */}
      <div className="card border-danger/20">
        <div className="card-body">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-xl bg-danger/10 flex items-center justify-center">
              <svg className="w-5 h-5 text-danger" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                <polyline points="16 17 21 12 16 7" />
                <line x1="21" y1="12" x2="9" y2="12" />
              </svg>
            </div>
            <div>
              <h2 className="heading-2 text-danger">Danger Zone</h2>
              <p className="caption text-text-muted">Account actions</p>
            </div>
          </div>

          <div className="flex items-center justify-between p-4 bg-danger/[0.03] rounded-xl border border-danger/10">
            <div>
              <h3 className="body font-medium text-navy">Sign Out</h3>
              <p className="caption text-text-muted mt-0.5">
                End your session and return to login
              </p>
            </div>
            <button
              onClick={logout}
              className="btn btn-danger"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                <polyline points="16 17 21 12 16 7" />
                <line x1="21" y1="12" x2="9" y2="12" />
              </svg>
              Sign Out
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
