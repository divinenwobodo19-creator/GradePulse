"use client";

import { useEffect, useState } from "react";
import { api } from "./api";
import { useAuth } from "./auth";
import { SUBJECTS } from "./types";

const FALLBACK: string[] = [...SUBJECTS];

// Each school keeps its own subject list (edited by its admin in Settings).
// Cached per school so moving between pages does not flash the fallback.
const cache = new Map<string, string[]>();

export function rememberSubjects(schoolId: string, subjects: string[]) {
  if (schoolId && subjects.length > 0) cache.set(schoolId, subjects);
}

// Always returns at least one subject.
export function useSubjects(): string[] {
  const { user } = useAuth();
  const schoolId = user?.school_id ?? "";
  const [loaded, setLoaded] = useState<{ schoolId: string; subjects: string[] } | null>(null);

  useEffect(() => {
    if (!schoolId) return;
    const controller = new AbortController();
    api
      .getSubjects(controller.signal)
      .then(({ subjects }) => {
        rememberSubjects(schoolId, subjects);
        setLoaded({ schoolId, subjects });
      })
      .catch(() => undefined);
    return () => controller.abort();
  }, [schoolId]);

  const subjects = loaded?.schoolId === schoolId ? loaded.subjects : cache.get(schoolId);
  return subjects && subjects.length > 0 ? subjects : FALLBACK;
}

// The subject a page should show: the user's pick while it is still on the
// school's list, otherwise the first subject.
export function activeSubject(picked: string, subjects: string[]): string {
  return subjects.includes(picked) ? picked : subjects[0];
}
