"use client";
import Link from "next/link";
import { ReactNode, useState } from "react";
import type { RuleStatus, SourceReference } from "@/lib/api";

/* Status is never carried by colour alone — every badge has a text label. */
const STATUS: Record<RuleStatus, { label: string; fg: string; bg: string; bd: string }> = {
  PASS:            { label: "Pass",            fg: "text-pass",   bg: "bg-pass-bg",   bd: "border-pass/30" },
  WARNING:         { label: "Warning",         fg: "text-warn",   bg: "bg-warn-bg",   bd: "border-warn/30" },
  BLOCK:           { label: "Blocked",         fg: "text-block",  bg: "bg-block-bg",  bd: "border-block/30" },
  REVIEW_REQUIRED: { label: "Review required", fg: "text-review", bg: "bg-review-bg", bd: "border-review/30" },
  NOT_APPLICABLE:  { label: "Not applicable",  fg: "text-na",     bg: "bg-na-bg",     bd: "border-na/25" },
};

export function StatusBadge({ status, size = "sm" }: { status: RuleStatus; size?: "sm" | "lg" }) {
  const s = STATUS[status] ?? STATUS.NOT_APPLICABLE;
  return (
    <span className={`inline-flex items-center gap-1.5 rounded border font-medium
      ${s.fg} ${s.bg} ${s.bd}
      ${size === "lg" ? "px-3 py-1.5 text-sm" : "px-2 py-0.5 text-[11px]"}`}>
      <span className="h-1.5 w-1.5 rounded-full bg-current" aria-hidden />
      {s.label}
    </span>
  );
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`rounded-lg border border-border bg-surface ${className}`}>{children}</div>
  );
}

export function SectionTitle({ children, hint }: { children: ReactNode; hint?: string }) {
  return (
    <div className="mb-3 flex items-baseline justify-between gap-4">
      <h2 className="text-[13px] font-semibold uppercase tracking-[0.09em] text-muted">{children}</h2>
      {hint && <span className="text-xs text-faint">{hint}</span>}
    </div>
  );
}

export function Button({
  children, onClick, type = "button", variant = "primary", disabled, className = "", href,
}: {
  children: ReactNode; onClick?: () => void; type?: "button" | "submit";
  variant?: "primary" | "ghost" | "danger"; disabled?: boolean; className?: string; href?: string;
}) {
  const base =
    "inline-flex items-center justify-center gap-2 rounded-md px-4 py-2 text-sm font-medium " +
    "transition-colors disabled:cursor-not-allowed disabled:opacity-50";
  const styles = {
    primary: "bg-accent text-white hover:bg-accent-hi",
    ghost: "border border-border-lit bg-surface-2 text-ink-2 hover:border-accent/60 hover:text-ink",
    danger: "border border-block/40 bg-block-bg text-block hover:border-block/70",
  }[variant];
  if (href) {
    return <Link href={href} className={`${base} ${styles} ${className}`}>{children}</Link>;
  }
  return (
    <button type={type} onClick={onClick} disabled={disabled}
            className={`${base} ${styles} ${className}`}>{children}</button>
  );
}

export function Field({ label, hint, children, required, error }:
  { label: string; hint?: string; children: ReactNode;
    required?: boolean; error?: string | null }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm text-ink-2">
        {label}{required && <span className="ml-1 text-accent">*</span>}
      </span>
      {children}
      {/* The error replaces the hint rather than stacking with it: two lines of
          small print under one input is harder to read than one. */}
      {error ? <span className="mt-1 block text-xs text-block">{error}</span>
        : hint ? <span className="mt-1 block text-xs text-faint">{hint}</span> : null}
    </label>
  );
}

export const inputCls =
  "w-full rounded-md border border-border bg-ground px-3 py-2 text-sm text-ink " +
  "placeholder:text-faint focus:border-accent focus:outline-none";

const invalidCls = "border-block/60 focus:border-block";

