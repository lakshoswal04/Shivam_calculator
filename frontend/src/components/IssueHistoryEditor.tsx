"use client";
import { type IssueHistoryBody, type RouteInfo } from "@/lib/api";
import { Field, Input, Select } from "@/components/ui";
import { RowEditor } from "@/components/RowEditor";

const STATUSES = [
  { value: "ALLOTTED", label: "Allotted" },
  { value: "CLOSED", label: "Closed" },
  { value: "OPEN", label: "Open" },
  { value: "ANNOUNCED", label: "Announced" },
  { value: "PLANNED", label: "Planned" },
  { value: "WITHDRAWN", label: "Withdrawn" },
];

/** A fresh idempotency key per row, so a retried submission cannot duplicate it. */
const newRef = () =>
  (globalThis.crypto?.randomUUID?.() ??
    `${Date.now()}-${Math.random().toString(16).slice(2)}`);

export function IssueHistoryEditor({ rows, onChange, routes }: {
  rows: IssueHistoryBody[];
  onChange: (rows: IssueHistoryBody[]) => void;
  routes: RouteInfo[];
}) {
  const routeOptions = routes.map((r) => ({ value: r.issue_type, label: r.label }));

  return (
    <RowEditor<IssueHistoryBody>
      rows={rows}
      onChange={onChange}
      blank={() => ({ client_ref: newRef(), issue_type: "", status: "ALLOTTED" })}
      addLabel="+ Add a previous issue"
      empty="No previous issues recorded. Rules that depend on what the company has already done — such as limits counted across a financial year — cannot consider them."
      render={(row, update) => (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Field label="Route">
            <Select value={row.issue_type} onChange={(v) => update({ issue_type: v })}
                    options={routeOptions} placeholder="Select a route" />
          </Field>
          <Field label="Status">
            <Select value={row.status ?? "ALLOTTED"} onChange={(v) => update({ status: v })}
                    options={STATUSES} placeholder="Allotted" />
          </Field>
          <Field label="Allotment date">
            <Input type="date" value={row.allotment_date ?? ""}
                   onChange={(v) => update({ allotment_date: v || null })} />
          </Field>
          <Field label="Securities issued">
            <Input type="number" value={row.shares_offered?.toString() ?? ""}
                   onChange={(v) => update({ shares_offered: v ? Number(v) : null })} />
          </Field>
          <Field label="Issue price (₹)">
            <Input type="number" step="0.01" value={row.issue_price?.toString() ?? ""}
                   onChange={(v) => update({ issue_price: v ? Number(v) : null })} />
          </Field>
          <Field label="Issue opened">
            <Input type="date" value={row.issue_open_date ?? ""}
                   onChange={(v) => update({ issue_open_date: v || null })} />
          </Field>
          <Field label="Issue closed">
            <Input type="date" value={row.issue_close_date ?? ""}
                   onChange={(v) => update({ issue_close_date: v || null })} />
          </Field>
          <Field label="Board resolution">
            <Input type="date" value={row.board_resolution_date ?? ""}
                   onChange={(v) => update({ board_resolution_date: v || null })} />
          </Field>
        </div>
      )}
    />
  );
}
