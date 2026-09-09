"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api, inr, rupees, type Company, type SourceGap } from "@/lib/api";
import { Banner, Button, Card, Empty, SectionTitle } from "@/components/ui";

export default function CompaniesPage() {
  const [companies, setCompanies] = useState<Company[] | null>(null);
  const [gaps, setGaps] = useState<SourceGap[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.companies().then((r) => setCompanies(r.companies)).catch((e) => setError(e.message));
    api.sourceGaps().then((r) => setGaps(r.gaps.filter((g) => !g.resolved_at))).catch(() => {});
  }, []);

  const blocker = gaps.find((g) => g.severity === "BLOCKER");

  return (
    <div className="space-y-8">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Companies</h1>
          <p className="mt-1 text-sm text-muted">
            Client companies in your organisation. Select one to assess a proposed issue.
          </p>
        </div>
        <Button href="/assess">New assessment</Button>
      </div>

      {blocker && (
        <Banner tone="warn" title={blocker.title}>
          <p>{blocker.detail}</p>
          <p className="mt-2 text-ink-2">
            <span className="font-medium">Affects:</span>{" "}
            {blocker.blocks_issue_types.join(", ").toLowerCase().replace(/_/g, " ")} —
            these routes still produce every calculation, but their legal conclusions are
            returned as review-required.
          </p>
        </Banner>
      )}

      {error && <Banner tone="block" title="Could not load companies">{error}</Banner>}

      {companies === null ? (
        <p className="text-sm text-muted">Loading…</p>
      ) : companies.length === 0 ? (
        <Empty title="No companies yet">Add a company to run its first assessment.</Empty>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {companies.map((c) => {
            const authShares = c.authorised_capital && c.face_value
              ? Math.floor(c.authorised_capital / c.face_value) : null;
            const available = authShares && c.shares_issued != null
              ? authShares - c.shares_issued : null;
            return (
              <Card key={c.company_id} className="p-5">
                <div className="mb-3 flex items-start justify-between gap-3">
                  <div>
                    <h3 className="font-medium leading-tight text-ink">{c.name}</h3>
                    <p className="mt-1 font-mono text-[11px] text-faint">{c.cin ?? "CIN not recorded"}</p>
                  </div>
                  <span className={`shrink-0 rounded border px-2 py-0.5 text-[10px] font-medium
                    ${c.listed_status === "LISTED"
                      ? "border-accent/30 bg-accent-dim/40 text-accent-hi"
                      : "border-border-lit bg-surface-2 text-muted"}`}>
                    {c.listed_status?.toLowerCase()}
                  </span>
                </div>
                <dl className="tnum space-y-1.5 text-[13px]">
                  <div className="flex justify-between">
                    <dt className="text-muted">Authorised</dt>
                    <dd className="text-ink-2">{rupees(c.authorised_capital)}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-muted">Issued shares</dt>
                    <dd className="text-ink-2">{inr(c.shares_issued)}</dd>
                  </div>
                  <div className="flex justify-between border-t border-border pt-1.5">
                    <dt className="text-muted">Capital headroom</dt>
                    <dd className="font-medium text-accent-hi">{inr(available)} shares</dd>
                  </div>
                </dl>
                <p className="mt-2 text-[11px] leading-relaxed text-faint">
                  Headroom is arithmetic only — it is not what the company may lawfully issue.
                </p>
                <div className="mt-4 flex gap-2">
                  <Button href={`/assess?company=${c.company_id}`} className="flex-1">Assess</Button>
                  <Link href={`/assessments?company=${c.company_id}`}
                        className="grid place-items-center rounded-md border border-border-lit
                                   px-3 text-xs text-muted hover:text-ink-2">History</Link>
                </div>
              </Card>
            );
          })}
        </div>
      )}

      {gaps.length > 0 && (
        <section>
          <SectionTitle hint={`${gaps.length} open`}>Known source gaps</SectionTitle>
          <div className="space-y-2">
            {gaps.map((g) => (
              <Card key={g.code} className="p-4">
                <div className="flex items-start gap-3">
                  <span className={`mt-0.5 shrink-0 rounded border px-1.5 py-0.5 font-mono text-[10px]
                    ${g.severity === "BLOCKER" ? "border-block/30 bg-block-bg text-block"
                                               : "border-warn/30 bg-warn-bg text-warn"}`}>
                    {g.severity}
                  </span>
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-ink">{g.title}</p>
                    <p className="mt-1 text-[13px] leading-relaxed text-muted">{g.detail}</p>
                    {g.provisions_required.length > 0 && (
                      <p className="mt-1.5 font-mono text-[11px] text-faint">
                        needs: {g.provisions_required.join(", ")}
                      </p>
                    )}
                  </div>
                </div>
              </Card>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