/** Text, number or date input. Carries its own invalid state and aria-invalid. */
export function Input({ value, onChange, type = "text", placeholder, invalid,
                        step, min, max, disabled, id }: {
  value: string; onChange: (v: string) => void;
  type?: "text" | "number" | "date"; placeholder?: string; invalid?: boolean;
  step?: string; min?: string; max?: string; disabled?: boolean; id?: string;
}) {
  return (
    <input id={id} type={type} value={value} placeholder={placeholder}
           step={step} min={min} max={max} disabled={disabled}
           aria-invalid={invalid || undefined}
           onChange={(e) => onChange(e.target.value)}
           className={`${inputCls} ${invalid ? invalidCls : ""} disabled:opacity-60`} />
  );
}

export function Select({ value, onChange, options, placeholder = "Not stated",
                         invalid, disabled }: {
  value: string; onChange: (v: string) => void;
  options: Array<{ value: string; label: string }>;
  placeholder?: string; invalid?: boolean; disabled?: boolean;
}) {
  return (
    <select value={value} disabled={disabled} aria-invalid={invalid || undefined}
            onChange={(e) => onChange(e.target.value)}
            className={`${inputCls} ${invalid ? invalidCls : ""} disabled:opacity-60`}>
      <option value="">{placeholder}</option>
      {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
}

export function CheckboxField({ label, checked, onChange, hint }: {
  label: string; checked: boolean; onChange: (v: boolean) => void; hint?: string;
}) {
  return (
    <label className="flex cursor-pointer items-start gap-2.5">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)}
             className="mt-0.5 h-4 w-4 rounded border-border accent-accent" />
      <span>
        <span className="block text-sm text-ink-2">{label}</span>
        {hint && <span className="block text-xs text-faint">{hint}</span>}
      </span>
    </label>
  );
}

/** Small inline marker. Duplicated in three places before this existed. */
export function Badge({ children, tone = "neutral", title }: {
  children: ReactNode; tone?: "neutral" | "accent" | "warn" | "block"; title?: string;
}) {
  const map = {
    neutral: "bg-surface-2 text-muted",
    accent: "bg-accent-dim/40 text-accent-hi",
    warn: "bg-warn/10 text-warn",
    block: "bg-block-bg text-block",
  }[tone];
  return (
    <span title={title}
          className={`inline-block rounded px-1.5 py-0.5 font-mono text-[10px] ${map}`}>
      {children}
    </span>
  );
}

/** A large selectable card. The select-me pattern appears all over the wizard. */
export function ChoiceCard({ selected, onClick, children, disabled, className = "" }: {
  selected: boolean; onClick: () => void; children: ReactNode;
  disabled?: boolean; className?: string;
}) {
  return (
    <button type="button" onClick={onClick} disabled={disabled} aria-pressed={selected}
            className={`rounded-md border px-4 py-3 text-left transition-colors
                        disabled:cursor-not-allowed disabled:opacity-50 ${
              selected ? "border-accent bg-accent-dim/30"
                       : "border-border hover:border-border-lit"} ${className}`}>
      {children}
    </button>
  );
}

export function SearchInput({ value, onChange, placeholder, busy, label }: {
  value: string; onChange: (v: string) => void;
  placeholder?: string; busy?: boolean; label: string;
}) {
  return (
    <div className="relative">
      <input value={value} onChange={(e) => onChange(e.target.value)}
             placeholder={placeholder} aria-label={label} type="search"
             className={`${inputCls} pr-20`} />
      <span className="absolute right-3 top-1/2 -translate-y-1/2 text-[11px] text-faint">
        {busy ? "searching…" : value ? "" : "⌕"}
      </span>
    </div>
  );
}

