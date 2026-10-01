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
    <span className={`inline-flex items-center gap-1.5 rounded-full border font-medium
      ${s.fg} ${s.bg} ${s.bd}
      ${size === "lg" ? "px-3.5 py-1.5 text-sm" : "px-2.5 py-0.5 text-[11px]"}`}>
      <span className="h-1.5 w-1.5 rounded-full bg-current" aria-hidden />
      {s.label}
    </span>
  );
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`rim rounded-[var(--radius-card)] border border-border bg-surface ${className}`}>
      {children}
    </div>
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
  variant?: "primary" | "secondary" | "ghost" | "danger"; disabled?: boolean; className?: string; href?: string;
}) {
  const base =
    "inline-flex items-center justify-center gap-2 rounded-full px-5 py-2 text-sm font-medium " +
    "transition-colors disabled:cursor-not-allowed disabled:opacity-50";
  // The reference's primary action is a white pill with near-black text, which
  // also keeps the accent free to mean "link" rather than "button".
  const styles = {
    primary: "bg-ink text-ground hover:bg-ink-2",
    secondary: "border border-border-lit bg-surface-2 text-ink-2 hover:border-accent/60 hover:text-ink",
    ghost: "border border-transparent bg-transparent text-muted hover:bg-surface-2 hover:text-ink-2",
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
  "w-full rounded-xl border border-border bg-surface-2 px-3.5 py-2.5 text-sm text-ink " +
  "placeholder:text-faint focus:border-accent focus:outline-none transition-colors";

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
    accent: "bg-accent-dim/60 text-accent-hi",
    warn: "bg-warn/10 text-warn",
    block: "bg-block-bg text-block",
  }[tone];
  return (
    <span title={title}
          className={`inline-block rounded-full px-2 py-0.5 font-mono text-[10px] ${map}`}>
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
            className={`rounded-2xl border px-4 py-3.5 text-left transition-colors
                        disabled:cursor-not-allowed disabled:opacity-50 ${
              selected ? "border-accent bg-accent-dim/40 ring-1 ring-accent/40"
                       : "border-border bg-surface-2/40 hover:border-border-lit"} ${className}`}>
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
    <div className={`rim rounded-[var(--radius-card)] border p-4 ${map}`}>
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
              className="inline-flex items-center gap-1.5 rounded-full border border-border-lit
                         bg-surface-2 px-2.5 py-1 font-mono text-[11px] text-muted
                         hover:border-accent/50 hover:text-accent-hi">
        <span aria-hidden>§</span>
        {source.reference ?? source.citation}
        {source.page ? ` · p.${source.page}` : ""}
        <span className="text-faint">{open ? "▲" : "▼"}</span>
      </button>
      {open && (
        <div className="mt-2 rounded-2xl border border-border bg-ground p-3.5">
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

/** The reference's small +/- pill: lime when things went up, coral when down. */
export function Delta({ children, tone }: {
  children: ReactNode; tone: "up" | "down" | "flat" | "review";
}) {
  const map = {
    up: "bg-pass/15 text-pass",
    down: "bg-block/15 text-block",
    review: "bg-review/15 text-review",
    flat: "bg-surface-2 text-muted",
  }[tone];
  return (
    <span className={`tnum inline-block rounded-full px-2 py-0.5 text-[11px] font-medium ${map}`}>
      {children}
    </span>
  );
}

export function Stat({ label, value, sub, tone = "default", unit, delta, deltaTone = "flat" }:
  { label: string; value: ReactNode; sub?: ReactNode; tone?: "default" | "accent" | "muted";
    /** Superscript unit beside the figure, as the reference sets its currency mark. */
    unit?: string; delta?: ReactNode; deltaTone?: "up" | "down" | "flat" }) {
  const valueCls = { default: "text-ink", accent: "text-accent-hi", muted: "text-muted" }[tone];
  return (
    <div>
      <div className="text-[11px] font-medium uppercase tracking-[0.09em] text-muted">{label}</div>
      <div className="mt-1.5 flex flex-wrap items-center gap-x-2.5 gap-y-1">
        <span className={`tnum text-[26px] font-semibold leading-none tracking-tight ${valueCls}`}>
          {value}
          {unit && <sup className="ml-0.5 text-[13px] font-medium text-muted">{unit}</sup>}
        </span>
        {delta != null && <Delta tone={deltaTone}>{delta}</Delta>}
      </div>
      {sub && <div className="mt-1.5 text-xs leading-relaxed text-faint">{sub}</div>}
    </div>
  );
}

/** The signature gradient card carrying a page's headline figure.
 *
 * `tone="alert"` swaps to the coral gradient so a figure that has gone wrong is
 * not delivered on a reassuring green card. */
export function HeroCard({ label, value, unit, sub, actions, tone = "default" }: {
  label: string; value: ReactNode; unit?: string; sub?: ReactNode;
  actions?: ReactNode; tone?: "default" | "alert";
}) {
  return (
    <div className={`relative overflow-hidden rounded-[var(--radius-card)] p-6
                     ${tone === "alert" ? "bg-alert" : "bg-hero"}`}>
      {/* The soft diagonal sheen the reference folds across its hero card. */}
      <div aria-hidden className="pointer-events-none absolute -right-16 -top-10 h-72 w-72
                                  rotate-12 rounded-[40%] bg-white/10" />
      <div className="relative">
        <p className="text-[15px] font-medium text-black/70">{label}</p>
        <p className="tnum mt-3 text-[40px] font-bold leading-none tracking-tight text-black
                      sm:text-[52px]">
          {value}
          {unit && <sup className="ml-1 text-[18px] font-semibold text-black/60">{unit}</sup>}
        </p>
        {sub && <p className="mt-3 text-[13px] leading-relaxed text-black/70">{sub}</p>}
        {actions && <div className="mt-6 flex flex-wrap items-center gap-2.5">{actions}</div>}
      </div>
    </div>
  );
}

/** A button sized for the hero card, where the surface is light. */
export function HeroButton({ children, href, onClick, variant = "dark" }: {
  children: ReactNode; href?: string; onClick?: () => void; variant?: "dark" | "light";
}) {
  const cls = `inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-sm font-medium
    transition-colors ${variant === "dark"
      ? "bg-black text-white hover:bg-black/80"
      : "bg-white text-black hover:bg-white/85"}`;
  return href
    ? <Link href={href} className={cls}>{children}</Link>
    : <button type="button" onClick={onClick} className={cls}>{children}</button>;
}

export interface Segment { label: string; value: number; color: string }

/** Donut built from stroke-dasharray on one circle per segment.
 *
 * Inline SVG rather than a charting dependency: there is exactly one chart
 * shape in this design, and it reads its colours from the theme tokens. */
export function Donut({ segments, total, caption, size = 190 }: {
  segments: Segment[]; total: ReactNode; caption?: string; size?: number;
}) {
  const sum = segments.reduce((n, s) => n + s.value, 0);
  const r = 70;
  const circ = 2 * Math.PI * r;
  let offset = 0;
  return (
    <div className="flex flex-wrap items-center gap-6">
      <svg width={size} height={size} viewBox="0 0 180 180" role="img"
           aria-label={caption ?? "Proportional breakdown"}>
        <circle cx="90" cy="90" r={r} fill="none"
                stroke="var(--color-surface-2)" strokeWidth="22" />
        {sum > 0 && segments.map((s) => {
          const len = (s.value / sum) * circ;
          // 2px of the gap is eaten by the round cap at each end.
          const dash = `${Math.max(0, len - 4)} ${circ - Math.max(0, len - 4)}`;
          const el = (
            <circle key={s.label} cx="90" cy="90" r={r} fill="none"
                    stroke={s.color} strokeWidth="22" strokeLinecap="round"
                    strokeDasharray={dash} strokeDashoffset={-offset}
                    transform="rotate(-90 90 90)" />
          );
          offset += len;
          return el;
        })}
        <text x="90" y="84" textAnchor="middle"
              className="fill-[var(--color-muted)] text-[11px]">Total</text>
        <text x="90" y="106" textAnchor="middle"
              className="tnum fill-[var(--color-ink)] text-[19px] font-semibold">{total}</text>
      </svg>
      <ul className="grid min-w-[180px] flex-1 grid-cols-2 gap-x-6 gap-y-3">
        {segments.map((s) => (
          <li key={s.label}>
            <div className="text-[11px] leading-tight text-muted">{s.label}</div>
            <div className="mt-1 flex items-center gap-1.5">
              <span className="h-3.5 w-1 rounded-full" style={{ background: s.color }} aria-hidden />
              <span className="tnum text-[15px] font-semibold text-ink">
                {sum > 0 ? Math.round((s.value / sum) * 100) : 0}%
              </span>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Rounded-top bars with the last — or a named — bar highlighted. */
export function MiniBars({ bars, highlight }: {
  bars: Array<{ label: string; value: number; caption?: string }>; highlight?: string;
}) {
  const max = Math.max(1, ...bars.map((b) => Math.abs(b.value)));
  const hi = highlight ?? bars[bars.length - 1]?.label;
  return (
    <div className="flex items-end gap-2.5" style={{ height: 180 }}>
      {bars.map((b) => {
        const on = b.label === hi;
        return (
          <div key={b.label} className="flex flex-1 flex-col items-center gap-2">
            <div className="flex w-full flex-1 items-end">
              <div
                className={`w-full rounded-t-xl transition-colors ${
                  on ? "bg-review" : "bg-review/25"}`}
                style={{ height: `${Math.max(6, (Math.abs(b.value) / max) * 100)}%` }}
                title={`${b.label}: ${b.caption ?? b.value}`}
              />
            </div>
            {b.caption && (
              <span className="tnum text-[10px] text-muted">{b.caption}</span>
            )}
            <span className="text-[11px] text-faint">{b.label}</span>
          </div>
        );
      })}
    </div>
  );
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="rounded-[var(--radius-card)] border border-dashed border-border p-10 text-center">
      <p className="text-sm font-medium text-ink-2">{title}</p>
      {children && <div className="mx-auto mt-2 max-w-md text-sm text-muted">{children}</div>}
    </div>
  );
}
