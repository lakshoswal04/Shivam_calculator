"use client";
import { useEffect, useMemo, useState } from "react";
import { api, type LegalSource, type ProvisionHit, type SourceGap } from "@/lib/api";
import { Banner, Card, Empty, PageHeader, thCls, tdCls } from "@/components/ui";

/** A source amended this long ago or more is shown as possibly superseded. */
const STALE_AFTER_YEARS = 3;

function yearsSince(iso: string): number {
  return (Date.now() - new Date(iso).getTime()) / (365.25 * 24 * 3600 * 1000);
}

/** What the corpus knows about how current a document is — never a guess. */
function CurrencyBadge({ source }: { source: LegalSource }) {
  const { consolidation_status: status, as_amended_upto: upto } = source;
  if (status === "CONSOLIDATED" && upto) {
    const stale = yearsSince(upto) >= STALE_AFTER_YEARS;
    return (
      <span
        title={stale
          ? `Consolidated to ${upto}. Later amendments, if any, are not in this text.`
          : `Consolidated to ${upto}.`}
        className={`rounded px-1.5 py-0.5 font-mono text-[10px] ${
          stale ? "bg-warn/10 text-warn" : "bg-surface-2 text-muted"}`}>
        {stale ? "amended to " : "current to "}{upto}
      </span>
    );
  }
  if (status === "REFERENCE_ONLY") {
    return (
      <span title="Guidance, not law. Cannot source an approved rule."
            className="rounded-full bg-surface-2 px-1.5 py-0.5 font-mono text-[10px] text-muted">
        reference only
      </span>
    );
  }
  return (
    <span title="Nobody has recorded how far this text has been amended."
          className="rounded-full bg-surface-2 px-1.5 py-0.5 font-mono text-[10px] text-faint">
      currency unrecorded
    </span>
  );
}

/** Whether this edition is the law in force, and on whose authority we say so. */
function SupersessionBadge({ source }: { source: LegalSource }) {
  if (source.status !== "SUPERSEDED") return null;
  const replacedBy = source.superseded_by_date
    ? `the ${source.superseded_by_date} edition`
    : "a later edition";
  const basis = source.supersession_basis === "DECLARED"
    ? "Confirmed by a reviewer."
    : "Inferred from the title and date by the ingestion pipeline, not confirmed by a reviewer.";
  return (
    <span title={`Replaced by ${replacedBy}. ${basis}`}
          className="rounded-full bg-warn/10 px-1.5 py-0.5 font-mono text-[10px] text-warn">
      superseded
    </span>
  );
}

/** One circular and every earlier edition of it the corpus holds. */
interface Family {
  key: string;
  current: LegalSource;
  earlier: LegalSource[];
}

/** Group editions of a reissued circular under the one in force.
 *
 * A document with no family, or the only edition of its family, is a family of
 * one and renders exactly as it did before. */
function toFamilies(list: LegalSource[]): Family[] {
  const grouped = new Map<string, LegalSource[]>();
  for (const s of list) {
    const key = s.document_family ?? `__solo__${s.file_hash_short}`;
    grouped.set(key, [...(grouped.get(key) ?? []), s]);
  }
  return [...grouped.entries()].map(([key, editions]) => {
    const sorted = [...editions].sort(
      (a, b) => (b.publication_date ?? "").localeCompare(a.publication_date ?? ""));
    // The in-force edition leads even where the API returned it second.
    const idx = Math.max(0, sorted.findIndex((s) => s.status !== "SUPERSEDED"));
    return { key, current: sorted[idx], earlier: sorted.filter((_, i) => i !== idx) };
  });
}

function FamilyRows({ family }: { family: Family }) {
  const [open, setOpen] = useState(false);
  const { current, earlier } = family;
  return (
    <>
      <SourceRow source={current} />
      {earlier.length > 0 && (
        <tr className="bg-surface-2/40">
          <td colSpan={6} className="px-5 py-2">
            <button type="button" onClick={() => setOpen((v) => !v)}
                    aria-expanded={open}
                    className="text-[11px] text-muted hover:text-accent-hi">
              {open ? "▾" : "▸"} {earlier.length} earlier edition
              {earlier.length > 1 ? "s" : ""} of this circular
            </button>
          </td>
        </tr>
      )}
      {open && earlier.map((s) => <SourceRow key={s.file_hash_short} source={s} nested />)}
    </>
  );
}

