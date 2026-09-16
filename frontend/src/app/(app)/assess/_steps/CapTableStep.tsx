"use client";
import { useState } from "react";
import type { Company, HoldingBody } from "@/lib/api";
import { Banner, Button, SectionTitle } from "@/components/ui";
import { HoldingsEditor } from "@/components/HoldingsEditor";

export function CapTableStep({ company, saving, error, onSave, onSkip }: {
  company: Company;
  saving: boolean;
  error: string | null;
  onSave: (rows: HoldingBody[]) => void;
  onSkip: () => void;
}) {
  const [rows, setRows] = useState<HoldingBody[]>([]);

  return (
    <div className="space-y-4">
      <SectionTitle hint="Optional">Shareholders</SectionTitle>
      <p className="text-sm text-muted">
        The cap table drives the dilution table and any rule that turns on promoter holding.
        Leaving it out is safe — the assessment records that it had none rather than assuming
        one.
      </p>
      {error && <Banner tone="block" title="Could not save the cap table">{error}</Banner>}
      <HoldingsEditor rows={rows} onChange={setRows}
                      sharesIssued={company.shares_issued} />
      <div className="flex gap-2">
        <Button onClick={() => onSave(rows)} disabled={rows.length === 0 || saving}>
          {saving ? "Saving…" : "Save and continue"}
        </Button>
        <Button variant="ghost" onClick={onSkip}>Skip — add later</Button>
      </div>
    </div>
  );
}
