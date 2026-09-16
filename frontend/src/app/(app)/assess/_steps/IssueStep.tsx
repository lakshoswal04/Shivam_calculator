"use client";
import { inr, rupees, type Company } from "@/lib/api";
import { Banner, Field, Input, SectionTitle } from "@/components/ui";

export interface IssueDraft {
  shares_proposed: string; issue_price: string; face_value: string;
}

export function IssueStep({ company, draft, onChange, txnDate, onTxnDate }: {
  company: Company;
  draft: IssueDraft;
  onChange: (d: IssueDraft) => void;
  txnDate: string;
  onTxnDate: (d: string) => void;
}) {
  const n = Number(draft.shares_proposed || 0);
  const p = Number(draft.issue_price || 0);
  const fv = Number(draft.face_value || 0);
  const authShares = company.authorised_capital && company.face_value
    ? Math.floor(company.authorised_capital / company.face_value) : null;
  const available = authShares !== null && company.shares_issued !== null
    ? authShares - company.shares_issued : null;
  const exceeds = available !== null && n > available;

  return (
    <div className="space-y-4">
      <SectionTitle>Proposed issue</SectionTitle>
      <div className="grid gap-4 sm:grid-cols-3">
        <Field label="Number of securities" required>
          <Input type="number" min="1" value={draft.shares_proposed}
                 onChange={(v) => onChange({ ...draft, shares_proposed: v })} />
        </Field>
        <Field label="Face value (₹)" required>
          <Input type="number" step="0.01" value={draft.face_value}
                 onChange={(v) => onChange({ ...draft, face_value: v })} />
        </Field>
        <Field label="Issue price (₹)">
          <Input type="number" step="0.01" value={draft.issue_price}
                 onChange={(v) => onChange({ ...draft, issue_price: v })} />
        </Field>
      </div>
      <Field label="Transaction date"
             hint="Selects which rule and calculation versions apply — not the run date.">
        <Input type="date" value={txnDate} onChange={onTxnDate} />
      </Field>

      <div className="tnum grid gap-3 rounded-md border border-border bg-ground p-4 sm:grid-cols-3">
        <div>
          <div className="text-[11px] uppercase tracking-wider text-muted">Consideration</div>
          <div className="mt-0.5 text-ink-2">{rupees(n && p ? n * p : null)}</div>
        </div>
        <div>
          <div className="text-[11px] uppercase tracking-wider text-muted">Premium / share</div>
          <div className="mt-0.5 text-ink-2">{rupees(p && fv ? p - fv : null)}</div>
        </div>
        <div>
          <div className="text-[11px] uppercase tracking-wider text-muted">Capital headroom</div>
          <div className={`mt-0.5 ${exceeds ? "text-block" : "text-ink-2"}`}>{inr(available)}</div>
        </div>
      </div>
      {exceeds && (
        <Banner tone="warn" title="Exceeds capital headroom">
          The proposal is larger than the shares available within authorised capital. The
          assessment will still run and will name this as the binding constraint.
        </Banner>
      )}
    </div>
  );
}
