"use client";
import Link from "next/link";
import { use, useEffect, useState } from "react";
import {
  api, inr, rupees, type AssessmentRow, type CompanyDetail,
} from "@/lib/api";
import {
  Badge, Banner, Button, Card, Empty, ListRow, PageHeader, RowMark,
  SectionTitle, Stat, StatusBadge, thCls, tdCls,
} from "@/components/ui";

/** The detail payload is loosely typed, so values are read defensively. */
function str(o: Record<string, unknown> | null | undefined, k: string): string | null {
  const v = o?.[k];
  return v == null || v === "" ? null : String(v);
}
function num(o: Record<string, unknown> | null | undefined, k: string): number | null {
  const v = o?.[k];
  return v == null || v === "" ? null : Number(v);
}

export default function CompanyProfilePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [d, setD] = useState<CompanyDetail | null>(null);
  const [runs, setRuns] = useState<AssessmentRow[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.company(id).then(setD).catch((e) => setError(e.message));
    api.assessments()
      .then((r) => setRuns(r.assessments.filter((a) => a.company_id === id)))
      .catch(() => {});
  }, [id]);

  if (error) {
    return (
      <div className="space-y-4">
        <Banner tone="block" title="Could not load that company">{error}</Banner>
        <Link href="/companies" className="text-sm text-accent hover:underline">← Companies</Link>
      </div>
    );
  }
  if (!d) return <p className="text-sm text-muted">Loading…</p>;

  const c = d.company;
  const cap = d.capital;
  const name = str(c, "name") ?? "Company";
  const faceValue = num(cap, "face_value");
  const authorised = num(cap, "authorised_capital");
  const sharesIssued = num(cap, "shares_issued");
  const authShares = authorised && faceValue ? Math.floor(authorised / faceValue) : null;
  const available = authShares != null && sharesIssued != null
    ? authShares - sharesIssued : null;
  const ready = faceValue != null;

  const totalHeld = d.holdings.reduce((n, h) => n + (h.shares_held || 0), 0);

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow={<Link href="/companies" className="hover:text-accent">← Companies</Link>}
        title={name}
        lead={
          <span className="flex flex-wrap items-center gap-1.5">
            <Badge>{(str(c, "company_type") ?? "").toLowerCase().replace(/_/g, " ")}</Badge>
            <Badge tone={str(c, "listed_status") === "LISTED" ? "accent" : "neutral"}>
              {(str(c, "listed_status") ?? "").toLowerCase()}
            </Badge>
            {str(c, "ticker_symbol") && <Badge>{str(c, "ticker_symbol")}</Badge>}
            {!str(c, "cin") && (
              <Badge tone="warn" title="Added by a user. Nothing is verified against any register.">
                user-entered
              </Badge>
            )}
          </span>
        }
        actions={
          <>
            <Button variant="secondary" href={`/assessments?company=${id}`}>History</Button>
            <Button href={`/assess?company=${id}`}>
              {ready ? "Start an assessment" : "Finish setup"}
            </Button>
          </>
        }
      />

      {!ready && (
        <Banner tone="warn" title="No capital structure on file">
          This company cannot be assessed until its authorised capital, face value and issued
          shares are recorded. The assessment wizard collects them as its first step.
        </Banner>
      )}

      {/* ------------------------------------------------------ capital */}
      <div className="grid gap-4 sm:grid-cols-3">
        <Card className="p-5">
          <Stat label="Capital headroom" value={available != null ? inr(available) : "—"}
                unit={available != null ? "shares" : undefined}
                sub="Arithmetic only — not what may lawfully be issued." />
        </Card>
        <Card className="p-5">
          <Stat label="Authorised capital" value={authorised != null ? rupees(authorised) : "—"}
                sub={faceValue != null ? `at ₹${faceValue} face value` : undefined} />
        </Card>
        <Card className="p-5">
          <Stat label="Issued shares" value={sharesIssued != null ? inr(sharesIssued) : "—"}
                sub={authShares != null ? `of ${inr(authShares)} authorised` : undefined} />
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* ------------------------------------------------- identity */}
        <section className="space-y-3">
          <SectionTitle>Company details</SectionTitle>
          <Card className="p-6">
            <dl className="divide-y divide-border">
              {([
                ["CIN", str(c, "cin") ?? "Not recorded"],
                ["Incorporated", str(c, "incorporation_date") ?? "—"],
                ["Registered office", str(c, "registered_office") ?? "—"],
                ["Exchanges", (c.exchanges as string[] | null)?.join(", ") || "—"],
                ["ISIN", str(c, "isin") ?? "—"],
                ["Capital as of", str(cap, "capital_as_of") ?? "—"],
              ] as const).map(([k, v]) => (
                <div key={k} className="flex items-baseline justify-between gap-4 py-2.5 text-sm">
                  <dt className="shrink-0 text-muted">{k}</dt>
                  <dd className="text-right text-ink">{v}</dd>
                </div>
              ))}
            </dl>
          </Card>
        </section>

        {/* ---------------------------------------------- shareholders */}
        <section className="space-y-3">
          <SectionTitle hint={d.holdings.length ? `${d.holdings.length} on file` : undefined}>
            Shareholders
          </SectionTitle>
          {d.holdings.length === 0
            ? <Empty title="No cap table on file">
                <p>Shareholders are captured during an assessment, and are what dilution is
                   measured against.</p>
              </Empty>
            : (
              <Card className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border">
                      <th className={thCls}>Holder</th>
                      <th className={`${thCls} text-right`}>Shares</th>
                      <th className={`${thCls} text-right`}>Share</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {d.holdings.map((h, i) => (
                      <tr key={i}>
                        <td className={tdCls}>
                          <span className="text-ink">{h.name}</span>
                          {h.is_promoter && <Badge title="Promoter group">promoter</Badge>}
                        </td>
                        <td className={`tnum ${tdCls} text-right text-ink`}>{inr(h.shares_held)}</td>
                        <td className={`tnum ${tdCls} text-right text-muted`}>
                          {totalHeld > 0 ? `${((h.shares_held / totalHeld) * 100).toFixed(2)}%` : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Card>
            )}
        </section>
      </div>

      {/* -------------------------------------------------- issue history */}
      {d.issues.length > 0 && (
        <section className="space-y-3">
          <SectionTitle hint={`${d.issues.length}`}>Previous issues</SectionTitle>
          <Card className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className={thCls}>Date</th>
                  <th className={thCls}>Route</th>
                  <th className={`${thCls} text-right`}>Shares</th>
                  <th className={`${thCls} text-right`}>Price</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {d.issues.map((it) => (
                  <tr key={it.issue_id}>
                    {/* An issue is dated by its allotment where that is known,
                        and falls back to the date it was resolved on. */}
                    <td className={`tnum ${tdCls} text-muted`}>
                      {it.allotment_date ?? it.shareholder_resolution_date
                        ?? it.board_resolution_date ?? "—"}
                    </td>
                    <td className={tdCls}>
                      {String(it.issue_type ?? "").toLowerCase().replace(/_/g, " ")}
                    </td>
                    <td className={`tnum ${tdCls} text-right text-ink`}>
                      {it.shares_offered != null ? inr(it.shares_offered) : "—"}
                    </td>
                    <td className={`tnum ${tdCls} text-right text-muted`}>
                      {it.issue_price != null ? rupees(it.issue_price) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        </section>
      )}

      {/* --------------------------------------------------- assessments */}
      <section className="space-y-3">
        <SectionTitle hint={runs.length ? `${runs.length}` : undefined}>
          Assessments for this company
        </SectionTitle>
        {runs.length === 0
          ? <Empty title="No assessments yet">
              <Button className="mt-4" href={`/assess?company=${id}`}>
                {ready ? "Start an assessment" : "Finish setup"}
              </Button>
            </Empty>
          : (
            <div className="space-y-2">
              {runs.map((r) => (
                <ListRow
                  key={r.assessment_id}
                  href={`/assessments/${r.assessment_id}`}
                  lead={<RowMark>{r.issue_type.slice(0, 2).toUpperCase()}</RowMark>}
                  title={r.issue_type.toLowerCase().replace(/_/g, " ")}
                  sub={`Transaction date ${r.transaction_date}`}
                  trailing={<StatusBadge status={r.overall_result} />}
                />
              ))}
            </div>
          )}
      </section>
    </div>
  );
}
