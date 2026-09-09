/** Typed client for the FastAPI service. */
const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export type RuleStatus =
  | "PASS" | "WARNING" | "BLOCK" | "NOT_APPLICABLE" | "REVIEW_REQUIRED";

export interface SourceReference {
  citation?: string; citation_uid?: string; instrument?: string; page?: number;
  reference?: string; document?: string; file_hash?: string; authority?: string;
  source_priority?: string; provision_text?: string; amended?: boolean;
  effective_from?: string; effective_to?: string;
  reviewed_by?: string; reviewed_at?: string;
}

export interface RuleResult {
  rule_code: string; rule_version_id: string; title: string;
  status: RuleStatus; severity: string; message: string; explanation: string;
  requirement?: string; missing_field?: string | null;
  condition_trace: Array<Record<string, unknown>>;
  exception_applied?: { exception_code: string; description: string; condition: string;
                        effect: string; source_reference?: string } | null;
  source_reference: SourceReference; demo_approved: boolean;
}

export interface CalcResult {
  calc_code: string; name: string; formula: string; unit: string;
  inputs: Record<string, string>; result: string | null;
  calculation_version_id: string | null; note?: string | null;
}

export interface Assessment {
  assessment_id?: string; scenario_id?: string; engine_version: string;
  transaction_date: string; issue_type: string; issue_label: string;
  overall_status: RuleStatus;
  company?: { company_id: string; name: string; company_type: string;
              listed_status: string; exchanges: string[] };
  capacity: {
    capital_capacity: { available_shares: number | null; basis: string;
                        calculation_version_id: string | null };
    legal_issue_capacity: { determinable: boolean; value: number | null;
                            reason: string; indeterminate_causes: string[] };
    binding_constraint: { type: string; detail: string; rule_code?: string;
                          source_reference?: SourceReference };
    proposed_shares: number | null;
    proposal_within_capital_capacity: boolean | null;
  };
  calculations: CalcResult[];
  calculations_skipped: Array<{ calc_code: string; name: string; missing_field: string }>;
  dilution: DilutionRow[];
  rule_results: RuleResult[];
  rules_evaluated: number; rules_applicable: number;
  counts: Record<string, number>;
  approvals: Array<{ approval_code: string; approval_type: string; name: string;
                     authority: string; stage: string; caused_by_rule: string;
                     source_reference: SourceReference }>;
  filings: Array<Record<string, unknown>>;
  document_requirements: Array<{ requirement_code: string; name: string; stage: string;
                                 necessity: string; authority: string;
                                 caused_by_rule: string; source_reference: SourceReference }>;
  compliance_timeline: Array<Record<string, unknown>>;
  warnings: Array<{ code: string; message: string; action_required?: string;
                    provisions_required?: string[] }>;
  assumptions: Array<{ code: string; message: string }>;
  audit: { rule_versions_used: string[]; calculation_versions_used: string[];
           reproducible: boolean };
  disclaimer: string;
}

export interface SessionUser {
  user_id: string; email: string; full_name: string; role: string;
  org_id: string; org_name: string; is_demo_org: boolean;
}

const TOKEN_KEY = "csi.access";
const REFRESH_KEY = "csi.refresh";
const USER_KEY = "csi.user";

export const session = {
  get token() { return typeof window === "undefined" ? null : localStorage.getItem(TOKEN_KEY); },
  get user(): SessionUser | null {
    if (typeof window === "undefined") return null;
    const raw = localStorage.getItem(USER_KEY);
    return raw ? (JSON.parse(raw) as SessionUser) : null;
  },
  save(access: string, refresh: string, user: SessionUser) {
    localStorage.setItem(TOKEN_KEY, access);
    localStorage.setItem(REFRESH_KEY, refresh);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  },
  clear() { [TOKEN_KEY, REFRESH_KEY, USER_KEY].forEach((k) => localStorage.removeItem(k)); },
};

