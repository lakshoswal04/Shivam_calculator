"use client";
import { useEffect, useState } from "react";
import { api, type AssessmentRow } from "@/lib/api";
import {
  Banner, Delta, Empty, ListRow, PageHeader, RowMark, StatusBadge,
} from "@/components/ui";

export default function HistoryPage() {
  const [rows, setRows] = useState<AssessmentRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api.assessments().then((r) => setRows(r.assessments)).catch((e) => setError(e.message));
  }, []);

  const list = rows ?? [];
  const blocked = list.filter((r) => r.overall_result === "BLOCK").length;
  const passed = list.filter((r) => r.overall_result === "PASS").length;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Assessment history"
        lead="Every assessment is immutable and pins the rule versions it used, so it can be
              reproduced after the law changes."
      />

      {list.length > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          <Delta tone="flat">{list.length} assessments</Delta>
          <Delta tone={passed > 0 ? "up" : "flat"}>{passed} passed</Delta>
          <Delta tone={blocked > 0 ? "down" : "flat"}>{blocked} blocked</Delta>
        </div>
      )}

      {error && <Banner tone="block" title="Could not load history">{error}</Banner>}
      {rows === null ? <p className="text-sm text-muted">Loading…</p>
        : rows.length === 0 ? <Empty title="No assessments yet" />
        : (
        <div className="space-y-2">
          {rows.map((r) => (
            <ListRow
              key={r.assessment_id}
              href={`/assessments/${r.assessment_id}`}
              lead={<RowMark>{(r.company_name || "?").slice(0, 2).toUpperCase()}</RowMark>}
              title={r.company_name}
              sub={`${r.issue_type.toLowerCase().replace(/_/g, " ")} · ${r.transaction_date}`}
              value={
                <span className="font-mono text-[11px] font-normal text-faint">
                  {r.run_at?.slice(0, 16).replace("T", " ")}
                </span>
              }
              trailing={<StatusBadge status={r.overall_result} />}
            />
          ))}
        </div>
      )}
    </div>
  );
}
