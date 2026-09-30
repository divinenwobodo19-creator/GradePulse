import type {
  BrainSummary,
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
    if (body) headers["Content-Type"] = "application/json";

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
        body: body ? JSON.stringify(body) : undefined,
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
  async signup(email: string, password: string, schoolName: string) {
    const data = await this.request<{
      id: string;
      email: string;
      school_id: string;
      school_name: string;
      token: string;
    }>("POST", "/auth/signup", { email, password, school_name: schoolName });
    this.setToken(data.token);
    return data;
  }

  async login(email: string, password: string) {
    const data = await this.request<{
      id: string;
      email: string;
      school_id: string;
      school_name: string;
      token: string;
    }>("POST", "/auth/login", { email, password });
    this.setToken(data.token);
    return data;
  }

  async me() {
    return this.request<{
      id: string;
      email: string;
      school_id: string;
      school_name: string;
    }>("GET", "/auth/me");
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

  // ─── Classes ───
  async getClasses(schoolId: string, signal?: AbortSignal) {
    return this.request<
      { class_id: string; label: string; grade_level: string; arm: string }[]
    >("GET", `/classes/${schoolId}`, undefined, signal);
  }

  async createClass(schoolId: string, label: string) {
    return this.request<{
      class_id: string;
      label: string;
      grade_level: string;
      arm: string;
    }>(`POST`, `/classes/${schoolId}`, { label });
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

  async bulkUpdate(
    entries: { student_id: string; subject: string; score: number }[]
  ) {
    return this.request<{ processed: number }>("POST", "/bulk-update", {
      entries,
    });
  }

  async triage(subject: string, signal?: AbortSignal) {
    return this.request<TriageResult>("POST", "/triage", { subject }, signal);
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
    }>("GET", "/health", undefined, signal);
  }
}

export const api = new ApiClient();
