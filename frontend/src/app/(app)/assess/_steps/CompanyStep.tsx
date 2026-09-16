"use client";
import { useState } from "react";
import type { Company } from "@/lib/api";
import { Banner, Button, SectionTitle } from "@/components/ui";
import { CompanyForm, type CreatedCompany } from "@/components/CompanyForm";
import { CompanyBadges, CompanySearch } from "@/components/CompanySearch";

export function CompanyStep({ company, onSelect, onCreated }: {
  company: Company | null;
  onSelect: (c: Company) => void;
  onCreated: (c: CreatedCompany) => void;
}) {
  const [adding, setAdding] = useState(false);
  const [warnings, setWarnings] = useState<string[]>([]);

  if (adding) {
    return (
      <div className="space-y-4">
        <SectionTitle hint="Your own record">Add a company</SectionTitle>
        <CompanyForm
          onCancel={() => setAdding(false)}
          onCreated={(c) => { setWarnings(c.warnings); onCreated(c); }}
          submitLabel="Create and continue" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <SectionTitle>Select your company</SectionTitle>
      {warnings.length > 0 && (
        <Banner tone="warn" title="Check this is not a duplicate">
          <ul className="list-disc pl-4">{warnings.map((w) => <li key={w}>{w}</li>)}</ul>
        </Banner>
      )}
      {company && (
        <div className="rounded-md border border-accent bg-accent-dim/20 px-4 py-3">
          <div className="text-sm font-medium text-ink">
            {company.name}<CompanyBadges company={company} />
          </div>
          <div className="font-mono text-[11px] text-faint">
            {company.cin ?? "no CIN"} · {company.company_type?.toLowerCase()} ·{" "}
            {company.listed_status?.toLowerCase()}
            {company.exchanges?.length ? ` · ${company.exchanges.join(", ")}` : ""}
          </div>
        </div>
      )}
      <CompanySearch selectedId={company?.company_id ?? null}
                     onSelect={onSelect} onAddNew={() => setAdding(true)} />
      <p className="text-xs leading-relaxed text-faint">
        Any company in your organisation can be assessed, and you can add one that is not
        here yet — including a hypothetical company with no CIN.
      </p>
      {company && <Button className="sr-only" onClick={() => onSelect(company)}>Selected</Button>}
    </div>
  );
}
