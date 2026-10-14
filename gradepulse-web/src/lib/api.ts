import type { ScoreRow } from "./reports";
import type { StudentScore } from "@/components/ScoreHistory";
import type {
  AuthResponse,
  BrainSummary,
  IngestResult,
  Invite,
  Member,
  PasswordResetLink,
  SchoolClass,
  Student,
  TriageResult,
} from "./types";

const configuredApiUrl = process.env.NEXT_PUBLIC_API_URL?.trim();
const API_URL = configuredApiUrl ? configuredApiUrl.replace(/\/+$/, "") : "";
const API_PREFIX = API_URL ? "" : "/api";
const REQUEST_TIMEOUT_MS = Number(
  process.env.NEXT_PUBLIC_GRADEPULSE_API_TIMEOUT_MS || 15000
);

export const UNAUTHORIZED_EVENT = "gradepulse:unauthorized";

const RATE_LIMIT_MESSAGE =
  "Too many attempts just now. Wait about a minute, then try again.";
const FORBIDDEN_MESSAGE =
  "You don't have access to that. If this keeps happening, your account may not be linked to the right school.";

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, detail: string) {
    super(ApiError.describe(status, detail));
    this.name = "ApiError";
    this.status = status;
  }

  private static describe(status: number, detail: string): string {
    if (status === 429) return detail || RATE_LIMIT_MESSAGE;
    if (status === 403) return FORBIDDEN_MESSAGE;
    return detail || `Request failed (${status}). Please try again.`;
  }
}

export interface Recommendation {
  content_id: string;
  title: string;
  topic: string;
  difficulty: number;
  content_type: string;
  times_recommended?: number;
  times_rewarded?: number;
  avg_reward?: number;
}

class ApiClient {
  private token: string | null = null;

  setToken(token: string | null) {
    this.token = token;
    if (typeof window !== "undefined") {
      if (token) {
        localStorage.setItem("gradepulse_token", token);
      } else {
        localStorage.removeItem("gradepulse_token");
      }
    }
  }

  getToken(): string | null {
    if (this.token) return this.token;
    if (typeof window !== "undefined") {
      return localStorage.getItem("gradepulse_token");
    }
    return null;
  }

  private async request<T>(
    method: string,
    path: string,
    body?: unknown,
    signal?: AbortSignal
  ): Promise<T> {
    const headers: Record<string, string> = {};
    const token = this.getToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
    // A FormData body (file upload) sets its own multipart Content-Type.
    const isForm = typeof FormData !== "undefined" && body instanceof FormData;
    if (body && !isForm) headers["Content-Type"] = "application/json";

    const controller = new AbortController();
    let timedOut = false;
    const timeout = setTimeout(() => {
      timedOut = true;
      controller.abort();
    }, REQUEST_TIMEOUT_MS);
    const abortRequest = () => controller.abort();

    if (signal) {
      if (signal.aborted) controller.abort();
      else signal.addEventListener("abort", abortRequest, { once: true });
    }

    try {
      const res = await fetch(`${API_URL}${API_PREFIX}${path}`, {
        method,
        headers,
        body: isForm ? (body as FormData) : body ? JSON.stringify(body) : undefined,
        signal: controller.signal,
      });

      if (res.status === 401 && typeof window !== "undefined") {
        window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
      }

      if (!res.ok) {
        const body = await res.json().catch(() => null);
        const detail =
          typeof body?.detail === "string" ? body.detail : res.statusText;
        throw new ApiError(res.status, detail);
      }

      return res.json();
    } catch (error) {
      if (timedOut) throw new Error("The request timed out. Please try again.");
      throw error;
    } finally {
      clearTimeout(timeout);
      signal?.removeEventListener("abort", abortRequest);
    }
  }

  // ─── Auth ───
  // With an invite code the account joins that school as a teacher and
  // schoolName is ignored; without one it creates a new school as its admin.
  async signup(email: string, password: string, schoolName: string, inviteCode?: string) {
    const data = await this.request<AuthResponse>("POST", "/auth/signup", {
      email,
      password,
      school_name: schoolName,
      ...(inviteCode ? { invite_code: inviteCode } : {}),
    });
    this.setToken(data.token);
    return data;
  }

  async login(email: string, password: string) {
    const data = await this.request<AuthResponse>("POST", "/auth/login", { email, password });
    this.setToken(data.token);
    return data;
  }

  async me() {
    return this.request<Omit<AuthResponse, "token">>("GET", "/auth/me");
  }

  // ─── Passwords ───
  // Signs every other session out; this one continues on the new token.
  async changePassword(currentPassword: string, newPassword: string) {
    const data = await this.request<AuthResponse>("POST", "/auth/change-password", {
      current_password: currentPassword,
      new_password: newPassword,
    });
    this.setToken(data.token);
    return data;
  }

  async resetPassword(code: string, newPassword: string) {
    return this.request<{ status: string }>("POST", "/auth/reset-password", {
      code,
      new_password: newPassword,
    });
  }

  // ─── School members (admin only) ───
  async listMembers(signal?: AbortSignal) {
    return this.request<Member[]>("GET", "/members", undefined, signal);
  }

  // A single-use reset code for one teacher. It is only returned here, once.
  async createMemberPasswordReset(userId: string) {
    return this.request<PasswordResetLink>("POST", `/members/${encodeURIComponent(userId)}/password-reset`);
  }

  // ─── Invites (school admin only) ───
  async createInvite() {
    return this.request<Invite>("POST", "/invites");
  }

  async listInvites(signal?: AbortSignal) {
    return this.request<Invite[]>("GET", "/invites", undefined, signal);
  }

  async revokeInvite(code: string) {
    return this.request<{ status: string }>("DELETE", `/invites/${encodeURIComponent(code)}`);
  }

