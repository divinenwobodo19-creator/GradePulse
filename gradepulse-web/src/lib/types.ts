export interface User {
  id: string;
  email: string;
  school_id: string;
  school_name: string;
}

export interface AuthResponse {
  id: string;
  email: string;
  school_id: string;
  school_name: string;
  token: string;
}

export interface School {
  school_id: string;
  name: string;
  classes: SchoolClass[];
}

export interface SchoolClass {
  class_id: string;
  label: string;
  grade_level: string;
  arm: string;
}

export interface Student {
  student_id: string;
  name: string;
  performance_score: number;
  current_topic: string;
  class_id?: string | null;
  metadata?: Record<string, unknown>;
  grade_history?: Record<string, number[]>;
}

export function getStudentClassId(student: Student): string | null {
  if (student.class_id) return student.class_id;
  const metadataClassId = student.metadata?.class_id;
  return typeof metadataClassId === "string" ? metadataClassId : null;
}

export interface Content {
  content_id: string;
  title: string;
  topic: string;
  difficulty: number;
  content_type: string;
}

export interface BrainSummary {
  student_count: number;
  content_count: number;
  total_sessions: number;
  model_type: string;
  current_alpha: number;
  current_gamma: number;
  cumulative_regret: number;
  last_neural_score: number | null;
}

export interface TriageStudent {
  student_id: string;
  name: string;
  predicted_score: number;
  average_score?: number | null;
  attempts: number;
}

export interface TriageTier {
  students: TriageStudent[];
  count: number;
  recommended_difficulty: number;
  note: string;
}

export interface TriageResult {
  subject: string;
  total_students: number;
  tiers: Record<string, TriageTier>;
  scope: string;
}

export interface RewardResult {
  reward: number;
}

export type GradeLevel =
  | "A1"  // 75-100
  | "B2"  // 70-74
  | "B3"  // 65-69
  | "C4"  // 60-64
  | "C5"  // 55-59
  | "C6"  // 50-54
  | "D7"  // 45-49
  | "E8"  // 40-44
  | "F9"; // 0-39

export function scoreToGrade(score: number): GradeLevel {
  if (score >= 75) return "A1";
  if (score >= 70) return "B2";
  if (score >= 65) return "B3";
  if (score >= 60) return "C4";
  if (score >= 55) return "C5";
  if (score >= 50) return "C6";
  if (score >= 45) return "D7";
  if (score >= 40) return "E8";
  return "F9";
}

export function scoreToPercentage(score: number): number {
  return Math.round(score * 100);
}

export const GRADE_COLORS: Record<GradeLevel, string> = {
  A1: "bg-emerald-100 text-emerald-800 border-emerald-200",
  B2: "bg-green-100 text-green-800 border-green-200",
  B3: "bg-lime-100 text-lime-800 border-lime-200",
  C4: "bg-yellow-100 text-yellow-800 border-yellow-200",
  C5: "bg-amber-100 text-amber-800 border-amber-200",
  C6: "bg-orange-100 text-orange-800 border-orange-200",
  D7: "bg-red-100 text-red-800 border-red-200",
  E8: "bg-rose-100 text-rose-800 border-rose-200",
  F9: "bg-red-200 text-red-900 border-red-300",
};

export const TIER_LABELS: Record<string, { label: string; color: string; badgeClass: string; description: string }> = {
  ahead: {
    label: "Ahead",
    color: "#10b981",
    badgeClass: "badge-success",
    description: "Scored 75%+ (A1). Give advanced materials.",
  },
  on_track: {
    label: "On Track",
    color: "#3b82f6",
    badgeClass: "badge-info",
    description: "Scored 40-74% (E8-B2). Standard curriculum.",
  },
  remediation: {
    label: "Needs Intervention",
    color: "#ef4444",
    badgeClass: "badge-danger",
    description: "Below 40% (F9). Extra practice needed.",
  },
};

export const SUBJECTS = ["MATH", "SCIENCE", "ENGLISH", "HISTORY"] as const;
export type Subject = typeof SUBJECTS[number];
