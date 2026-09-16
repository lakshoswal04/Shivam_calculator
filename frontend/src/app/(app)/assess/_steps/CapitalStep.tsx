"use client";
import { useState } from "react";
import type { CapitalBody, Company } from "@/lib/api";
import { Banner, Button, SectionTitle } from "@/components/ui";
import { CapitalForm } from "@/components/CapitalForm";

export function CapitalStep({ company, saving, error, onSave }: {
  company: Company;
  saving: boolean;
  error: string | null;
  onSave: (body: CapitalBody) => void;
}) {
  const [body, setBody] = useState<CapitalBody | null>(null);
  const onFile = company.face_value !== null;

  return (
    <div className="space-y-4">
      <SectionTitle hint={company.name}>Current share capital</SectionTitle>
      {onFile && (
        <Banner tone="info" title="Capital is already on file">
          Recorded as at {company.capital_as_of ?? "an earlier date"}. Entering figures here
          replaces that snapshot for today.
        </Banner>
      )}
      {error && <Banner tone="block" title="Could not save the capital structure">{error}</Banner>}
      <CapitalForm value={null} onChange={setBody} />
      <Button onClick={() => body && onSave(body)} disabled={!body || saving}>
        {saving ? "Saving…" : "Save and continue"}
      </Button>
      {!body && (
        <p className="text-xs text-faint">
          Authorised and issued capital, face value and the share count are all needed before
          an assessment can run.
        </p>
      )}
    </div>
  );
}