function SourceRow({ source: s, nested = false }: { source: LegalSource; nested?: boolean }) {
  return (
    <tr className={nested ? "bg-surface-2/20" : "hover:bg-surface-2"}>
      <td className={`py-3.5 pr-5 ${nested ? "pl-12" : "px-5"}`}>
        <span className="text-ink-2">{s.display_name}</span>
        <span className="ml-2 font-mono text-[10px] text-faint">{s.source_priority}</span>
        {s.publication_date && (
          <span className="ml-2 font-mono text-[10px] text-faint">{s.publication_date}</span>
        )}
        <div className="font-mono text-[10px] text-faint">
          {s.official_url
            ? <a href={s.official_url} target="_blank" rel="noopener noreferrer"
                 className="hover:text-accent-hi hover:underline">{s.file_name}</a>
            : s.file_name}
        </div>
      </td>
      <td className={`${tdCls} font-mono text-[11px] text-muted`}>
        {s.document_type.toLowerCase().replace(/_/g, " ")}
      </td>
      <td className={tdCls}>
        <div className="flex flex-wrap items-center gap-1">
          <SupersessionBadge source={s} />
          <CurrencyBadge source={s} />
        </div>
      </td>
      <td className={`${tdCls} text-right font-mono text-[11px] text-muted`}>
        {s.page_count ?? "—"}
      </td>
      <td className={`${tdCls} text-right font-mono text-[11px] text-muted`}>
        {s.provision_count > 0 ? s.provision_count.toLocaleString() : "—"}
      </td>
      <td className={`${tdCls} font-mono text-[10px] text-faint`}>{s.file_hash_short}…</td>
    </tr>
  );
}

