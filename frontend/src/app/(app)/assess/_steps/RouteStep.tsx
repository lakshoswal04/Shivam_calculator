"use client";
import { useState } from "react";
import type { RouteCandidate, RouteInfo } from "@/lib/api";
import { Badge, Banner, Button, ChoiceCard, SectionTitle } from "@/components/ui";

function RouteTile({ route, selected, onSelect }: {
  route: RouteInfo; selected: boolean; onSelect: () => void;
}) {
  return (
    <ChoiceCard selected={selected} onClick={onSelect}>
      <div className="flex items-start justify-between gap-2">
        <span className="text-sm font-medium text-ink">{route.label}</span>
        {route.authored_rule_count === 0 && (
          <Badge tone="warn" title="No approved rule covers this route, so its legal conclusions are withheld.">
            no rules yet
          </Badge>
        )}
      </div>
      <div className="mt-1 text-[11px] text-faint">
        {route.authored_rule_count > 0
          ? `${route.authored_rule_count} approved rule${route.authored_rule_count === 1 ? "" : "s"}`
          : "Calculations only"}
      </div>
      {route.source_gate && (
        <div className="mt-1.5 text-[11px] text-warn">Primary law missing — legal conclusions withheld</div>
      )}
    </ChoiceCard>
  );
}

export function RouteStep({ routes, issueType, onSelect, guidance, onAskGuidance }: {
  routes: RouteInfo[];
  issueType: string;
  onSelect: (t: string) => void;
  guidance: RouteCandidate[] | null;
  onAskGuidance: () => void;
}) {
  const [showOthers, setShowOthers] = useState(false);
  // Routes whose facts are modelled lead. The rest stay reachable but are not
  // presented as equivalent: nine of the twelve have no authored law at all.
  const supported = routes.filter((r) => r.in_mvp);
  const others = routes.filter((r) => !r.in_mvp);

  return (
    <div className="space-y-4">
      <SectionTitle>What do you want to do?</SectionTitle>

      <div className="grid gap-3 sm:grid-cols-2">
        {supported.map((r) => (
          <RouteTile key={r.issue_type} route={r} selected={issueType === r.issue_type}
                     onSelect={() => onSelect(r.issue_type)} />
        ))}
        <button type="button" onClick={onAskGuidance}
                className="rounded-md border border-dashed border-border px-4 py-3 text-left
                           hover:border-accent/50">
          <div className="text-sm font-medium text-ink-2">Not sure</div>
          <div className="mt-1 text-[11px] text-faint">Explain which routes may apply</div>
        </button>
      </div>

      {others.length > 0 && (
        <div>
          <button type="button" onClick={() => setShowOthers(!showOthers)}
                  className="text-xs text-muted hover:text-accent-hi">
            {showOthers ? "▾" : "▸"} Other routes ({others.length})
          </button>
          {showOthers && (
            <div className="mt-3 space-y-3">
              <Banner tone="warn" title="No rules are authored for these routes yet">
                They will run every calculation, but their legal conclusions are withheld
                rather than guessed. Adding one is a matter of authoring its rules, not
                changing this page.
              </Banner>
              <div className="grid gap-3 sm:grid-cols-2">
                {others.map((r) => (
                  <RouteTile key={r.issue_type} route={r} selected={issueType === r.issue_type}
                             onSelect={() => onSelect(r.issue_type)} />
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {guidance && (
        <div className="space-y-2 rounded-md border border-border bg-ground p-4">
          <p className="text-sm text-ink-2">
            These routes may apply. This is guidance, not a decision.
          </p>
          {guidance.map((g) => (
            <div key={g.issue_type} className="flex items-start justify-between gap-4 border-t
                                               border-border pt-2 first:border-0 first:pt-0">
              <div>
                <div className="text-sm text-ink-2">{g.label}</div>
                <div className="text-[11px] leading-relaxed text-faint">{g.rationale}</div>
              </div>
              <Button variant="ghost" onClick={() => onSelect(g.issue_type)}>Choose</Button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
