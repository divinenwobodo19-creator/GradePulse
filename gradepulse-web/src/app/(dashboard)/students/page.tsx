"use client";

import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import type { Student, School, SchoolClass } from "@/lib/types";
import { SUBJECTS } from "@/lib/types";

export default function StudentsPage() {
  const [students, setStudents] = useState<Student[]>([]);
  const [schools, setSchools] = useState<School[]>([]);
  const [classes, setClasses] = useState<SchoolClass[]>([]);
  const [selectedSchool, setSelectedSchool] = useState("");
  const [selectedClass, setSelectedClass] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [toast, setToast] = useState<{ type: string; message: string } | null>(null);
  const [search, setSearch] = useState("");

  // Modal state
  const [showModal, setShowModal] = useState(false);
  const [newId, setNewId] = useState("");
  const [newName, setNewName] = useState("");
  const [newTopic, setNewTopic] = useState("MATH");
  const [adding, setAdding] = useState(false);

  const showToast = (type: string, message: string) => {
    setToast({ type, message });
    setTimeout(() => setToast(null), 3000);
  };

  const loadStudents = useCallback(async () => {
    try {
      const data = await api.getStudents(selectedSchool || undefined, selectedClass || undefined);
      setStudents(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load students");
    }
  }, [selectedSchool, selectedClass]);

  useEffect(() => {
    async function init() {
      try {
        const s = await api.getSchools();
        setSchools(s);
        if (s.length > 0) {
          setSelectedSchool(s[0].school_id);
          const c = await api.getClasses(s[0].school_id);
          setClasses(c);
        }
      } catch {
        // Schools may not exist yet
      } finally {
        setLoading(false);
      }
    }
    init();
  }, []);

  useEffect(() => {
    if (selectedSchool) {
      api.getClasses(selectedSchool).then(setClasses).catch(() => setClasses([]));
      setSelectedClass("");
    }
  }, [selectedSchool]);

  useEffect(() => {
    loadStudents();
  }, [loadStudents]);

  const resetForm = () => {
    setNewId("");
    setNewName("");
    setNewTopic("MATH");
    setShowModal(false);
  };

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newId.trim() || !newName.trim()) return;
    setAdding(true);
    try {
      await api.addStudent({
        student_id: newId.trim(),
        name: newName.trim(),
        school_id: selectedSchool || undefined,
        class_id: selectedClass || undefined,
        current_topic: newTopic,
      });
      showToast("success", `Added ${newName.trim()} successfully`);
      resetForm();
      loadStudents();
    } catch (err) {
      showToast("error", err instanceof Error ? err.message : "Failed to add student");
    } finally {
      setAdding(false);
    }
  };

  const handleDelete = async (id: string, name: string) => {
    if (!confirm(`Delete ${name}? This cannot be undone.`)) return;
    try {
      await api.deleteStudent(id);
      showToast("success", `Deleted ${name}`);
      loadStudents();
    } catch (err) {
      showToast("error", err instanceof Error ? err.message : "Failed to delete");
    }
  };

  const filtered = students.filter((s) =>
    s.name.toLowerCase().includes(search.toLowerCase()) ||
    s.student_id.toLowerCase().includes(search.toLowerCase())
  );

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-48 skeleton" />
        <div className="h-10 w-full skeleton" />
        <div className="h-64 skeleton" />
      </div>
    );
  }

  return (
    <div className="page-shell">
      {toast && (
        <div className={`toast toast-${toast.type}`}>
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
          <h1 className="heading-display text-navy">Students</h1>
          <p className="body text-text-secondary">
            Manage your student roster and track performance
          </p>
        </div>
        <button
          onClick={() => setShowModal(true)}
          className="btn btn-primary"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          Add Student
        </button>
      </div>

      {/* Filters & Search */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[200px] max-w-sm">
          <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="input pl-10"
            placeholder="Search students..."
          />
        </div>

        <select
          value={selectedSchool}
          onChange={(e) => setSelectedSchool(e.target.value)}
          className="input select w-auto min-w-[160px]"
        >
          <option value="">All Schools</option>
          {schools.map((s) => (
            <option key={s.school_id} value={s.school_id}>{s.name}</option>
          ))}
        </select>

        <select
          value={selectedClass}
          onChange={(e) => setSelectedClass(e.target.value)}
          className="input select w-auto min-w-[160px]"
        >
          <option value="">All Classes</option>
          {classes.map((c) => (
            <option key={c.class_id} value={c.class_id}>{c.label}</option>
          ))}
        </select>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-danger-light border border-danger/20 text-danger px-4 py-3 rounded-lg text-sm">
          {error}
        </div>
      )}

      {/* Student Table */}
      <div className="table-wrapper">
        {filtered.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">
              <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
                <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                <circle cx="9" cy="7" r="4" />
                <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
                <path d="M16 3.13a4 4 0 0 1 0 7.75" />
              </svg>
            </div>
            <h3 className="heading-3 text-navy mb-1">No students found</h3>
            <p className="body-sm text-text-muted mb-4">
              {search ? "Try a different search term" : "Add your first student to get started"}
            </p>
            {!search && (
              <button onClick={() => setShowModal(true)} className="btn btn-primary btn-sm">
                Add Student
              </button>
            )}
          </div>
        ) : (
          <>
            <div className="px-5 py-3 border-b border-border flex items-center justify-between">
              <span className="body-sm text-text-secondary">
                {filtered.length} student{filtered.length !== 1 ? "s" : ""}
              </span>
            </div>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Student</th>
                  <th>ID</th>
                  <th className="text-right">Score</th>
                  <th>Topic</th>
                  <th className="text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((s) => (
                  <tr key={s.student_id}>
                    <td>
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-full bg-navy/5 flex items-center justify-center text-navy text-xs font-semibold shrink-0">
                          {s.name.charAt(0)}
                        </div>
                        <span className="font-medium text-navy">{s.name}</span>
                      </div>
                    </td>
                    <td className="font-mono text-xs text-text-muted">{s.student_id}</td>
                    <td className="text-right">
                      <span className="badge badge-info font-mono">
                        {Math.round(s.performance_score * 100)}%
                      </span>
                    </td>
                    <td className="text-text-secondary">{s.current_topic}</td>
                    <td className="text-right">
                      <button
                        onClick={() => handleDelete(s.student_id, s.name)}
                        className="text-xs text-danger hover:text-danger/80 transition-colors font-medium"
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </div>

      {/* Add Student Modal */}
      {showModal && (
        <div className="modal-overlay" onClick={() => !adding && resetForm()}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="px-6 py-5 border-b border-border">
              <div className="flex items-center justify-between">
                <h2 className="heading-2 text-navy">Add New Student</h2>
                <button
                  onClick={() => !adding && resetForm()}
                  className="text-text-muted hover:text-text-primary transition-colors"
                >
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                    <line x1="18" y1="6" x2="6" y2="18" />
                    <line x1="6" y1="6" x2="18" y2="18" />
                  </svg>
                </button>
              </div>
            </div>

            <form onSubmit={handleAdd} className="px-6 py-5 space-y-4">
              <div className="input-group">
                <label className="input-label">Student ID</label>
                <input
                  value={newId}
                  onChange={(e) => setNewId(e.target.value)}
                  className="input"
                  placeholder="e.g. S001, STU005"
                  required
                />
                <span className="input-hint">Unique identifier for this student</span>
              </div>

              <div className="input-group">
                <label className="input-label">Full Name</label>
                <input
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  className="input"
                  placeholder="e.g. Adebayo Okonkwo"
                  required
                />
              </div>

              <div className="input-group">
                <label className="input-label">Primary Subject</label>
                <select
                  value={newTopic}
                  onChange={(e) => setNewTopic(e.target.value)}
                  className="input select"
                >
                  {SUBJECTS.map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
              </div>

              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={resetForm}
                  disabled={adding}
                  className="btn btn-ghost"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={adding || !newId.trim() || !newName.trim()}
                  className="btn btn-primary"
                >
                  {adding ? (
                    <>
                      <div className="spinner spinner-sm" style={{ borderTopColor: 'var(--color-navy)' }} />
                      Adding...
                    </>
                  ) : (
                    "Add Student"
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