  logout() {
    this.setToken(null);
  }

  // ─── Schools ───
  async getSchools(signal?: AbortSignal) {
    return this.request<
      { school_id: string; name: string; classes: SchoolClass[] }[]
    >("GET", "/schools", undefined, signal);
  }

  async createSchool(name: string) {
    return this.request<{ school_id: string; name: string }>(
      "POST",
      "/schools",
      { name }
    );
  }

  // ─── Subjects (per school) ───
  async getSubjects(signal?: AbortSignal) {
    return this.request<{ subjects: string[] }>("GET", "/subjects", undefined, signal);
  }

  // Admin only. Replaces the school's whole list.
  async setSubjects(subjects: string[]) {
    return this.request<{ subjects: string[] }>("PUT", "/subjects", { subjects });
  }

  // ─── Classes ───
  async getClasses(schoolId: string, signal?: AbortSignal) {
    return this.request<
      { class_id: string; label: string; grade_level: string; arm: string }[]
    >("GET", `/classes/${schoolId}`, undefined, signal);
  }

  // Every recorded test for one student, oldest first.
  async getStudentScores(studentId: string, signal?: AbortSignal) {
    return this.request<StudentScore[]>(
      "GET",
      `/students/${encodeURIComponent(studentId)}/scores`,
      undefined,
      signal
    );
  }

  async createClass(schoolId: string, label: string) {
    return this.request<{
      class_id: string;
      label: string;
      grade_level: string;
      arm: string;
    }>(`POST`, `/classes/${schoolId}`, { label });
  }

  async updateClass(schoolId: string, classId: string, label: string) {
    return this.request<SchoolClass>("PUT", `/classes/${schoolId}/${classId}`, { label });
  }

  // Admin only. Archives the students in the class as well.
  async deleteClass(schoolId: string, classId: string) {
    return this.request<{ status: string }>("DELETE", `/classes/${schoolId}/${classId}`);
  }

  // ─── Students ───
  async getStudents(schoolId?: string, classId?: string, signal?: AbortSignal) {
    const params = new URLSearchParams();
    if (schoolId) params.set("school_id", schoolId);
    if (classId) params.set("class_id", classId);
    const qs = params.toString();
    return this.request<Student[]>(
      "GET",
      `/students${qs ? `?${qs}` : ""}`,
      undefined,
      signal
    );
  }

  async addStudent(data: {
    student_id: string;
    name: string;
    current_topic?: string;
    metadata?: Record<string, unknown>;
  }) {
    return this.request<{ student_id: string; name: string }>(
      "POST",
      "/students",
      data
    );
  }

  async updateStudent(
    studentId: string,
    data: { name?: string; current_topic?: string; class_id?: string }
  ) {
    return this.request<{ student_id: string }>(
      "PUT",
      `/students/${studentId}`,
      data
    );
  }

  async deleteStudent(studentId: string) {
    return this.request<{ status: string }>(
      "DELETE",
      `/students/${studentId}`
    );
  }

  // Upload a class list (CSV or Excel). With dryRun the file is only checked.
  async importRoster(file: File, dryRun: boolean) {
    const form = new FormData();
    form.append("file", file);
    form.append("type", "students");
    form.append("dry_run", dryRun ? "true" : "false");
    return this.request<IngestResult>("POST", "/ingest", form);
  }

  // Every recorded score in the school (or one class), oldest first.
  async getSchoolScores(classId?: string, signal?: AbortSignal) {
    const qs = classId ? `?class_id=${encodeURIComponent(classId)}` : "";
    return this.request<ScoreRow[]>("GET", `/scores${qs}`, undefined, signal);
  }

  // ─── Content ───
  async addContent(data: {
    content_id: string;
    title: string;
    topic: string;
    difficulty: number;
    content_type: string;
  }) {
    return this.request<{ content_id: string }>("POST", "/content", data);
  }

  // ─── Brain Operations ───
  // /recommend always returns a JSON array, including at top_n=1.
  async recommend(studentId: string, topN: number = 3, signal?: AbortSignal) {
    return this.request<Recommendation[]>(
      "POST",
      "/recommend",
      { student_id: studentId, top_n: topN },
      signal
    );
  }

  // One sitting of a test. Re-sending the same student, subject, date and
  // label corrects the earlier score instead of adding another.
  async bulkUpdate(
    entries: { student_id: string; subject: string; score: number }[],
    sitting: { assessedOn?: string; label?: string } = {}
  ) {
    return this.request<{ processed: number }>("POST", "/bulk-update", {
      entries,
      ...(sitting.assessedOn ? { assessed_on: sitting.assessedOn } : {}),
      ...(sitting.label ? { label: sitting.label } : {}),
    });
  }

  async triage(subject: string, signal?: AbortSignal, classId?: string) {
    return this.request<TriageResult>(
      "POST",
      "/triage",
      { subject, ...(classId ? { class_id: classId } : {}) },
      signal
    );
  }

  async summary(signal?: AbortSignal) {
    return this.request<BrainSummary>("GET", "/summary", undefined, signal);
  }

  async calculateReward(data: {
    before_score: number;
    after_score: number;
    completed: boolean;
    time_spent_ratio: number;
    engaged: boolean;
    churned: boolean;
  }) {
    return this.request<{ reward: number }>("POST", "/calculate-reward", data);
  }

  async save() {
    return this.request<{ status: string }>("POST", "/save");
  }

  async health(signal?: AbortSignal) {
    return this.request<{
      status: string;
      engine: string;
      version: string;
      // Features this server has switched on or off.
      features?: { recommendations?: boolean };
    }>("GET", "/health", undefined, signal);
  }
}

export const api = new ApiClient();
