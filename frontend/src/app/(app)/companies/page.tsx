"use client";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useReveal } from "@/lib/useReveal";
import { api, inr, rupees, type SourceGap } from "@/lib/api";
import { useCompanySearch } from "@/lib/useCompanySearch";
import {
  Badge, Banner, Button, Card, Empty, PageHeader, SearchInput, SectionTitle, Stat,
} from "@/components/ui";

/** A page of cards, not the whole book. Twelve fills a wide grid four across
 *  without the page becoming a wall. */
const PAGE = 12;

export default function CompaniesPage() {
  const { query, setQuery, rows, total, busy, error, hasMore, loadMore } =
    useCompanySearch(PAGE);
  const [onlyIncomplete, setOnlyIncomplete] = useState(false);
  const [gaps, setGaps] = useState<SourceGap[]>([]);

  useEffect(() => {
    api.sourceGaps().then((r) => setGaps(r.gaps.filter((g) => !g.resolved_at))).catch(() => {});
  }, []);

  // The filter narrows what has been loaded rather than the query, because the
  // search endpoint has no "incomplete" parameter. The count says "of those
  // loaded" so the number is never mistaken for a total.
  const shown = useMemo(
    () => (onlyIncomplete ? rows.filter((c) => c.face_value === null) : rows),
    [rows, onlyIncomplete]);

  const incompleteLoaded = rows.filter((c) => c.face_value === null).length;
  const blocker = gaps.find((g) => g.severity === "BLOCKER");

  const reveal = useReveal<HTMLDivElement>();

  return (
    <div ref={reveal} className="space-y-6">
      <PageHeader
        title="Companies"
        lead="Client companies in your organisation. Open one to see what is on file, or start an assessment."
        actions={
          <>
            <Button variant="secondary" href="/companies/new">+ Add company</Button>
            <Button href="/assess">New assessment</Button>
          </>
        }
      />

      {blocker && (
        <Banner tone="warn" title={blocker.title}>
          <p>{blocker.detail}</p>
          {blocker.blocks_issue_types.length > 0 && (
            <p className="mt-2 text-ink-2">
              <span className="font-medium">Affects:</span>{" "}
              {blocker.blocks_issue_types.join(", ").toLowerCase().replace(/_/g, " ")} — these
              routes still produce every calculation, but their legal conclusions are returned
              as review-required.
            </p>
          )}
        </Banner>
      )}

      {/* ----------------------------------------------------------- search */}
      <Card className="p-4">
        <SearchInput value={query} onChange={setQuery} busy={busy}
                     label="Search companies"
                     placeholder="Search by company name, CIN, ticker or ISIN" />
        <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <FilterChip active={!onlyIncomplete} onClick={() => setOnlyIncomplete(false)}>
              All
            </FilterChip>
            <FilterChip active={onlyIncomplete} onClick={() => setOnlyIncomplete(true)}
                        count={incompleteLoaded}>
              Needs setup
            </FilterChip>
          </div>
          <span className="text-xs text-faint">
            {onlyIncomplete
              ? `${shown.length} of ${rows.length} loaded`
              : `${rows.length} of ${total} ${total === 1 ? "company" : "companies"}`}
          </span>
        </div>
      </Card>

      {error && <Banner tone="block" title="Could not load companies">{error}</Banner>}

      {/* ------------------------------------------------------------ cards */}
      {rows.length === 0 && busy ? (
        <p className="text-sm text-muted">Loading…</p>
      ) : shown.length === 0 ? (
        <Empty title={query ? `Nothing matches “${query}”`
                            : onlyIncomplete ? "Every loaded company has a capital structure"
                            : "No companies yet"}>
          {!query && !onlyIncomplete && (
            <>
              <p>Add a company to run its first assessment.</p>
              <Button className="mt-4" href="/companies/new">+ Add your first company</Button>
            </>
          )}
        </Empty>
      ) : (
        <>
          <div className="reveal grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {shown.map((c) => {
              const authShares = c.authorised_capital && c.face_value
                ? Math.floor(c.authorised_capital / c.face_value) : null;
              const available = authShares && c.shares_issued != null
                ? authShares - c.shares_issued : null;
              return (
                <Card key={c.company_id}
                      className="flex flex-col p-5 transition-shadow hover:shadow-md">
                  <div className="mb-3 flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <h3 className="truncate font-medium leading-tight text-ink">{c.name}</h3>
                      <p className="mt-1 truncate font-mono text-[11px] text-faint">
                        {c.cin ?? "CIN not recorded"}
                        {c.ticker_symbol ? ` · ${c.ticker_symbol}` : ""}
                      </p>
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
                        ? "border-accent/30 bg-accent-dim text-accent"
                        : "border-border-lit bg-surface-2 text-muted"}`}>
                      {c.listed_status?.toLowerCase()}
                    </span>
                  </div>

                  <div className="rounded-xl bg-surface-2 p-4">
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

          {hasMore && !onlyIncomplete && (
            <div className="flex justify-center">
              <Button variant="secondary" disabled={busy} onClick={loadMore}>
                {busy ? "Loading…" : `Load more (${total - rows.length} remaining)`}
              </Button>
            </div>
          )}
        </>
      )}

      {gaps.length > 0 && (
        <section>
          <SectionTitle hint={`${gaps.length} open`}>Known source gaps</SectionTitle>
          <div className="space-y-2">
            {gaps.map((g) => (
              <Card key={g.code} className="p-4">
                <div className="flex items-start gap-3">
                  <span className={`mt-0.5 shrink-0 rounded-full border px-2 py-0.5 font-mono text-[10px]
                    ${g.severity === "BLOCKER" ? "border-block/30 bg-block-bg text-block"
                                               : "border-warn/30 bg-warn-bg text-warn"}`}>
                    {g.severity}
                  </span>
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-ink">{g.title}</p>
                    <p className="mt-1 text-[13px] leading-relaxed text-muted">{g.detail}</p>
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

function FilterChip({ active, onClick, children, count }: {
  active: boolean; onClick: () => void; children: React.ReactNode; count?: number;
}) {
  return (
    <button type="button" onClick={onClick} aria-pressed={active}
            className={`rounded-full px-3 py-1 text-[12px] transition-colors ${
              active ? "bg-accent text-white"
                     : "border border-border bg-surface text-muted hover:border-accent/40"}`}>
      {children}
      {count != null && count > 0 && (
        <span className={`tnum ml-1.5 ${active ? "text-white/70" : "text-faint"}`}>{count}</span>
      )}
    </button>
  );
}
