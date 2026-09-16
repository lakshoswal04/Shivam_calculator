"use client";
import type { RouteInfo } from "@/lib/api";
import { Banner, Field, Input, SectionTitle, Select } from "@/components/ui";

export function DetailsStep({ route, extra, onChange }: {
  route: RouteInfo | undefined;
  extra: Record<string, string | boolean>;
  onChange: (e: Record<string, string | boolean>) => void;
}) {
  const questions = route?.questions ?? [];
  const set = (k: string, v: string) => onChange({ ...extra, [k]: v });

  return (
    <div className="space-y-4">
      <SectionTitle hint={route?.label}>Route details</SectionTitle>
      {route?.source_gate && (
        <Banner tone="warn" title="Primary law for this route is not in the corpus">
          {route.source_gate.detail}
        </Banner>
      )}
      {questions.length === 0 ? (
        <p className="text-sm text-muted">No additional questions for this route.</p>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {questions.map((q) => (
            <Field key={q.key} label={q.label} required={q.required}>
              {q.type === "boolean" ? (
                <Select value={String(extra[q.key] ?? "")} onChange={(v) => set(q.key, v)}
                        options={[{ value: "true", label: "Yes" },
                                  { value: "false", label: "No" }]} />
              ) : q.type === "select" ? (
                <Select value={String(extra[q.key] ?? "")} onChange={(v) => set(q.key, v)}
                        options={(q.options ?? []).map((o) =>
                          ({ value: o, label: o.replace(/_/g, " ").toLowerCase() }))} />
              ) : (
                <Input type={q.type === "number" ? "number" : q.type === "date" ? "date" : "text"}
                       value={String(extra[q.key] ?? "")} onChange={(v) => set(q.key, v)} />
              )}
            </Field>
          ))}
        </div>
      )}
      <p className="text-xs leading-relaxed text-faint">
        Leaving a question unanswered is safe: the engine reports the rule as review-required
        and names the missing fact. It never assumes an answer.
      </p>
    </div>
  );
}
