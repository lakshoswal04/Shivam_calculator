"use client";
import { type Company } from "@/lib/api";
import { useCompanySearch } from "@/lib/useCompanySearch";
import { Badge, Button, ChoiceCard, SearchInput } from "@/components/ui";

const PAGE = 25;

/** A company with no CIN is the user's own record. Say that, and only that. */
export function CompanyBadges({ company }: { company: Company }) {
  return (
    <span className="ml-2 inline-flex gap-1.5 align-middle">
      {!company.cin && (
        <Badge tone="warn" title="Added by a user. No CIN is on file and nothing is verified against any register.">
          user-entered
        </Badge>
      )}
      {company.face_value === null && (
        <Badge title="No capital structure is recorded yet, so this company cannot be assessed until it is.">
          setup incomplete
        </Badge>
      )}
    </span>
  );
}

export function CompanySearch({ selectedId, onSelect, onAddNew }: {
  selectedId: string | null;
  onSelect: (c: Company) => void;
  onAddNew?: () => void;
}) {
  const { query, setQuery, rows, total, busy, error, hasMore, loadMore } =
    useCompanySearch(PAGE);

  return (
    <div className="space-y-3">
      <SearchInput value={query} onChange={setQuery} busy={busy}
                   label="Search companies"
                   placeholder="Search by company name, CIN, ticker or ISIN" />

      {error && <p className="text-sm text-block">{error}</p>}

      {rows.length === 0 && !busy ? (
        <div className="rounded-xl border border-dashed border-border px-4 py-6 text-center">
          <p className="text-sm text-muted">
            {query ? `Nothing matches "${query}".` : "No companies on file yet."}
          </p>
          {onAddNew && (
            <Button className="mt-3" onClick={onAddNew}>+ Add a new company</Button>
          )}
        </div>
      ) : (
        <div className="space-y-2">
          {rows.map((c) => (
            <ChoiceCard key={c.company_id} selected={selectedId === c.company_id}
                        onClick={() => onSelect(c)} className="w-full">
              <div className="flex items-center justify-between gap-4">
                <div className="min-w-0">
                  <div className="truncate text-sm font-medium text-ink">
                    {c.name}<CompanyBadges company={c} />
                  </div>
                  <div className="truncate font-mono text-[11px] text-faint">
                    {c.cin ?? "no CIN"}
                    {" · "}{c.company_type?.toLowerCase()} · {c.listed_status?.toLowerCase()}
                    {c.ticker_symbol ? ` · ${c.ticker_symbol}` : ""}
                    {c.isin ? ` · ${c.isin}` : ""}
                  </div>
                </div>
                <div className="tnum shrink-0 text-right text-xs">
                  <div className="text-muted">shares issued</div>
                  <div className="text-ink-2">
                    {c.shares_issued === null ? "—" : Number(c.shares_issued).toLocaleString("en-IN")}
                  </div>
                </div>
              </div>
            </ChoiceCard>
          ))}
        </div>
      )}

      <div className="flex items-center justify-between gap-3">
        <span className="text-xs text-faint">
          {rows.length} of {total} {total === 1 ? "company" : "companies"}
        </span>
        <div className="flex gap-2">
          {hasMore && (
            <Button variant="ghost" disabled={busy} onClick={loadMore}>
              Load more
            </Button>
          )}
          {onAddNew && rows.length > 0 && (
            <Button variant="ghost" onClick={onAddNew}>+ Add new company</Button>
          )}
        </div>
      </div>
    </div>
  );
}
