"use client";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";
import { api, ApiError, type CapitalBody, type Company, type HoldingBody,
         type IssueHistoryBody, type RouteCandidate, type RouteInfo } from "@/lib/api";
import { Banner, Button, Card, PageHeader } from "@/components/ui";
import { canJumpTo, nextStep, plan, previousStep, type StepId } from "./_wizard/machine";
import { CompanyStep } from "./_steps/CompanyStep";
import { CapitalStep } from "./_steps/CapitalStep";
import { CapTableStep } from "./_steps/CapTableStep";
import { HistoryStep } from "./_steps/HistoryStep";
import { RouteStep } from "./_steps/RouteStep";
import { IssueStep, type IssueDraft } from "./_steps/IssueStep";
import { DetailsStep } from "./_steps/DetailsStep";
import { ReviewStep } from "./_steps/ReviewStep";

function Wizard() {
  const router = useRouter();
  const params = useSearchParams();

  const [step, setStep] = useState<StepId>("company");
  const [company, setCompany] = useState<Company | null>(null);
  const [routes, setRoutes] = useState<RouteInfo[]>([]);
  const [issueType, setIssueType] = useState("");
  const [guidance, setGuidance] = useState<RouteCandidate[] | null>(null);
  const [draft, setDraft] = useState<IssueDraft>({
    shares_proposed: "", issue_price: "", face_value: "",
  });
  const [extra, setExtra] = useState<Record<string, string | boolean>>({});
  const [txnDate, setTxnDate] = useState(new Date().toISOString().slice(0, 10));

  // Exactly one write is ever in flight, and its failure is attributed to the
  // step that caused it rather than to the wizard as a whole.
  const [saving, setSaving] = useState<StepId | null>(null);
  const [errors, setErrors] = useState<Partial<Record<StepId, string>>>({});
  const [busy, setBusy] = useState(false);

  const listed = company?.listed_status === "LISTED";
  const route = routes.find((r) => r.issue_type === issueType);
  const steps = plan(company, route);

  /** Completeness is read back from the server, never inferred locally. */
  const refresh = useCallback(async (id: string): Promise<Company | null> => {
    try {
      const r = await api.searchCompanies("", { limit: 100 });
      return r.companies.find((c) => c.company_id === id) ?? null;
    } catch {
      return null;
    }
  }, []);

  // Resuming: ?company= is the whole of the wizard's durable state, so a
  // refresh or a back-button after a part-finished setup picks up where it was
  // rather than starting a second company.
  const initial = params.get("company");
  useEffect(() => {
    if (!initial || company) return;
    void refresh(initial).then((c) => {
      if (!c) return;
      setCompany(c);
      const p = plan(c, undefined);
      setStep(nextStep(p, "company"));
    });
  }, [initial, company, refresh]);

  useEffect(() => { api.routes(listed).then((r) => setRoutes(r.routes)).catch(() => {}); },
            [listed]);

  useEffect(() => {
    if (company?.face_value && !draft.face_value) {
      setDraft((d) => ({ ...d, face_value: String(company.face_value) }));
    }
  }, [company, draft.face_value]);

  function fail(id: StepId, e: unknown) {
    setErrors((x) => ({
      ...x, [id]: e instanceof ApiError ? e.message
        : e instanceof Error ? e.message : "That did not save.",
    }));
  }

  function advance(from: StepId, c: Company | null = company) {
    setStep(nextStep(plan(c, route), from));
  }

  async function selectCompany(c: Company) {
    setCompany(c);
    // Claims the URL immediately, so a reload resumes this company.
    router.replace(`/assess?company=${c.company_id}`, { scroll: false });
    advance("company", c);
  }

  async function created(c: { company_id: string }) {
    const full = await refresh(c.company_id);
    if (full) await selectCompany(full);
  }

  async function save<T>(id: StepId, fn: () => Promise<T>) {
    if (saving) return;
    setSaving(id); setErrors((x) => ({ ...x, [id]: undefined }));
    try {
      await fn();
      const refreshed = company ? await refresh(company.company_id) : null;
      if (refreshed) setCompany(refreshed);
      setStep(nextStep(plan(refreshed ?? company, route), id));
    } catch (e) {
      fail(id, e);
    } finally {
      setSaving(null);
    }
  }

  async function askGuidance() {
    try {
      const r = await api.guidance({
        listed_status: company?.listed_status ?? "UNKNOWN",
        offered_to_existing_shareholders: null,
        allottee_count: null,
      });
      setGuidance(r.candidates);
    } catch (e) { fail("route", e); }
  }

  async function run() {
    if (!company) return;
    setBusy(true); setErrors((x) => ({ ...x, review: undefined }));
    try {
      const cleanExtra: Record<string, unknown> = {};
      for (const [k, v] of Object.entries(extra)) {
        if (v === "" || v === undefined) continue;
        cleanExtra[k] = v === "true" ? true : v === "false" ? false : v;
      }
      const a = await api.assess({
        company_id: company.company_id,
        transaction_date: txnDate,
        issue: {
          issue_type: issueType,
          security_type: "EQUITY_SHARES",
          shares_proposed: draft.shares_proposed || null,
          issue_price: draft.issue_price || null,
          face_value: draft.face_value || null,
          extra: cleanExtra,
        },
      });
      router.push(`/assessments/${a.assessment_id}`);
    } catch (e) {
      fail("review", e);
      setBusy(false);
    }
  }

  const canContinue: Partial<Record<StepId, boolean>> = {
    company: !!company,
    route: !!issueType,
    issue: !!draft.shares_proposed && !!draft.face_value,
    details: true,
  };
  const showContinue = ["company", "route", "issue", "details"].includes(step);
  const back = previousStep(steps, step);

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <PageHeader
        title="New assessment"
        lead="The result reports capital capacity and legal issue capacity separately."
      />

      {/* Same pill group as the main nav, so the wizard reads as part of the
          app rather than a form bolted onto it. The active step is a white
          pill: the accent is a light mint, so white-on-accent would be
          unreadable. */}
      <ol className="flex flex-wrap items-center gap-1 rounded-lg bg-surface-2 p-1">
        {steps.map((s, i) => {
          const jumpable = canJumpTo(steps, step, s.id);
          const done = s.state === "satisfied" && s.id !== step;
          return (
            <li key={s.id}>
              <button onClick={() => jumpable && setStep(s.id)} disabled={!jumpable}
                      title={s.note}
                      aria-current={s.id === step ? "step" : undefined}
                      className={`flex items-center gap-1.5 whitespace-nowrap rounded-md
                                  px-3 py-1.5 text-[12px] transition-colors ${
                        s.id === step ? "bg-surface font-medium text-accent shadow-sm"
                        : jumpable ? "text-ink-2 hover:text-ink"
                        : "cursor-not-allowed text-faint"}`}>
                <span className={`tnum grid h-4 w-4 place-items-center rounded-full text-[10px] ${
                  s.id === step ? "bg-accent-dim text-accent"
                  : done ? "bg-pass-bg text-pass" : "bg-surface-2 text-faint"}`}>
                  {done ? "✓" : i + 1}
                </span>
                {s.label}
              </button>
            </li>
          );
        })}
      </ol>

      {errors[step] && step !== "company" && (
        <Banner tone="block" title="Could not continue">{errors[step]}</Banner>
      )}

      <Card className="p-6">
        {step === "company" && (
          <CompanyStep company={company} onSelect={selectCompany} onCreated={created} />
        )}
        {step === "capital" && company && (
          <CapitalStep company={company} saving={saving === "capital"}
                       error={errors.capital ?? null}
                       onSave={(b: CapitalBody) =>
                         void save("capital", () => api.setCapital(company.company_id, b))} />
        )}
        {step === "captable" && company && (
          <CapTableStep company={company} saving={saving === "captable"}
                        error={errors.captable ?? null}
                        onSkip={() => advance("captable")}
                        onSave={(rows: HoldingBody[]) =>
                          void save("captable", () => api.setHoldings(company.company_id, rows))} />
        )}
        {step === "history" && company && (
          <HistoryStep routes={routes} saving={saving === "history"}
                       error={errors.history ?? null}
                       onSkip={() => advance("history")}
                       onSave={(rows: IssueHistoryBody[]) =>
                         void save("history", () => api.recordIssues(company.company_id, rows))} />
        )}
        {step === "route" && (
          <RouteStep routes={routes} issueType={issueType} guidance={guidance}
                     onAskGuidance={() => void askGuidance()}
                     onSelect={(t) => { setIssueType(t); setGuidance(null); }} />
        )}
        {step === "issue" && company && (
          <IssueStep company={company} draft={draft} onChange={setDraft}
                     txnDate={txnDate} onTxnDate={setTxnDate} />
        )}
        {step === "details" && (
          <DetailsStep route={route} extra={extra} onChange={setExtra} />
        )}
        {step === "review" && company && (
          <ReviewStep company={company} route={route} draft={draft} extra={extra}
                      txnDate={txnDate} busy={busy} onRun={() => void run()} />
        )}
      </Card>

      <div className="flex justify-between">
        <Button variant="ghost" onClick={() => back && setStep(back)} disabled={!back}>
          Back
        </Button>
        {showContinue && (
          <Button onClick={() => advance(step)} disabled={!canContinue[step]}>Continue</Button>
        )}
      </div>
    </div>
  );
}

export default function AssessPage() {
  return (
    <Suspense fallback={<p className="text-sm text-muted">Loading…</p>}>
      <Wizard />
    </Suspense>
  );
}
