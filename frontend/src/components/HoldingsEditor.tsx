"use client";
import { useMemo } from "react";
import { type HoldingBody } from "@/lib/api";
import { CheckboxField, Field, Input, Select } from "@/components/ui";
import { RowEditor } from "@/components/RowEditor";

const CATEGORIES = [
  { value: "PROMOTER", label: "Promoter" },
  { value: "PROMOTER_GROUP", label: "Promoter group" },
  { value: "PUBLIC", label: "Public" },
  { value: "INSTITUTIONAL", label: "Institutional / QIB" },
  { value: "EMPLOYEE", label: "Employee" },
  { value: "BODY_CORPORATE", label: "Body corporate" },
];

export function HoldingsEditor({ rows, onChange, sharesIssued }: {
  rows: HoldingBody[];
  onChange: (rows: HoldingBody[]) => void;
  sharesIssued: number | null;
}) {
  const entered = useMemo(
    () => rows.reduce((t, r) => t + (Number(r.shares_held) || 0), 0), [rows]);
  // Shown, never corrected: ownership percentages are computed from what the
  // register actually says, and a gap between the two is information.
  const diff = sharesIssued === null ? null : entered - sharesIssued;

  return (
    <RowEditor<HoldingBody>
      rows={rows}
      onChange={onChange}
      blank={() => ({ name: "", shares_held: 0, category: "PUBLIC", is_promoter: false })}
      addLabel="+ Add shareholder"
      empty="No shareholders recorded. Without a cap table, dilution cannot be shown and rules that turn on promoter holding will report review-required."
      render={(row, update) => (
        <div className="grid gap-3 sm:grid-cols-[2fr_1fr_1fr]">
          <Field label="Name">
            <Input value={row.name} onChange={(v) => update({ name: v })}
                   placeholder="Promoter group" />
          </Field>
          <Field label="Shares held">
            <Input type="number" value={String(row.shares_held ?? "")}
                   onChange={(v) => update({ shares_held: Number(v) || 0 })} />
          </Field>
          <div className="space-y-2">
            <Field label="Category">
              <Select value={row.category ?? ""} onChange={(v) => update({ category: v })}
                      options={CATEGORIES} placeholder="Public" />
            </Field>
            <CheckboxField label="Promoter" checked={row.is_promoter}
                           onChange={(v) => update({ is_promoter: v })} />
          </div>
        </div>
      )}
      footer={
        <div className="tnum text-right text-xs">
          <div className="text-muted">
            {entered.toLocaleString("en-IN")} shares entered
            {sharesIssued !== null && ` of ${sharesIssued.toLocaleString("en-IN")} issued`}
          </div>
          {diff !== null && diff !== 0 && rows.length > 0 && (
            <div className="text-warn">
              {diff > 0 ? `${diff.toLocaleString("en-IN")} more than issued`
                        : `${Math.abs(diff).toLocaleString("en-IN")} unaccounted for`}
            </div>
          )}
        </div>
      }
    />
  );
}
