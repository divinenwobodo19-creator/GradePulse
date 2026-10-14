"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { SchoolClass, Student } from "@/lib/types";
import { getStudentClassId } from "@/lib/types";

export default function ClassesPage() {
  const { user, loading: authLoading } = useAuth();
  const schoolId = user?.school_id ?? "";
  const isAdmin = user?.role === "admin";
  const [classes, setClasses] = useState<SchoolClass[]>([]);
  const [students, setStudents] = useState<Student[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [toast, setToast] = useState<{ type: string; message: string } | null>(null);
  const [newLabel, setNewLabel] = useState("");
  const [creating, setCreating] = useState(false);
  const [renaming, setRenaming] = useState<{ classId: string; label: string } | null>(null);
  const [busyClass, setBusyClass] = useState("");
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
      try {
        const [nextClasses, nextStudents] = await Promise.all([
          schoolId ? api.getClasses(schoolId, controller.signal) : Promise.resolve([]),
          api.getStudents(undefined, undefined, controller.signal),
        ]);
        if (!cancelled) {
          setClasses(nextClasses);
          setStudents(nextStudents);
        }
      } catch (err) {
        if (!cancelled && !(err instanceof Error && err.name === "AbortError")) {
          setError(err instanceof Error ? err.message : "Failed to load classes");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void load();
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [authLoading, user, schoolId]);

  const studentCount = (classId: string) => students.filter((s) => getStudentClassId(s) === classId).length;
  const unassigned = students.filter((s) => !getStudentClassId(s)).length;

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    const label = newLabel.trim();
    if (!label) return;
    setCreating(true);
    try {
      const created = await api.createClass(schoolId, label);
      setClasses((prev) => [...prev, created]);
      setNewLabel("");
      showToast("success", `Added ${created.label}`);
    } catch (err) {
      showToast("error", err instanceof Error ? err.message : "Could not add class");
    } finally {
      setCreating(false);
    }
  };

  const handleRename = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!renaming) return;
    const label = renaming.label.trim();
    if (!label) return;
    setBusyClass(renaming.classId);
    try {
      const updated = await api.updateClass(schoolId, renaming.classId, label);
      setClasses((prev) => prev.map((c) => (c.class_id === updated.class_id ? updated : c)));
      setRenaming(null);
      showToast("success", `Renamed to ${updated.label}`);
    } catch (err) {
      showToast("error", err instanceof Error ? err.message : "Could not rename class");
    } finally {
      setBusyClass("");
    }
  };

  const handleDelete = async (cls: SchoolClass) => {
    const count = studentCount(cls.class_id);
    const warning = count > 0
      ? `Delete ${cls.label}? Its ${count} student${count !== 1 ? "s" : ""} will be removed from your lists too. Move them to another class first if you want to keep them.`
      : `Delete ${cls.label}?`;
    if (!confirm(warning)) return;
    setBusyClass(cls.class_id);
    try {
      await api.deleteClass(schoolId, cls.class_id);
      setClasses((prev) => prev.filter((c) => c.class_id !== cls.class_id));
      setStudents((prev) => prev.filter((s) => getStudentClassId(s) !== cls.class_id));
      showToast("success", `Deleted ${cls.label}`);
    } catch (err) {
      showToast("error", err instanceof Error ? err.message : "Could not delete class");
    } finally {
      setBusyClass("");
    }
  };

  if (authLoading || loading) {
    return (
      <div role="status" aria-live="polite" className="space-y-6">
        <div className="h-8 w-48 skeleton" />
        <div className="h-20 skeleton" />
        <div className="h-64 skeleton" />
      </div>
    );
  }

  return (
    <div className="page-shell max-w-3xl">
      {toast && (
        <div role="status" aria-live="polite" aria-atomic="true" className={`toast toast-${toast.type}`}>
          {toast.message}
        </div>
      )}

      <div className="page-header">
        <div className="page-header-left">
          <h1 className="heading-display text-navy">Classes</h1>
          <p className="body text-text-secondary">
            {isAdmin
              ? `Set up the classes in ${user?.school_name || "your school"}, for example JSS1A or SS2 Science`
              : "The classes you teach. Your school admin manages classes and who teaches them."}
          </p>
        </div>
      </div>

      {error && (
        <div role="alert" aria-live="assertive" className="bg-danger-light border border-danger/20 text-danger px-4 py-3 rounded-lg text-sm">
          {error}
        </div>
      )}

      {isAdmin && (
      <div className="card">
        <div className="card-body">
          <form onSubmit={handleCreate} className="flex flex-wrap items-end gap-3">
            <div className="input-group flex-1 min-w-[200px]">
              <label className="input-label" htmlFor="new-class">New class</label>
              <input
                id="new-class"
                value={newLabel}
                maxLength={40}
                onChange={(e) => setNewLabel(e.target.value)}
                className="input"
                placeholder="e.g. JSS1A"
                autoComplete="off"
              />
            </div>
            <button type="submit" disabled={creating || !newLabel.trim()} aria-busy={creating} className="btn btn-primary">
              {creating ? "Adding..." : "Add Class"}
            </button>
          </form>
        </div>
      </div>
      )}

      <div className="table-wrapper">
        {classes.length === 0 ? (
          <div className="empty-state">
            <h3 className="heading-3 text-navy mb-1">No classes yet</h3>
            <p className="body-sm text-text-muted">
              {isAdmin
                ? "Add your first class above, then put students in it."
                : "You have not been given a class yet. Ask your school admin to add you in Settings → People."}
            </p>
          </div>
        ) : (
          <table className="data-table">
            <caption className="sr-only">Classes in your school</caption>
            <thead>
              <tr>
                <th scope="col">Class</th>
                <th scope="col" className="text-right">Students</th>
                <th scope="col" className="text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {classes.map((cls) => (
                <tr key={cls.class_id}>
                  <td>
                    {renaming?.classId === cls.class_id ? (
                      <form onSubmit={handleRename} className="flex items-center gap-2">
                        <input
                          aria-label={`New name for ${cls.label}`}
                          value={renaming.label}
                          maxLength={40}
                          onChange={(e) => setRenaming({ classId: cls.class_id, label: e.target.value })}
                          className="input w-40"
                          autoFocus
                        />
                        <button type="submit" disabled={busyClass === cls.class_id || !renaming.label.trim()} className="btn btn-primary btn-sm">
                          Save
                        </button>
                        <button type="button" onClick={() => setRenaming(null)} className="btn btn-ghost btn-sm">
                          Cancel
                        </button>
                      </form>
                    ) : (
                      <span className="font-medium text-navy">{cls.label}</span>
                    )}
                  </td>
                  <td className="text-right font-mono text-sm text-text-secondary">{studentCount(cls.class_id)}</td>
                  <td className="text-right">
                    <div className="flex items-center justify-end gap-3">
                      {isAdmin && (
                      <button
                        type="button"
                        onClick={() => setRenaming({ classId: cls.class_id, label: cls.label })}
                        aria-label={`Rename ${cls.label}`}
                        className="text-xs text-navy hover:text-gold transition-colors font-medium"
                      >
                        Rename
                      </button>
                      )}
                      {isAdmin && (
                        <button
                          type="button"
                          onClick={() => handleDelete(cls)}
                          disabled={busyClass === cls.class_id}
                          aria-label={`Delete ${cls.label}`}
                          className="text-xs text-danger hover:text-danger/80 transition-colors font-medium"
                        >
                          Delete
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {isAdmin && unassigned > 0 && (
        <p className="caption text-text-muted">
          {unassigned} student{unassigned !== 1 ? "s are" : " is"} not in any class. Open <strong>Students</strong> and use Edit to place them.
        </p>
      )}
    </div>
  );
}
