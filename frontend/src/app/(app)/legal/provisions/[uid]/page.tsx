"use client";
import Link from "next/link";
import { use, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Banner, Card } from "@/components/ui";

interface Provision {
  citation: string; citation_uid: string; provision_type: string; number: string;
  instrument_label: string | null; page_from: number | null; page_to: number | null;
  full_text: string | null; display_text: string | null;
  amended: boolean; amendment_markers: string[] | null;
  file_name: string; file_hash_short: string; authority: string;
  source_priority: string; citation_ambiguous: boolean; ancestry: string[];
}

export default function ProvisionPage({ params }: { params: Promise<{ uid: string }> }) {
  const { uid } = use(params);
  const [prov, setProv] = useState<Provision | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.provision(decodeURIComponent(uid))
      .then((r) => setProv(r as unknown as Provision))
      .catch((e) => setError(e.message));
  }, [uid]);

  if (error) {
    return (
      <div className="space-y-4">
        <Banner tone="block" title="Could not load that provision">{error}</Banner>
        <Link href="/legal" className="text-sm text-accent-hi hover:underline">← Legal library</Link>
      </div>
    );
  }
  if (!prov) return <p className="text-sm text-muted">Loading…</p>;

  return (
    <div className="space-y-6">
      <div>
        <Link href="/legal" className="text-sm text-muted hover:text-accent-hi">← Legal library</Link>
        <h1 className="mt-2 font-mono text-lg text-accent-hi">{prov.citation}</h1>
        {prov.ancestry.length > 0 && (
          <p className="mt-1 font-mono text-[11px] text-faint">{prov.ancestry.join(" › ")}</p>
        )}
      </div>

      {prov.citation_ambiguous && (
        <Banner tone="warn" title="This citation is not unique in its document">
          More than one provision carries this citation, so a rule must anchor to the uid
          below rather than to the citation string.
        </Banner>
      )}
      {prov.amended && (
        <Banner tone="warn" title="This text carries amendment markers">
          Passages here were substituted by a later amendment
          {prov.amendment_markers?.length ? ` (footnotes ${prov.amendment_markers.join(", ")})` : ""}.
          Read it against the amending instrument before relying on it.
        </Banner>
      )}

      <Card className="p-5">
        <p className="whitespace-pre-wrap text-[14px] leading-relaxed text-ink-2">
          {prov.full_text || prov.display_text || "No text was extracted for this provision."}
        </p>
      </Card>

      <Card className="p-5">
        <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-1.5 font-mono text-[11px] text-muted">
          <dt>Instrument</dt><dd className="text-ink-2">{prov.instrument_label ?? "—"}</dd>
          <dt>Type</dt><dd className="text-ink-2">{prov.provision_type.toLowerCase().replace(/_/g, " ")}</dd>
          <dt>Page</dt><dd className="text-ink-2">
            {prov.page_from ?? "—"}{prov.page_to && prov.page_to !== prov.page_from ? `–${prov.page_to}` : ""}
          </dd>
          <dt>Document</dt><dd className="text-ink-2">{prov.file_name}</dd>
          <dt>Authority</dt><dd className="text-ink-2">{prov.authority} · {prov.source_priority}</dd>
          <dt>SHA-256</dt><dd className="text-ink-2">{prov.file_hash_short}…</dd>
          <dt>Anchor</dt><dd className="text-ink-2">{prov.citation_uid}</dd>
        </dl>
      </Card>
    </div>
  );
}
