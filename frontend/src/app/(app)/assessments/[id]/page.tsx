"use client";
import { use, useEffect, useState } from "react";
import { api, inr, rupees, type Assessment, type RuleResult } from "@/lib/api";
import { Banner, Card, SectionTitle, SourceChip, Stat, StatusBadge } from "@/components/ui";

const ORDER = ["BLOCK", "REVIEW_REQUIRED", "WARNING", "PASS", "NOT_APPLICABLE"];

export default function AssessmentPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [a, setA] = useState<Assessment | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showNA, setShowNA] = useState(false);

  useEffect(() => {
    api.assessment(id).then(setA).catch((e) => setError(e.message));
  }, [id]);

  if (error) return <Banner tone="block" title="Could not load assessment">{error}</Banner>;
  if (!a) return <p className="text-sm text-muted">Loading…</p>;

  const cap = a.capacity;
  const legal = cap.legal_issue_capacity;
  const rules = [...a.rule_results].sort(
    (x, y) => ORDER.indexOf(x.status) - ORDER.indexOf(y.status));
  const visible = rules.filter((r) => showNA || r.status !== "NOT_APPLICABLE");

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="mb-1 font-mono text-[11px] uppercase tracking-[0.12em] text-muted">
            {a.issue_label} · {a.transaction_date}
          </div>
          <h1 className="text-xl font-semibold tracking-tight">{a.company?.name}</h1>
          <p className="mt-1 text-sm text-muted">
            {a.company?.company_type?.toLowerCase()} · {a.company?.listed_status?.toLowerCase()}
            {a.company?.exchanges?.length ? ` · ${a.company.exchanges.join(", ")}` : ""}
          </p>
        </div>
        <StatusBadge status={a.overall_status} size="lg" />
      </div>

      {/* The product's central discipline: two numbers, never merged. */}
      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="p-6">
          <Stat label="Capital capacity"
                value={cap.capital_capacity.available_shares !== null
                  ? `${inr(cap.capital_capacity.available_shares)} shares` : "—"}
                sub={<>Arithmetic only: {cap.capital_capacity.basis}. This is not a
                     statement that the shares may lawfully be issued.</>} />
        </Card>
        <Card className={`p-6 ${legal.determinable ? "" : "border-review/40"}`}>
          <Stat label="Legal issue capacity"
                tone={legal.determinable ? "accent" : "muted"}
                value={legal.value !== null ? `${inr(legal.value)} shares` : "Indeterminate"}
                sub={legal.reason} />
          {legal.indeterminate_causes.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {legal.indeterminate_causes.map((c) => (
                <span key={c} className="rounded border border-review/30 bg-review-bg px-2 py-0.5
                                         font-mono text-[10px] text-review">{c}</span>
              ))}
            </div>
          )}
        </Card>
      </div>

      <Card className="p-5">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <span className="text-[11px] font-semibold uppercase tracking-[0.09em] text-muted">
            Binding constraint
          </span>
          <span className="rounded border border-border-lit bg-surface-2 px-2 py-0.5
                           font-mono text-[11px] text-ink-2">
            {cap.binding_constraint.type}
          </span>
        </div>
        <p className="mt-2 text-sm leading-relaxed text-ink-2">{cap.binding_constraint.detail}</p>
        {cap.binding_constraint.source_reference && (
          <SourceChip source={cap.binding_constraint.source_reference} />
        )}
      </Card>

      {a.warnings.length > 0 && (
        <section className="space-y-2">
          <SectionTitle>Warnings</SectionTitle>
          {a.warnings.map((w, i) => (
            <Banner key={i} tone={w.code === "SOURCE_GAP" ? "warn" : "info"}
                    title={w.code.replace(/_/g, " ").toLowerCase()}>
              <p>{w.message}</p>
              {w.action_required && <p className="mt-1.5 text-ink-2">{w.action_required}</p>}
            </Banner>
          ))}
        </section>
      )}

      <section>
        <SectionTitle hint={`${a.counts.block} blocked · ${a.counts.review_required} review · ${a.counts.pass} pass`}>
          Legal assessment
        </SectionTitle>
        <div className="space-y-3">
          {visible.map((r) => <RuleCard key={r.rule_version_id} r={r} />)}
        </div>
        {a.counts.not_applicable > 0 && (
          <button onClick={() => setShowNA(!showNA)}
                  className="mt-3 text-xs text-muted hover:text-accent-hi">
            {showNA ? "Hide" : "Show"} {a.counts.not_applicable} rule(s) that did not apply
          </button>
        )}
      </section>

      <section>
        <SectionTitle hint="every figure shows its formula">Calculations</SectionTitle>
        <Card className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-[11px] uppercase tracking-wider text-muted">
                <th className="px-4 py-2.5 font-medium">Calculation</th>
                <th className="px-4 py-2.5 font-medium">Formula</th>
                <th className="px-4 py-2.5 text-right font-medium">Result</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {a.calculations.map((c) => (
                <tr key={c.calc_code}>
                  <td className="px-4 py-2.5 text-ink-2">{c.name}</td>
                  <td className="px-4 py-2.5 font-mono text-[11px] text-faint">{c.formula}</td>
                  <td className="tnum px-4 py-2.5 text-right font-medium text-ink">
                    {c.unit === "INR" ? rupees(c.result) : inr(c.result)}
                    <span className="ml-1.5 text-[11px] text-faint">
                      {c.unit === "INR" ? "" : c.unit}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
        {a.calculations_skipped.length > 0 && (
          <p className="mt-2 text-xs text-muted">
            Not computed: {a.calculations_skipped.map((s) => `${s.name} (needs ${s.missing_field})`).join("; ")}
          </p>
        )}
      </section>

      {a.dilution.length > 0 && (
        <section>
          <SectionTitle>Dilution</SectionTitle>
          <Card className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-[11px] uppercase tracking-wider text-muted">
                  <th className="px-4 py-2.5 font-medium">Holder</th>
                  <th className="px-4 py-2.5 text-right font-medium">Pre</th>
                  <th className="px-4 py-2.5 text-right font-medium">Post</th>
                  <th className="px-4 py-2.5 text-right font-medium">Change</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {a.dilution.map((d, i) => (
                  <tr key={i}>
                    <td className="px-4 py-2.5 text-ink-2">
                      {d.holder}
                      {d.is_promoter && (
                        <span className="ml-2 rounded border border-border-lit px-1.5 py-0.5
                                         text-[10px] text-muted">promoter</span>
                      )}
                    </td>
                    <td className="tnum px-4 py-2.5 text-right text-muted">{d.pct_pre ?? "—"}%</td>
                    <td className="tnum px-4 py-2.5 text-right text-ink">{d.pct_post}%</td>
                    <td className={`tnum px-4 py-2.5 text-right ${
                      Number(d.change_pp) < 0 ? "text-block" : "text-pass"}`}>
                      {d.change_pp ? `${Number(d.change_pp) > 0 ? "+" : ""}${d.change_pp} pp` : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        </section>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <section>
          <SectionTitle hint={`${a.approvals.length}`}>Approvals required</SectionTitle>
          {a.approvals.length === 0
            ? <p className="text-sm text-muted">None derived from the approved rule set.</p>
            : <div className="space-y-2">{a.approvals.map((ap) => (
                <Card key={ap.approval_code} className="p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-sm text-ink">{ap.name}</p>
                      <p className="mt-1 font-mono text-[11px] text-faint">
                        {ap.stage.toLowerCase().replace("_", " ")} · caused by {ap.caused_by_rule}
                      </p>
                    </div>
                    <span className="shrink-0 rounded border border-border-lit bg-surface-2
                                     px-2 py-0.5 text-[10px] text-muted">{ap.authority}</span>
                  </div>
                </Card>
              ))}</div>}
        </section>

        <section>
          <SectionTitle hint={`${a.document_requirements.length}`}>Documents required</SectionTitle>
          {a.document_requirements.length === 0
            ? <p className="text-sm text-muted">None derived from the approved rule set.</p>
            : <div className="space-y-2">{a.document_requirements.map((d) => (
                <Card key={d.requirement_code} className="p-4">
                  <p className="text-sm text-ink">{d.name}</p>
                  <p className="mt-1 font-mono text-[11px] text-faint">
                    {d.stage.toLowerCase().replace("_", " ")} · {d.necessity.toLowerCase()} ·
                    caused by {d.caused_by_rule}
                  </p>
                </Card>
              ))}</div>}
        </section>
      </div>

      {a.assumptions.length > 0 && (
        <section>
          <SectionTitle>Assumptions</SectionTitle>
          <Card className="divide-y divide-border">
            {a.assumptions.map((s, i) => (
              <p key={i} className="px-4 py-3 text-[13px] leading-relaxed text-muted">{s.message}</p>
            ))}
          </Card>
        </section>
      )}

      <section>
        <SectionTitle>Audit</SectionTitle>
        <Card className="p-4">
          <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-1.5 font-mono text-[11px]">
            {[
              ["Assessment", a.assessment_id],
              ["Engine", a.engine_version],
              ["Transaction date", a.transaction_date],
              ["Rule versions pinned", String(a.audit.rule_versions_used.length)],
              ["Calc versions pinned", String(a.audit.calculation_versions_used.length)],
              ["Reproducible", String(a.audit.reproducible)],
            ].map(([k, v]) => (
              <div key={k} className="contents">
                <dt className="text-muted">{k}</dt><dd className="text-ink-2">{v}</dd>
              </div>
            ))}
          </dl>
          <p className="mt-3 border-t border-border pt-3 text-[11px] leading-relaxed text-faint">
            {a.disclaimer}
          </p>
        </Card>
      </section>
    </div>
  );
}

function RuleCard({ r }: { r: RuleResult }) {
  const accent = {
    BLOCK: "border-l-block", REVIEW_REQUIRED: "border-l-review",
    WARNING: "border-l-warn", PASS: "border-l-pass", NOT_APPLICABLE: "border-l-na",
  }[r.status];
  return (
    <Card className={`border-l-2 p-5 ${accent}`}>
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <span className="font-mono text-[11px] font-semibold text-accent-hi">{r.rule_code}</span>
        <span className="text-sm font-medium text-ink">{r.title}</span>
        <span className="ml-auto flex items-center gap-2">
          {r.demo_approved && (
            <span className="rounded border border-warn/30 bg-warn-bg px-1.5 py-0.5
                             font-mono text-[10px] text-warn">demo approval</span>
          )}
          <StatusBadge status={r.status} />
        </span>
      </div>
      <p className="text-sm leading-relaxed text-ink-2">{r.message}</p>
      <p className="mt-2 text-[13px] leading-relaxed text-muted">{r.explanation}</p>
      {r.missing_field && (
        <p className="mt-2 rounded border border-review/25 bg-review-bg px-3 py-2 font-mono text-[11px] text-review">
          missing fact: {r.missing_field}
        </p>
      )}
      {r.exception_applied && (
        <p className="mt-2 rounded border border-border-lit bg-surface-2 px-3 py-2 text-[12px] text-ink-2">
          <span className="font-mono text-[11px] text-muted">
            {r.exception_applied.exception_code}
          </span>{" — "}{r.exception_applied.condition}
        </p>
      )}
      {r.requirement && (
        <details className="mt-2">
          <summary className="cursor-pointer text-xs text-muted hover:text-accent-hi">
            Requirement
          </summary>
          <p className="mt-1.5 border-l-2 border-border-lit pl-3 text-[13px] leading-relaxed text-ink-2">
            {r.requirement}
          </p>
        </details>
      )}
      <SourceChip source={r.source_reference} />
    </Card>
  );
}