export class ApiError extends Error {
  constructor(public status: number, message: string, public detail?: unknown) {
    super(message);
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  const t = session.token;
  if (t) headers.set("Authorization", `Bearer ${t}`);

  const res = await fetch(`${BASE}${path}`, { ...init, headers });
  if (res.status === 401 && typeof window !== "undefined"
      && !window.location.pathname.startsWith("/login")) {
    session.clear();
    window.location.href = "/login";
    throw new ApiError(401, "Session expired");
  }
  const body = res.status === 204 ? null : await res.json().catch(() => null);
  if (!res.ok) {
    const detail = (body as { detail?: unknown; message?: string } | null);
    const msg =
      typeof detail?.detail === "string" ? detail.detail
      : Array.isArray(detail?.detail) ? "Please check the highlighted fields."
      : detail?.message ?? `Request failed (${res.status})`;
    throw new ApiError(res.status, msg, detail?.detail);
  }
  return body as T;
}

export const api = {
  login: (email: string, password: string) =>
    request<{ access_token: string; refresh_token: string; user: SessionUser }>(
      "/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  health: () => request<{ status: string; active_rules: number }>("/health"),
  companies: () => request<{ companies: Company[] }>("/companies"),
  company: (id: string) => request<Record<string, unknown>>(`/companies/${id}`),
  createCompany: (body: unknown) =>
    request<{ company_id: string }>("/companies", { method: "POST", body: JSON.stringify(body) }),
  setCapital: (id: string, body: unknown) =>
    request<unknown>(`/companies/${id}/capital`, { method: "PUT", body: JSON.stringify(body) }),
  routes: (listed: boolean) => request<{ routes: RouteInfo[] }>(`/routes?listed=${listed}`),
  guidance: (body: unknown) =>
    request<{ status: string; candidates: RouteCandidate[]; message: string }>(
      "/routes/guidance", { method: "POST", body: JSON.stringify(body) }),
  assess: (body: unknown) =>
    request<Assessment>("/assessments", { method: "POST", body: JSON.stringify(body) }),
  assessment: (id: string) => request<Assessment>(`/assessments/${id}`),
  assessments: () => request<{ assessments: AssessmentRow[] }>("/assessments"),
  provision: (uid: string) =>
    request<Record<string, unknown>>(`/legal/provisions/${encodeURIComponent(uid)}`),
  sourceGaps: () => request<{ gaps: SourceGap[] }>("/legal/source-gaps"),
  rulesInForce: (issueType?: string) =>
    request<{ count: number; rules: Record<string, unknown>[] }>(
      `/legal/rules${issueType ? `?issue_type=${issueType}` : ""}`),
  reviewQueue: () => request<{ pending: number; items: ReviewItem[] }>("/admin/review-queue"),
  reviewRule: (id: string, decision: string, notes?: string) =>
    request<unknown>(`/admin/rules/${id}/review`,
      { method: "POST", body: JSON.stringify({ decision, notes }) }),
  stats: () => request<Record<string, Record<string, number>>>("/admin/stats"),
  qualityChecks: () =>
    request<{ checks: Array<{ check_name: string; failing_rows: number }>; all_clear: boolean }>(
      "/admin/quality-checks"),
};

export interface DilutionRow {
  holder: string; category: string | null; is_promoter: boolean;
  shares_pre: string; shares_allotted: string; shares_post: string;
  pct_pre: string | null; pct_post: string; change_pp: string | null;
}

export interface Company {
  company_id: string; name: string; cin: string | null;
  company_type: string; listed_status: string; exchanges: string[] | null;
  authorised_capital: number | null; issued_capital: number | null;
  paid_up_capital: number | null; face_value: number | null; shares_issued: number | null;
}
export interface RouteInfo {
  issue_type: string; label: string; in_mvp: boolean;
  source_gate: { code: string; detail: string; provisions_required: string[] } | null;
  questions: RouteQuestion[];
}
export interface RouteQuestion {
  key: string; label: string; type: "number" | "date" | "boolean" | "select" | "text";
  options?: string[]; required?: boolean; unit?: string; listed_only?: boolean;
}
export interface RouteCandidate {
  issue_type: string; label: string; relevance: number; rationale: string;
  source_gate: { code: string } | null;
}
export interface AssessmentRow {
  assessment_id: string; run_at: string; overall_result: RuleStatus;
  blocks_count: number; warnings_count: number; review_count: number;
  issue_type: string; transaction_date: string; company_name: string; company_id: string;
}
export interface SourceGap {
  code: string; severity: string; title: string; detail: string;
  action_required: string; blocks_issue_types: string[]; provisions_required: string[];
  resolved_at: string | null;
}
export interface ReviewItem {
  rule_version_id: string; rule_code: string; title: string; issue_type: string;
  company_type: string; listed_status: string; severity: string; requirement: string;
  result_if_pass: string; result_if_fail: string; legal_review_status: string;
  effective_from: string; source_reference: string; citation: string | null;
  citation_uid: string | null; display_text: string | null; instrument_label: string | null;
  file_name: string | null; source_priority: string | null; page_from: number | null;
  conditions: Array<{ condition_role: string; expr_text: string; ordinal: number }>;
}

/** Indian digit grouping: 1,00,00,000 rather than 10,000,000. */
export function inr(value: number | string | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  const n = typeof value === "string" ? Number(value) : value;
  if (Number.isNaN(n)) return String(value);
  return new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 }).format(n);
}
export function rupees(value: number | string | null | undefined): string {
  const s = inr(value);
  return s === "—" ? s : `₹${s}`;
}
