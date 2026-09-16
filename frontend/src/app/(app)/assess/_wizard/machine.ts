import type { Company, RouteInfo } from "@/lib/api";

export type StepId =
  | "company" | "capital" | "captable" | "history"
  | "route" | "issue" | "details" | "review";

/**
 * `satisfied` steps are already on file and are skipped when moving forward,
 * but stay visible and revisitable. `optional` steps are shown with a skip.
 */
export type StepState = "required" | "optional" | "satisfied";

export interface PlannedStep {
  id: StepId;
  label: string;
  state: StepState;
  note?: string;
}

const LABELS: Record<StepId, string> = {
  company: "Company",
  capital: "Share capital",
  captable: "Shareholders",
  history: "Previous issues",
  route: "Transaction",
  issue: "Proposed issue",
  details: "Route details",
  review: "Review",
};

/**
 * Completeness is read from the company record the server returned, never from
 * a local flag. That makes "skip because it is already on file" and "resume
 * after a failed step" the same code path rather than two.
 */
export function plan(company: Company | null, route: RouteInfo | undefined): PlannedStep[] {
  const hasCapital = !!company && company.face_value !== null;
  const hasHolders = !!company && company.holder_count > 0;
  const hasIssues = !!company && company.issue_count > 0;

  const step = (id: StepId, state: StepState, note?: string): PlannedStep =>
    ({ id, label: LABELS[id], state, note });

  return [
    step("company", company ? "satisfied" : "required"),
    // Required: POST /assessments refuses a company with no capital snapshot.
    step("capital", hasCapital ? "satisfied" : "required",
         hasCapital ? "on file" : undefined),
    step("captable", hasHolders ? "satisfied" : "optional",
         hasHolders ? `${company!.holder_count} on file` : undefined),
    step("history", hasIssues ? "satisfied" : "optional",
         hasIssues ? `${company!.issue_count} on file` : undefined),
    step("route", "required"),
    step("issue", "required"),
    step("details", route && route.questions.length === 0 ? "optional" : "required"),
    step("review", "required"),
  ];
}

export function nextStep(steps: PlannedStep[], from: StepId): StepId {
  const i = steps.findIndex((s) => s.id === from);
  for (let j = i + 1; j < steps.length; j++) {
    if (steps[j].state !== "satisfied") return steps[j].id;
  }
  return steps[steps.length - 1].id;
}

export function previousStep(steps: PlannedStep[], from: StepId): StepId | null {
  const i = steps.findIndex((s) => s.id === from);
  for (let j = i - 1; j >= 0; j--) {
    if (steps[j].state !== "satisfied") return steps[j].id;
  }
  return null;
}

/** A satisfied step may be revisited in either direction; others only backwards. */
export function canJumpTo(steps: PlannedStep[], current: StepId, target: StepId): boolean {
  const ci = steps.findIndex((s) => s.id === current);
  const ti = steps.findIndex((s) => s.id === target);
  if (ti < 0 || ci < 0) return false;
  return ti < ci || steps[ti].state === "satisfied";
}
