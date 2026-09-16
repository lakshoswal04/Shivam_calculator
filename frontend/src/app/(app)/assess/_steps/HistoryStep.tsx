"use client";
import { useState } from "react";
import type { IssueHistoryBody, RouteInfo } from "@/lib/api";
import { Banner, Button, SectionTitle } from "@/components/ui";
import { IssueHistoryEditor } from "@/components/IssueHistoryEditor";

export function HistoryStep({ routes, saving, error, onSave, onSkip }: {
  routes: RouteInfo[];
  saving: boolean;
  error: string | null;
  onSave: (rows: IssueHistoryBody[]) => void;
  onSkip: () => void;
}) {
  const [rows, setRows] = useState<IssueHistoryBody[]>([]);
  const ready = rows.length > 0 && rows.every((r) => r.issue_type);

  return (
    <div className="space-y-4">
      <SectionTitle hint="Optional">Previous issues</SectionTitle>
      <p className="text-sm text-muted">
        Earlier transactions can condition what the company may do now. Anything recorded
        here is available to the rules; anything omitted is reported as an assumption rather
        than treated as though it never happened.
      </p>
      {error && <Banner tone="block" title="Could not save the issue history">{error}</Banner>}
      <IssueHistoryEditor rows={rows} onChange={setRows} routes={routes} />
      <div className="flex gap-2">
        <Button onClick={() => onSave(rows)} disabled={!ready || saving}>
          {saving ? "Saving…" : "Save and continue"}
        </Button>
        <Button variant="ghost" onClick={onSkip}>Skip — add later</Button>
      </div>
    </div>
  );
}
