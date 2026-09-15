"use client";
import { useEffect, useMemo, useState } from "react";
import { api, type LegalSource, type ProvisionHit, type SourceGap } from "@/lib/api";
import { Banner, Card, Empty } from "@/components/ui";

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
            className="rounded bg-surface-2 px-1.5 py-0.5 font-mono text-[10px] text-muted">
        reference only
      </span>
    );
  }
  return (
    <span title="Nobody has recorded how far this text has been amended."
          className="rounded bg-surface-2 px-1.5 py-0.5 font-mono text-[10px] text-faint">
      currency unrecorded
    </span>
  );
}

export default function LegalLibraryPage() {
  const [sources, setSources] = useState<LegalSource[] | null>(null);
  const [gaps, setGaps] = useState<SourceGap[]>([]);
  const [error, setError] = useState<string | null>(null);

  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<ProvisionHit[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);

  useEffect(() => {
    api.sources().then((r) => setSources(r.sources)).catch((e) => setError(e.message));
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
    for (const list of groups.values()) {
      list.sort((a, b) => b.provision_count - a.provision_count);
    }
    return [...groups.entries()].sort((a, b) => a[0].localeCompare(b[0]));
  }, [sources]);

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
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Legal library</h1>
        <p className="mt-1 text-sm text-muted">
          Every document the platform reasons from, and how current each one is. Nothing here
          is legal advice; a citation locates text, it does not interpret it.
        </p>
      </div>

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
            className="min-w-0 flex-1 rounded border border-border bg-ground px-3 py-2 text-sm
                       placeholder:text-faint focus:border-accent/60 focus:outline-none" />
          <button type="submit" disabled={searching}
                  className="rounded border border-border-lit bg-surface-2 px-4 py-2 text-sm
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
            <p className="text-sm text-muted">
              {sources.length} documents · {totalProvisions.toLocaleString()} citable provisions
            </p>
            {byAuthority.map(([authority, list]) => (
              <Card key={authority} className="overflow-x-auto">
                <div className="border-b border-border px-4 py-2.5">
                  <h2 className="text-sm font-medium">{authority}</h2>
                </div>
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border text-left text-[11px] uppercase tracking-wider text-muted">
                      <th className="px-4 py-2 font-medium">Document</th>
                      <th className="px-4 py-2 font-medium">Type</th>
                      <th className="px-4 py-2 font-medium">Currency</th>
                      <th className="px-4 py-2 text-right font-medium">Pages</th>
                      <th className="px-4 py-2 text-right font-medium">Provisions</th>
                      <th className="px-4 py-2 font-medium">SHA-256</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {list.map((s) => (
                      <tr key={s.file_hash_short} className="hover:bg-surface-2">
                        <td className="px-4 py-2.5">
                          <span className="text-ink-2">{s.display_name}</span>
                          <span className="ml-2 font-mono text-[10px] text-faint">{s.source_priority}</span>
                          <div className="font-mono text-[10px] text-faint">{s.file_name}</div>
                        </td>
                        <td className="px-4 py-2.5 font-mono text-[11px] text-muted">
                          {s.document_type.toLowerCase().replace(/_/g, " ")}
                        </td>
                        <td className="px-4 py-2.5"><CurrencyBadge source={s} /></td>
                        <td className="px-4 py-2.5 text-right font-mono text-[11px] text-muted">
                          {s.page_count ?? "—"}
                        </td>
                        <td className="px-4 py-2.5 text-right font-mono text-[11px] text-muted">
                          {s.provision_count > 0 ? s.provision_count.toLocaleString() : "—"}
                        </td>
                        <td className="px-4 py-2.5 font-mono text-[10px] text-faint">{s.file_hash_short}…</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Card>
            ))}
          </>
        )}
    </div>
  );
}
