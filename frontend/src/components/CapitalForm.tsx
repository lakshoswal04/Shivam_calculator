"use client";
import { useMemo, useState } from "react";
import { rupees, type CapitalBody } from "@/lib/api";
import { Banner, Field, Input } from "@/components/ui";

const n = (v: string) => (v.trim() === "" ? null : Number(v));

/**
 * Authorised / issued / subscribed / paid-up capital, face value and share
 * count. The ordering rules are checked here as well as server-side so the
 * user sees which two figures conflict before submitting rather than after.
 */
export function CapitalForm({ value, onChange }: {
  value: CapitalBody | null;
  onChange: (body: CapitalBody | null) => void;
}) {
  const [f, setF] = useState({
    authorised_capital: value?.authorised_capital?.toString() ?? "",
    issued_capital: value?.issued_capital?.toString() ?? "",
    subscribed_capital: value?.subscribed_capital?.toString() ?? "",
    paid_up_capital: value?.paid_up_capital?.toString() ?? "",
    face_value: value?.face_value?.toString() ?? "",
    shares_issued: value?.shares_issued?.toString() ?? "",
  });

  const v = useMemo(() => ({
    authorised: n(f.authorised_capital), issued: n(f.issued_capital),
    subscribed: n(f.subscribed_capital), paidUp: n(f.paid_up_capital),
    faceValue: n(f.face_value), shares: n(f.shares_issued),
  }), [f]);

  const subscribed = v.subscribed ?? v.issued;
  const paidUp = v.paidUp ?? subscribed;

  const errors = {
    issued: v.issued !== null && v.authorised !== null && v.issued > v.authorised
      ? "Issued capital cannot exceed authorised capital." : null,
    subscribed: v.subscribed !== null && v.issued !== null && v.subscribed > v.issued
      ? "Subscribed capital cannot exceed issued capital." : null,
    paidUp: paidUp !== null && subscribed !== null && paidUp > subscribed
      ? "Paid-up capital cannot exceed subscribed capital." : null,
  };

  // Shares are not re-derived from capital / face value: a company may have
  // classes at different face values, and silently overwriting an entered
  // count would hide the discrepancy rather than surface it.
  const impliedShares = v.issued !== null && v.faceValue ? v.issued / v.faceValue : null;
  const mismatch = impliedShares !== null && v.shares !== null
    && Math.abs(impliedShares - v.shares) > 1;

  function update(key: keyof typeof f, raw: string) {
    const next = { ...f, [key]: raw };
    setF(next);
    const num = (k: keyof typeof f) => (next[k].trim() === "" ? null : Number(next[k]));
    const a = num("authorised_capital"), i = num("issued_capital");
    const fv = num("face_value"), sh = num("shares_issued");
    const ok = a !== null && a > 0 && i !== null && i >= 0
      && fv !== null && fv > 0 && sh !== null && sh >= 0
      && i <= a;
    onChange(ok ? {
      authorised_capital: a, issued_capital: i,
      subscribed_capital: num("subscribed_capital"),
      paid_up_capital: num("paid_up_capital"),
      face_value: fv, shares_issued: sh,
    } : null);
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Face value per share (₹)" required>
          <Input type="number" step="0.01" value={f.face_value}
                 onChange={(x) => update("face_value", x)} />
        </Field>
        <Field label="Shares issued" required>
          <Input type="number" value={f.shares_issued}
                 onChange={(x) => update("shares_issued", x)} invalid={mismatch} />
        </Field>
        <Field label="Authorised capital (₹)" required>
          <Input type="number" step="0.01" value={f.authorised_capital}
                 onChange={(x) => update("authorised_capital", x)} />
        </Field>
        <Field label="Issued capital (₹)" required error={errors.issued}>
          <Input type="number" step="0.01" value={f.issued_capital}
                 onChange={(x) => update("issued_capital", x)} invalid={!!errors.issued} />
        </Field>
        <Field label="Subscribed capital (₹)" error={errors.subscribed}
               hint="Defaults to issued capital.">
          <Input type="number" step="0.01" value={f.subscribed_capital}
                 onChange={(x) => update("subscribed_capital", x)} invalid={!!errors.subscribed} />
        </Field>
        <Field label="Paid-up capital (₹)" error={errors.paidUp}
               hint="Defaults to subscribed capital.">
          <Input type="number" step="0.01" value={f.paid_up_capital}
                 onChange={(x) => update("paid_up_capital", x)} invalid={!!errors.paidUp} />
        </Field>
      </div>

      {mismatch && impliedShares !== null && (
        <Banner tone="warn" title="Share count does not match issued capital">
          Issued capital divided by face value implies{" "}
          {Math.round(impliedShares).toLocaleString("en-IN")} shares, but{" "}
          {v.shares?.toLocaleString("en-IN")} are recorded. That is legitimate where more
          than one class exists at different face values; otherwise one of the figures is
          wrong. Nothing is changed for you — the assessment will use what you enter.
        </Banner>
      )}

      {v.authorised !== null && v.faceValue ? (
        <p className="text-xs text-faint">
          Authorised capital of {rupees(v.authorised)} supports{" "}
          {Math.floor(v.authorised / v.faceValue).toLocaleString("en-IN")} shares in total.
        </p>
      ) : null}
    </div>
  );
}
