"use client";
import { ReactNode } from "react";
import { Button } from "@/components/ui";

/**
 * A repeating list of rows with add and remove.
 *
 * Deliberately generic: the cap table and the issue-history editor are the same
 * interaction over different fields, and the mismatch between what the rows add
 * up to and what is on file is worth showing in both.
 */
export function RowEditor<T>({
  rows, onChange, blank, render, addLabel, empty, footer, disabled,
}: {
  rows: T[];
  onChange: (rows: T[]) => void;
  blank: () => T;
  render: (row: T, update: (patch: Partial<T>) => void, index: number) => ReactNode;
  addLabel: string;
  empty?: ReactNode;
  footer?: ReactNode;
  disabled?: boolean;
}) {
  function update(index: number, patch: Partial<T>) {
    onChange(rows.map((r, i) => (i === index ? { ...r, ...patch } : r)));
  }

  return (
    <div className="space-y-3">
      {rows.length === 0 && empty && (
        <p className="text-sm text-muted">{empty}</p>
      )}
      {rows.map((row, i) => (
        <div key={i} className="rounded-md border border-border bg-surface-2/40 p-3">
          <div className="flex items-start gap-3">
            <div className="min-w-0 flex-1">{render(row, (patch) => update(i, patch), i)}</div>
            <button type="button" disabled={disabled}
                    onClick={() => onChange(rows.filter((_, j) => j !== i))}
                    aria-label={`Remove row ${i + 1}`}
                    className="mt-1 rounded border border-border-lit px-2 py-1 text-xs text-muted
                               hover:border-block/60 hover:text-block disabled:opacity-50">
              Remove
            </button>
          </div>
        </div>
      ))}
      <div className="flex items-center justify-between gap-3">
        <Button variant="ghost" disabled={disabled}
                onClick={() => onChange([...rows, blank()])}>
          {addLabel}
        </Button>
        {footer}
      </div>
    </div>
  );
}
