"use client";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";
import { api, inr, rupees, type Company, type RouteCandidate, type RouteInfo,
         type RouteQuestion } from "@/lib/api";
import { Banner, Button, Card, Field, SectionTitle, inputCls } from "@/components/ui";

const STEPS = ["Company", "Route", "Proposed issue", "Route details", "Review"] as const;

function Wizard() {
  const router = useRouter();
  const params = useSearchParams();
  const [step, setStep] = useState(0);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [companyId, setCompanyId] = useState(params.get("company") ?? "");
  const [routes, setRoutes] = useState<RouteInfo[]>([]);
  const [issueType, setIssueType] = useState("");
  const [guidance, setGuidance] = useState<RouteCandidate[] | null>(null);
  const [form, setForm] = useState<Record<string, string>>({
    shares_proposed: "", issue_price: "", face_value: "",
  });
  const [extra, setExtra] = useState<Record<string, string | boolean>>({});
  const [txnDate, setTxnDate] = useState(new Date().toISOString().slice(0, 10));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const company = companies.find((c) => c.company_id === companyId);
  const listed = company?.listed_status === "LISTED";

  useEffect(() => { api.companies().then((r) => setCompanies(r.companies)).catch(() => {}); }, []);
  useEffect(() => {
    api.routes(listed).then((r) => setRoutes(r.routes)).catch(() => {});
  }, [listed]);
  useEffect(() => {
    if (company?.face_value && !form.face_value) {
      setForm((f) => ({ ...f, face_value: String(company.face_value) }));
    }
  }, [company, form.face_value]);

  const route = routes.find((r) => r.issue_type === issueType);
  const questions: RouteQuestion[] = route?.questions ?? [];

  const derived = useMemo(() => {
    const n = Number(form.shares_proposed || 0);
    const p = Number(form.issue_price || 0);
    const fv = Number(form.face_value || 0);
    const authShares = company?.authorised_capital && company?.face_value
      ? Math.floor(company.authorised_capital / company.face_value) : null;
    const available = authShares != null && company?.shares_issued != null
      ? authShares - company.shares_issued : null;
    return {
      consideration: n && p ? n * p : null,
      premium: p && fv ? p - fv : null,
      available,
      exceeds: available != null && n > available,
    };
  }, [form, company]);

  async function askGuidance() {
    try {
      const r = await api.guidance({
        listed_status: company?.listed_status ?? "UNKNOWN",
        offered_to_existing_shareholders: extra.offered_to_existing === true ? true
          : extra.offered_to_existing === false ? false : null,
        allottee_count: Number(extra.allottee_count ?? 0) || null,
      });
      setGuidance(r.candidates);
    } catch (e) { setError(e instanceof Error ? e.message : "Guidance failed"); }
  }

  async function run() {
    setBusy(true); setError(null);
    try {
      const cleanExtra: Record<string, unknown> = {};
      for (const [k, v] of Object.entries(extra)) {
        if (v === "" || v === undefined) continue;
        cleanExtra[k] = v === "true" ? true : v === "false" ? false : v;
      }
      const a = await api.assess({
        company_id: companyId,
        transaction_date: txnDate,
        issue: {
          issue_type: issueType,
          security_type: "EQUITY_SHARES",
          shares_proposed: form.shares_proposed || null,
          issue_price: form.issue_price || null,
          face_value: form.face_value || null,
          extra: cleanExtra,
        },
      });
      router.push(`/assessments/${a.assessment_id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Assessment failed");
      setBusy(false);
    }
  }

  const canNext = [
    !!companyId,
    !!issueType,
    !!form.shares_proposed && !!form.face_value,
    true,
    true,
  ][step];

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">New assessment</h1>
        <p className="mt-1 text-sm text-muted">
          The result reports capital capacity and legal issue capacity separately.
        </p>
      </div>

      <ol className="flex flex-wrap items-center gap-1 text-xs">
        {STEPS.map((s, i) => (
          <li key={s} className="flex items-center gap-1">
            <button onClick={() => i < step && setStep(i)}
                    className={`rounded px-2.5 py-1 ${
                      i === step ? "bg-accent text-white"
                      : i < step ? "bg-surface-2 text-ink-2 hover:text-accent-hi"
                      : "text-faint"}`}>
              <span className="tnum mr-1.5 opacity-60">{i + 1}</span>{s}
            </button>
            {i < STEPS.length - 1 && <span className="text-faint">›</span>}
          </li>
        ))}
      </ol>

      {error && <Banner tone="block" title="Could not continue">{error}</Banner>}

      <Card className="p-6">
        {step === 0 && (
          <div className="space-y-4">
            <SectionTitle>Select the company</SectionTitle>
            <div className="space-y-2">
              {companies.map((c) => (
                <button key={c.company_id} onClick={() => setCompanyId(c.company_id)}
                        className={`flex w-full items-center justify-between rounded-md border
                                    px-4 py-3 text-left transition-colors ${
                          companyId === c.company_id
                            ? "border-accent bg-accent-dim/30"
                            : "border-border hover:border-border-lit"}`}>
                  <div>
                    <div className="text-sm font-medium text-ink">{c.name}</div>
                    <div className="font-mono text-[11px] text-faint">
                      {c.company_type?.toLowerCase()} · {c.listed_status?.toLowerCase()}
                      {c.exchanges?.length ? ` · ${c.exchanges.join(", ")}` : ""}
                    </div>
                  </div>
                  <div className="tnum text-right text-xs">
                    <div className="text-muted">headroom</div>
                    <div className="text-ink-2">
                      {c.authorised_capital && c.face_value && c.shares_issued != null
                        ? inr(Math.floor(c.authorised_capital / c.face_value) - c.shares_issued)
                        : "—"}
                    </div>
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}

        {step === 1 && (
          <div className="space-y-4">
            <SectionTitle hint={listed ? "listed issuer" : "unlisted issuer"}>
              Which route?
            </SectionTitle>
            <div className="grid gap-2 sm:grid-cols-2">
              {routes.filter((r) => r.in_mvp).map((r) => (
                <button key={r.issue_type} onClick={() => setIssueType(r.issue_type)}
                        className={`rounded-md border px-4 py-3 text-left ${
                          issueType === r.issue_type
                            ? "border-accent bg-accent-dim/30"
                            : "border-border hover:border-border-lit"}`}>
                  <div className="text-sm font-medium text-ink">{r.label}</div>
                  {r.source_gate && (
                    <div className="mt-1 text-[11px] leading-snug text-warn">
                      Primary law missing — legal conclusions will be review-required
                    </div>
                  )}
                </button>
              ))}
              <button onClick={() => { setIssueType(""); askGuidance(); }}
                      className="rounded-md border border-dashed border-border px-4 py-3
                                 text-left hover:border-accent/50">
                <div className="text-sm font-medium text-ink-2">Not sure</div>
                <div className="mt-1 text-[11px] text-faint">Explain which routes may apply</div>
              </button>
            </div>

            {guidance && (
              <div className="rounded-md border border-review/30 bg-review-bg p-4">
                <p className="mb-3 text-sm text-ink-2">
                  These routes may be relevant. Identifying the correct route is a legal
                  question and must be confirmed by a professional.
                </p>
                <div className="space-y-2">
                  {guidance.map((g) => (
                    <div key={g.issue_type} className="rounded border border-border bg-ground p-3">
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-medium text-ink">{g.label}</span>
                        <button onClick={() => setIssueType(g.issue_type)}
                                className="text-xs text-accent-hi hover:underline">Choose</button>
                      </div>
                      <p className="mt-1 text-[13px] leading-relaxed text-muted">{g.rationale}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {step === 2 && (
          <div className="space-y-4">
            <SectionTitle>Proposed issue</SectionTitle>
            <div className="grid gap-4 sm:grid-cols-3">
              <Field label="Number of securities" required>
                <input className={inputCls} type="number" min="1" value={form.shares_proposed}
                       onChange={(e) => setForm({ ...form, shares_proposed: e.target.value })} />
              </Field>
              <Field label="Face value (₹)" required>
                <input className={inputCls} type="number" step="0.01" value={form.face_value}
                       onChange={(e) => setForm({ ...form, face_value: e.target.value })} />
              </Field>
              <Field label="Issue price (₹)">
                <input className={inputCls} type="number" step="0.01" value={form.issue_price}
                       onChange={(e) => setForm({ ...form, issue_price: e.target.value })} />
              </Field>
            </div>
            <Field label="Transaction date"
                   hint="Selects which rule and calculation versions apply — not the run date.">
              <input className={inputCls} type="date" value={txnDate}
                     onChange={(e) => setTxnDate(e.target.value)} />
            </Field>

            <div className="tnum grid gap-3 rounded-md border border-border bg-ground p-4 sm:grid-cols-3">
              <div>
                <div className="text-[11px] uppercase tracking-wider text-muted">Consideration</div>
                <div className="mt-0.5 text-ink-2">{rupees(derived.consideration)}</div>
              </div>
              <div>
                <div className="text-[11px] uppercase tracking-wider text-muted">Premium / share</div>
                <div className="mt-0.5 text-ink-2">{rupees(derived.premium)}</div>
              </div>
              <div>
                <div className="text-[11px] uppercase tracking-wider text-muted">Capital headroom</div>
                <div className={`mt-0.5 ${derived.exceeds ? "text-block" : "text-ink-2"}`}>
                  {inr(derived.available)}
                </div>
              </div>
            </div>
            {derived.exceeds && (
              <Banner tone="warn" title="Exceeds capital headroom">
                The proposal is larger than the shares available within authorised capital.
                The assessment will still run and will name this as the binding constraint.
              </Banner>
            )}
          </div>
        )}

        {step === 3 && (
          <div className="space-y-4">
            <SectionTitle hint={route?.label}>Route details</SectionTitle>
            {route?.source_gate && (
              <Banner tone="warn" title="Primary law for this route is not in the corpus">
                {route.source_gate.detail}
              </Banner>
            )}
            {questions.length === 0 ? (
              <p className="text-sm text-muted">No additional questions for this route.</p>
            ) : (
              <div className="grid gap-4 sm:grid-cols-2">
                {questions.map((q) => (
                  <Field key={q.key} label={q.label} required={q.required}>
                    {q.type === "boolean" ? (
                      <select className={inputCls} value={String(extra[q.key] ?? "")}
                              onChange={(e) => setExtra({ ...extra, [q.key]: e.target.value })}>
                        <option value="">Not stated</option>
                        <option value="true">Yes</option>
                        <option value="false">No</option>
                      </select>
                    ) : q.type === "select" ? (
                      <select className={inputCls} value={String(extra[q.key] ?? "")}
                              onChange={(e) => setExtra({ ...extra, [q.key]: e.target.value })}>
                        <option value="">Not stated</option>
                        {q.options?.map((o) => <option key={o} value={o}>{o.replace(/_/g, " ")}</option>)}
                      </select>
                    ) : (
                      <input className={inputCls}
                             type={q.type === "number" ? "number" : q.type === "date" ? "date" : "text"}
                             value={String(extra[q.key] ?? "")}
                             onChange={(e) => setExtra({ ...extra, [q.key]: e.target.value })} />
                    )}
                  </Field>
                ))}
              </div>
            )}
            <p className="text-xs leading-relaxed text-faint">
              Leaving a question unanswered is safe: the engine reports the rule as
              review-required and names the missing fact. It never assumes an answer.
            </p>
          </div>
        )}

        {step === 4 && (
          <div className="space-y-4">
            <SectionTitle>Review and run</SectionTitle>
            <dl className="divide-y divide-border rounded-md border border-border">
              {[
                ["Company", company?.name],
                ["Classification", `${company?.company_type?.toLowerCase()} · ${company?.listed_status?.toLowerCase()}`],
                ["Route", route?.label],
                ["Securities", `${inr(form.shares_proposed)} at ₹${form.issue_price || "—"}`],
                ["Consideration", rupees(derived.consideration)],
                ["Transaction date", txnDate],
                ["Route answers", `${Object.values(extra).filter((v) => v !== "").length} of ${questions.length} answered`],
              ].map(([k, v]) => (
                <div key={k as string} className="flex justify-between px-4 py-2.5 text-sm">
                  <dt className="text-muted">{k}</dt>
                  <dd className="tnum text-right text-ink-2">{v as string}</dd>
                </div>
              ))}
            </dl>
            <Button onClick={run} disabled={busy} className="w-full">
              {busy ? "Evaluating rules…" : "Run assessment"}
            </Button>
          </div>
        )}
      </Card>

      <div className="flex justify-between">
        <Button variant="ghost" onClick={() => setStep(Math.max(0, step - 1))}
                disabled={step === 0}>Back</Button>
        {step < STEPS.length - 1 && (
          <Button onClick={() => setStep(step + 1)} disabled={!canNext}>Continue</Button>
        )}
      </div>
    </div>
  );
}

export default function AssessPage() {
  return <Suspense fallback={<p className="text-sm text-muted">Loading…</p>}><Wizard /></Suspense>;
}