export default function LegalLibraryPage() {
  const [sources, setSources] = useState<LegalSource[] | null>(null);
  const [gaps, setGaps] = useState<SourceGap[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [showSuperseded, setShowSuperseded] = useState(false);

  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<ProvisionHit[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);

  useEffect(() => {
    setSources(null);
    api.sources(showSuperseded)
      .then((r) => setSources(r.sources))
      .catch((e) => setError(e.message));
  }, [showSuperseded]);

  useEffect(() => {
    api.sourceGaps()
      .then((r) => setGaps(r.gaps.filter((g) => !g.resolved_at)))
      .catch(() => { /* the library is still usable without the gap register */ });
  }, []);

  // Only documents that produced provisions can be cited, so they lead. The
  // rest are kept visible rather than hidden: a document in the corpus that
  // yielded nothing is a fact worth seeing.
  const byAuthority = useMemo(() => {
    const groups = new Map<string, LegalSource[]>();
    for (const s of sources ?? []) {
      const list = groups.get(s.authority) ?? [];
      list.push(s);
      groups.set(s.authority, list);
    }
    const out: Array<[string, Family[]]> = [];
    for (const [authority, list] of groups) {
      const families = toFamilies(list);
      // A family ranks by the edition in force, so a circular does not fall to
      // the bottom of the list merely because its older editions yielded less.
      families.sort((a, b) => b.current.provision_count - a.current.provision_count);
      out.push([authority, families]);
    }
    return out.sort((a, b) => a[0].localeCompare(b[0]));
  }, [sources]);

  const supersededShown = (sources ?? []).filter((s) => s.status === "SUPERSEDED").length;
  const inForceShown = (sources ?? []).length - supersededShown;

  async function search(e: React.FormEvent) {
    e.preventDefault();
    const q = query.trim();
    if (q.length < 3) { setSearchError("Enter at least three characters."); return; }
    setSearching(true); setSearchError(null);
    try {
      setHits((await api.searchProvisions(q)).results);
    } catch (err) {
      setSearchError((err as Error).message); setHits(null);
    } finally {
      setSearching(false);
    }
  }

  const totalProvisions = (sources ?? []).reduce((n, s) => n + s.provision_count, 0);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Legal library"
        lead="Every document the platform reasons from, and how current each one is. Nothing here
              is legal advice; a citation locates text, it does not interpret it."
      />

      {error && <Banner tone="block" title="Could not load the library">{error}</Banner>}

      {gaps.length > 0 && (
        <Banner tone="warn" title={`${gaps.length} source${gaps.length > 1 ? "s" : ""} the platform still needs`}>
          <ul className="space-y-2">
            {gaps.map((g) => (
              <li key={g.code}>
                <span className="font-mono text-[11px]">{g.severity}</span> · {g.title}
                {g.blocks_issue_types.length > 0 && (
                  <span className="text-muted"> — withholds conclusions on{" "}
                    {g.blocks_issue_types.join(", ").toLowerCase().replace(/_/g, " ")}</span>
                )}
              </li>
            ))}
          </ul>
        </Banner>
      )}

      <Card className="p-4">
        <form onSubmit={search} className="flex flex-wrap gap-2">
          <input
            value={query} onChange={(e) => setQuery(e.target.value)}
            placeholder="Search provisions — a citation like s.62(1)(a), or words in the text"
            aria-label="Search provisions"
            className="min-w-0 flex-1 rounded-xl border border-border bg-surface-2 px-3.5 py-2.5 text-sm
                       placeholder:text-faint focus:border-accent/60 focus:outline-none" />
          <button type="submit" disabled={searching}
                  className="rounded-full border border-border-lit bg-surface-2 px-4 py-2 text-sm
                             hover:border-accent/50 hover:text-accent-hi disabled:opacity-50">
            {searching ? "Searching…" : "Search"}
          </button>
        </form>
        {searchError && <p className="mt-2 text-sm text-block">{searchError}</p>}
        {hits !== null && (
          hits.length === 0
            ? <p className="mt-3 text-sm text-muted">No provision matches that.</p>
            : (
              <ul className="mt-3 divide-y divide-border">
                {hits.map((h) => (
                  <li key={h.citation_uid} className="py-2.5">
                    <div className="flex flex-wrap items-baseline gap-x-2">
                      <span className="font-mono text-[12px] text-accent-hi">{h.citation}</span>
                      {h.page_from && <span className="font-mono text-[11px] text-faint">p.{h.page_from}</span>}
                    </div>
                    <p className="mt-1 text-[13px] leading-relaxed text-ink-2">{h.excerpt}</p>
                  </li>
                ))}
              </ul>
            )
        )}
      </Card>

      {sources === null ? <p className="text-sm text-muted">Loading…</p>
        : sources.length === 0 ? <Empty title="The corpus is empty" />
        : (
          <>
            <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
              <p className="text-sm text-muted">
                {inForceShown} in force
                {supersededShown > 0 && <> · {supersededShown} superseded</>}
                {" "}· {totalProvisions.toLocaleString()} citable provisions
              </p>
              <label className="flex items-center gap-2 text-[13px] text-muted">
                <input type="checkbox" checked={showSuperseded}
                       onChange={(e) => setShowSuperseded(e.target.checked)}
                       className="accent-accent" />
                Show superseded editions
              </label>
            </div>
            {byAuthority.map(([authority, list]) => (
              <Card key={authority} className="overflow-x-auto">
                <div className="border-b border-border px-5 py-3.5">
                  <h2 className="text-sm font-semibold tracking-tight">{authority}</h2>
                </div>
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border">
                      <th className={thCls}>Document</th>
                      <th className={thCls}>Type</th>
                      <th className={thCls}>Currency</th>
                      <th className={`${thCls} text-right`}>Pages</th>
                      <th className={`${thCls} text-right`}>Provisions</th>
                      <th className={thCls}>SHA-256</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {list.map((f) => <FamilyRows key={f.key} family={f} />)}
                  </tbody>
                </table>
              </Card>
            ))}
          </>
        )}
    </div>
  );
}
