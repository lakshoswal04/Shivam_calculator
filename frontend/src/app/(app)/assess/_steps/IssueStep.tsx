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
    ? Math.max(0, authShares - company.shares_issued) : null;
  const exceeds = available !== null && n > available;
  const excess = exceeds && available !== null ? n - available : 0;

  const nominalIncrease = n * fv;
  const premiumPerShare = p > fv ? p - fv : 0;
  const totalPremium = n * premiumPerShare;
  const totalConsideration = n * p;

  return (
    <div className="space-y-4">
      <SectionTitle>Proposed issue</SectionTitle>
      <div className="grid gap-4 sm:grid-cols-3">
        <Field label="How many new shares do you want to issue?" required>
          <Input type="number" min="1" value={draft.shares_proposed}
                 onChange={(v) => onChange({ ...draft, shares_proposed: v })} placeholder="e.g. 1,00,000" />
        </Field>
        <Field label="Face value (₹)" required>
          <Input type="number" step="0.01" value={draft.face_value}
                 onChange={(v) => onChange({ ...draft, face_value: v })} />
        </Field>
        <Field label="Issue price (₹)" required>
          <Input type="number" step="0.01" value={draft.issue_price}
                 onChange={(v) => onChange({ ...draft, issue_price: v })} placeholder="e.g. 125" />
        </Field>
      </div>
      <Field label="Transaction date"
             hint="Selects which rule and calculation versions apply — not the run date.">
        <Input type="date" value={txnDate} onChange={onTxnDate} />
      </Field>

      <div className="tnum grid gap-3 rounded-xl border border-border bg-ground p-4 sm:grid-cols-4 text-xs">
        <div>
          <div className="uppercase tracking-wider text-muted font-semibold">Nominal Increase</div>
          <div className="mt-1 text-sm font-semibold text-ink-2">{rupees(nominalIncrease)}</div>
        </div>
        <div>
          <div className="uppercase tracking-wider text-muted font-semibold">Premium / Share</div>
          <div className="mt-1 text-sm font-medium text-ink-2">{rupees(premiumPerShare)}</div>
          <div className="text-[10px] text-faint">Total: {rupees(totalPremium)}</div>
        </div>
        <div>
          <div className="uppercase tracking-wider text-muted font-semibold">Total Consideration</div>
          <div className="mt-1 text-sm font-bold text-accent">{rupees(totalConsideration)}</div>
        </div>
        <div>
          <div className="uppercase tracking-wider text-muted font-semibold">Available Capacity</div>
          <div className={`mt-1 text-sm font-bold ${exceeds ? "text-warn" : "text-ink-2"}`}>
            {available !== null ? `${inr(available)} shares` : "—"}
          </div>
        </div>
      </div>

      {exceeds && available !== null && (
        <Banner tone="warn" title="⚠ Proposed issue exceeds current authorised share capacity">
          <div className="mt-1 space-y-1 text-xs leading-relaxed">
            <p>
              Available Capacity: <strong>{inr(available)} shares</strong> | Proposed Issue: <strong>{inr(n)} shares</strong> | Excess: <strong>{inr(excess)} shares</strong>
            </p>
            <p>
              Additional authorised capital may be required before allotment, subject to shareholder approval (Special Resolution in EGM) and filing Form SH-7 with the Registrar of Companies (ROC).
            </p>
          </div>
        </Banner>
      )}
    </div>
  );
}