export function Banner({ tone, title, children }:
  { tone: "info" | "warn" | "block" | "review"; title: string; children?: ReactNode }) {
  const map = {
    info:   "border-accent/30 bg-accent-dim/25 text-ink-2",
    warn:   "border-warn/30 bg-warn-bg text-ink-2",
    block:  "border-block/30 bg-block-bg text-ink-2",
    review: "border-review/30 bg-review-bg text-ink-2",
  }[tone];
  const dot = { info: "bg-accent", warn: "bg-warn", block: "bg-block", review: "bg-review" }[tone];
  return (
    <div className={`rounded-lg border p-4 ${map}`}>
      <div className="mb-1 flex items-center gap-2">
        <span className={`h-2 w-2 rounded-full ${dot}`} aria-hidden />
        <span className="text-sm font-semibold text-ink">{title}</span>
      </div>
      {children && <div className="pl-4 text-sm leading-relaxed">{children}</div>}
    </div>
  );
}

/** Source citation with the page, hash and reviewer behind the rule. */
export function SourceChip({ source }: { source: SourceReference }) {
  const [open, setOpen] = useState(false);
  if (!source?.citation && !source?.reference) return null;
  return (
    <div className="mt-3">
      <button onClick={() => setOpen(!open)}
              className="inline-flex items-center gap-1.5 rounded border border-border-lit
                         bg-surface-2 px-2 py-1 font-mono text-[11px] text-muted
                         hover:border-accent/50 hover:text-accent-hi">
        <span aria-hidden>§</span>
        {source.reference ?? source.citation}
        {source.page ? ` · p.${source.page}` : ""}
        <span className="text-faint">{open ? "▲" : "▼"}</span>
      </button>
      {open && (
        <div className="mt-2 rounded-md border border-border bg-ground p-3">
          {source.provision_text && (
            <p className="mb-3 border-l-2 border-accent/40 pl-3 text-[13px] leading-relaxed text-ink-2">
              {source.provision_text}
            </p>
          )}
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 font-mono text-[11px] text-muted">
            {/* The uid is the exact anchor; the citation string alone can be
                ambiguous, so the link is only offered when a uid is present. */}
            {source.citation && (<><dt>Citation</dt><dd className="text-ink-2">
              {source.citation_uid
                ? <Link href={`/legal/provisions/${encodeURIComponent(source.citation_uid)}`}
                        className="text-accent-hi hover:underline">{source.citation}</Link>
                : source.citation}
            </dd></>)}
            {source.document && (<><dt>Document</dt><dd className="text-ink-2">{source.document}</dd></>)}
            {source.file_hash && (<><dt>SHA-256</dt><dd className="text-ink-2">{source.file_hash}…</dd></>)}
            {source.source_priority && (<><dt>Priority</dt><dd className="text-ink-2">{source.source_priority}</dd></>)}
            {source.effective_from && (<><dt>In force</dt>
              <dd className="text-ink-2">{source.effective_from} → {source.effective_to ?? "present"}</dd></>)}
            {source.reviewed_by && (<><dt>Reviewed</dt>
              <dd className="text-ink-2">{source.reviewed_by} · {source.reviewed_at?.slice(0, 10)}</dd></>)}
          </dl>
          {source.amended && (
            <p className="mt-2 text-[11px] text-warn">
              This provision carries amendment markers — its text has been substituted by a
              later amendment.
            </p>
          )}
        </div>
      )}
    </div>
  );
}

export function Stat({ label, value, sub, tone = "default" }:
  { label: string; value: ReactNode; sub?: ReactNode; tone?: "default" | "accent" | "muted" }) {
  const valueCls = { default: "text-ink", accent: "text-accent-hi", muted: "text-muted" }[tone];
  return (
    <div>
      <div className="text-[11px] font-medium uppercase tracking-[0.09em] text-muted">{label}</div>
      <div className={`tnum mt-1 text-2xl font-semibold ${valueCls}`}>{value}</div>
      {sub && <div className="mt-1 text-xs leading-relaxed text-faint">{sub}</div>}
    </div>
  );
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="rounded-lg border border-dashed border-border p-10 text-center">
      <p className="text-sm font-medium text-ink-2">{title}</p>
      {children && <div className="mx-auto mt-2 max-w-md text-sm text-muted">{children}</div>}
    </div>
  );
}
