"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api, type AssessmentRow } from "@/lib/api";
import { Banner, Card, Empty, StatusBadge } from "@/components/ui";

export default function HistoryPage() {
  const [rows, setRows] = useState<AssessmentRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api.assessments().then((r) => setRows(r.assessments)).catch((e) => setError(e.message));
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Assessment history</h1>
        <p className="mt-1 text-sm text-muted">
          Every assessment is immutable and pins the rule versions it used, so it can be
          reproduced after the law changes.
        </p>
      </div>
      {error && <Banner tone="block" title="Could not load history">{error}</Banner>}
      {rows === null ? <p className="text-sm text-muted">Loading…</p>
        : rows.length === 0 ? <Empty title="No assessments yet" />
        : (
        <Card className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-[11px] uppercase tracking-wider text-muted">
                <th className="px-4 py-2.5 font-medium">Company</th>
                <th className="px-4 py-2.5 font-medium">Route</th>
                <th className="px-4 py-2.5 font-medium">Transaction date</th>
                <th className="px-4 py-2.5 font-medium">Result</th>
                <th className="px-4 py-2.5 text-right font-medium">Run</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {rows.map((r) => (
                <tr key={r.assessment_id} className="hover:bg-surface-2">
                  <td className="px-4 py-2.5">
                    <Link href={`/assessments/${r.assessment_id}`}
                          className="text-ink-2 hover:text-accent-hi">{r.company_name}</Link>
                  </td>
                  <td className="px-4 py-2.5 text-muted">
                    {r.issue_type.toLowerCase().replace(/_/g, " ")}
                  </td>
                  <td className="tnum px-4 py-2.5 text-muted">{r.transaction_date}</td>
                  <td className="px-4 py-2.5"><StatusBadge status={r.overall_result} /></td>
                  <td className="tnum px-4 py-2.5 text-right text-[11px] text-faint">
                    {r.run_at?.slice(0, 16).replace("T", " ")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
