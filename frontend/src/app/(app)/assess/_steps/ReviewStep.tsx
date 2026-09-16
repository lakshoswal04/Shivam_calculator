"use client";
import { inr, rupees, type Company, type RouteInfo } from "@/lib/api";
import { Banner, Button, SectionTitle } from "@/components/ui";
import type { IssueDraft } from "./IssueStep";

export function ReviewStep({ company, route, draft, extra, txnDate, busy, onRun }: {
  company: Company;
  route: RouteInfo | undefined;
  draft: IssueDraft;
  extra: Record<string, string | boolean>;
  txnDate: string;
  busy: boolean;
  onRun: () => void;
}) {
  const questions = route?.questions ?? [];
  const answered = Object.values(extra).filter((v) => v !== "").length;
  const n = Number(draft.shares_proposed || 0);
  const p = Number(draft.issue_price || 0);

  const rows: Array<[string, string]> = [
    ["Company", company.name],
    ["Classification",
     `${company.company_type?.toLowerCase()} · ${company.listed_status?.toLowerCase()}`],
    ["Route", route?.label ?? "—"],
    ["Securities", `${inr(draft.shares_proposed)} at ₹${draft.issue_price || "—"}`],
    ["Consideration", rupees(n && p ? n * p : null)],
    ["Transaction date", txnDate],
    ["Shareholders on file", company.holder_count ? String(company.holder_count) : "none"],
    ["Previous issues on file", company.issue_count ? String(company.issue_count) : "none"],
    ["Route answers", `${answered} of ${questions.length} answered`],
  ];

  return (
    <div className="space-y-4">
      <SectionTitle>Review and run</SectionTitle>

      {/* Said before the run, not discovered afterwards in the result. */}
      {route && route.authored_rule_count === 0 && (
        <Banner tone="warn" title={`No rules are authored for ${route.label}`}>
          Every calculation will be produced, but the legal conclusion is withheld rather than
          inferred from an empty rule set. The result will say so explicitly.
        </Banner>
      )}
      {company.holder_count === 0 && (
        <Banner tone="info" title="No cap table on file">
          Dilution cannot be shown and any rule turning on promoter holding will report
          review-required.
        </Banner>
      )}

      <dl className="divide-y divide-border rounded-md border border-border">
        {rows.map(([k, v]) => (
          <div key={k} className="flex justify-between gap-4 px-4 py-2.5 text-sm">
            <dt className="text-muted">{k}</dt>
            <dd className="tnum text-right text-ink-2">{v}</dd>
          </div>
        ))}
      </dl>

      <Button onClick={onRun} disabled={busy} className="w-full">
        {busy ? "Evaluating rules…" : "Run assessment"}
      </Button>
    </div>
  );
}
