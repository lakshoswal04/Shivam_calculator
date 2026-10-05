"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api, inr, rupees, type Company, type SourceGap } from "@/lib/api";
import {
  Badge, Banner, Button, Card, Empty, PageHeader, SectionTitle, Stat,
} from "@/components/ui";

export default function CompaniesPage() {
  const [companies, setCompanies] = useState<Company[] | null>(null);
  const [gaps, setGaps] = useState<SourceGap[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.companies().then((r) => setCompanies(r.companies)).catch((e) => setError(e.message));
    api.sourceGaps().then((r) => setGaps(r.gaps.filter((g) => !g.resolved_at))).catch(() => {});
  }, []);

  const blocker = gaps.find((g) => g.severity === "BLOCKER");

  // Portfolio totals, so the landing page opens on figures rather than a bare
  // list. Headroom is summed only where a capital structure is on file.
  const list = companies ?? [];
  const ready = list.filter((c) => c.face_value !== null).length;
  const headroom = list.reduce((n, c) => {
    if (!c.authorised_capital || !c.face_value || c.shares_issued == null) return n;
    return n + Math.max(0, Math.floor(c.authorised_capital / c.face_value) - c.shares_issued);
  }, 0);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Companies"
        lead="Client companies in your organisation. Select one to assess a proposed issue."
        actions={
          <>
            <Button variant="secondary" href="/companies/new">+ Add company</Button>
            <Button href="/assess">New assessment</Button>
          </>
        }
      />

      {list.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-3">
          <Card className="p-5">
            <Stat label="Companies on file" value={list.length} />
          </Card>
          <Card className="p-5">
            <Stat label="Ready to assess" value={ready}
                  delta={ready < list.length ? `${list.length - ready} need setup` : "all ready"}
                  deltaTone={ready < list.length ? "down" : "up"} />
          </Card>
          <Card className="p-5">
            <Stat label="Combined capital headroom" value={inr(headroom)} unit="shares"
                  sub="Arithmetic only — not what may lawfully be issued." />
          </Card>
        </div>
      )}

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
        <Empty title="No companies yet">
          <p>Add a company to run its first assessment.</p>
          <Button className="mt-4" href="/companies/new">+ Add your first company</Button>
        </Empty>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {companies.map((c) => {
            const authShares = c.authorised_capital && c.face_value
              ? Math.floor(c.authorised_capital / c.face_value) : null;
            const available = authShares && c.shares_issued != null
              ? authShares - c.shares_issued : null;
            return (
              <Card key={c.company_id} className="flex flex-col p-5">
                <div className="mb-3 flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h3 className="font-medium leading-tight text-ink">{c.name}</h3>
                    <p className="mt-1 font-mono text-[11px] text-faint">
                      {c.cin ?? "CIN not recorded"}
                      {c.ticker_symbol ? ` · ${c.ticker_symbol}` : ""}
                    </p>
                    {/* A CIN is format-checked only, so its absence is stated and
                        its presence is never described as verified. */}
                    <div className="mt-1.5 flex flex-wrap gap-1">
                      {!c.cin && (
                        <Badge tone="warn" title="Added by a user. Nothing is verified against any register.">
                          user-entered
                        </Badge>
                      )}
                      {c.face_value === null && (
                        <Badge title="No capital structure is recorded, so this company cannot be assessed yet.">
                          setup incomplete
                        </Badge>
                      )}
                    </div>
                  </div>
                  <span className={`shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-medium
                    ${c.listed_status === "LISTED"
                      ? "border-accent/30 bg-accent-dim/40 text-accent-hi"
                      : "border-border-lit bg-surface-2 text-muted"}`}>
                    {c.listed_status?.toLowerCase()}
                  </span>
                </div>
                <div className="rounded-2xl bg-surface-2/60 p-4">
                  <Stat label="Capital headroom" value={inr(available)} unit="shares" />
                  <dl className="tnum mt-3 space-y-1.5 border-t border-border pt-3 text-[13px]">
                    <div className="flex justify-between gap-3">
                      <dt className="text-muted">Authorised</dt>
                      <dd className="text-ink-2">{rupees(c.authorised_capital)}</dd>
                    </div>
                    <div className="flex justify-between gap-3">
                      <dt className="text-muted">Issued shares</dt>
                      <dd className="text-ink-2">{inr(c.shares_issued)}</dd>
                    </div>
                  </dl>
                </div>
                <p className="mt-2.5 text-[11px] leading-relaxed text-faint">
                  Headroom is arithmetic only — it is not what the company may lawfully issue.
                </p>
                <div className="mt-auto flex gap-2 pt-4">
                  {/* The profile is the step between picking a company and
                      choosing a transaction: it is where you check what is on
                      file before committing to an assessment. */}
                  <Button href={`/companies/${c.company_id}`} className="flex-1">
                    {c.face_value === null ? "Finish setup" : "Open"}
                  </Button>
                  <Link href={`/assess?company=${c.company_id}`}
                        className="grid place-items-center rounded-lg border border-border-lit
                                   px-3 text-xs text-muted hover:border-accent/50
                                   hover:text-accent">Assess</Link>
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
                  <span className={`mt-0.5 shrink-0 rounded-full border px-1.5 py-0.5 font-mono text-[10px]
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
