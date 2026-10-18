"use client";
import { useEffect, useState } from "react";
import { useReveal } from "@/lib/useReveal";
import {
  api, inr, session, type AssessmentRow, type Company, type SourceGap,
} from "@/lib/api";
import {
  Badge, Banner, Button, Card, Delta, Empty, ListRow, PageHeader, RowMark,
  SectionTitle, Stat, StatusBadge,
} from "@/components/ui";

export default function DashboardPage() {
  const [companies, setCompanies] = useState<Company[] | null>(null);
  const [rows, setRows] = useState<AssessmentRow[] | null>(null);
  const [gaps, setGaps] = useState<SourceGap[]>([]);
  const [error, setError] = useState<string | null>(null);

  // Three calls that already exist; the dashboard composes them rather than
  // adding an endpoint whose only job would be to denormalise them.
  useEffect(() => {
    api.companies().then((r) => setCompanies(r.companies)).catch((e) => setError(e.message));
    api.assessments().then((r) => setRows(r.assessments)).catch(() => setRows([]));
    api.sourceGaps().then((r) => setGaps(r.gaps.filter((g) => !g.resolved_at))).catch(() => {});
  }, []);

  const name = session.user?.full_name?.split(" ")[0];
  const cos = companies ?? [];
  const all = rows ?? [];
  const needSetup = cos.filter((c) => c.face_value === null);
  const blocked = all.filter((r) => r.overall_result === "BLOCK");
  const recent = all.slice(0, 5);
  const blocker = gaps.find((g) => g.severity === "BLOCKER");

  const reveal = useReveal<HTMLDivElement>();

  return (
    <div ref={reveal} className="space-y-6">
      <PageHeader
        title={name ? `Welcome back, ${name}` : "Dashboard"}
        lead="Start an assessment, or pick up where you left off."
        actions={
          <>
            <Button variant="secondary" href="/calculator">Open calculator</Button>
            <Button href="/assess">New assessment</Button>
          </>
        }
      />

      {error && <Banner tone="block" title="Could not load your workspace">{error}</Banner>}

      <div className="reveal grid gap-4 sm:grid-cols-3">
        <Card className="p-5">
          <Stat label="Companies" value={cos.length}
                sub={needSetup.length > 0
                  ? `${needSetup.length} still need a capital structure`
                  : "all have a capital structure on file"} />
        </Card>
        <Card className="p-5">
          <Stat label="Assessments run" value={all.length}
                sub="Each one is immutable and pins the rules it used." />
        </Card>
        <Card className="p-5">
          <Stat label="Blocked outcomes" value={blocked.length}
                tone={blocked.length > 0 ? "accent" : "muted"}
                delta={blocked.length > 0 ? "needs attention" : "none outstanding"}
                deltaTone={blocked.length > 0 ? "down" : "up"} />
        </Card>
      </div>

      {blocker && (
        <Banner tone="warn" title={blocker.title}>
          <p>{blocker.detail}</p>
          {blocker.blocks_issue_types.length > 0 && (
            <p className="mt-2 text-ink-2">
              <span className="font-medium">Affects:</span>{" "}
              {blocker.blocks_issue_types.join(", ").toLowerCase().replace(/_/g, " ")} — these
              routes still produce every calculation, but their legal conclusions are returned
              as review-required.
            </p>
          )}
        </Banner>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="space-y-3">
          <SectionTitle hint={all.length > 5 ? `${all.length} in total` : undefined}>
            Recent assessments
          </SectionTitle>
          {rows === null ? <p className="text-sm text-muted">Loading…</p>
            : recent.length === 0 ? (
              <Empty title="No assessments yet">
                <p>Run one to see how a proposed issue stands against the rule set.</p>
                <Button className="mt-4" href="/assess">Start an assessment</Button>
              </Empty>
            ) : (
              <div className="space-y-2">
                {recent.map((r) => (
                  <ListRow
                    key={r.assessment_id}
                    href={`/assessments/${r.assessment_id}`}
                    lead={<RowMark>{(r.company_name || "?").slice(0, 2).toUpperCase()}</RowMark>}
                    title={r.company_name}
                    sub={`${r.issue_type.toLowerCase().replace(/_/g, " ")} · ${r.transaction_date}`}
                    trailing={<StatusBadge status={r.overall_result} />}
                  />
                ))}
                {all.length > recent.length && (
                  <Button variant="ghost" href="/assessments" className="w-full">
                    View all {all.length} assessments →
                  </Button>
                )}
              </div>
            )}
        </section>

        <section className="space-y-3">
          <SectionTitle hint={needSetup.length > 0 ? "action needed" : undefined}>
            {needSetup.length > 0 ? "Companies needing setup" : "Your companies"}
          </SectionTitle>
          {companies === null ? <p className="text-sm text-muted">Loading…</p>
            : cos.length === 0 ? (
              <Empty title="No companies yet">
                <p>Add a company to run its first assessment.</p>
                <Button className="mt-4" href="/companies/new">+ Add a company</Button>
              </Empty>
            ) : (
              <div className="space-y-2">
                {(needSetup.length > 0 ? needSetup : cos).slice(0, 5).map((c) => {
                  const authShares = c.authorised_capital && c.face_value
                    ? Math.floor(c.authorised_capital / c.face_value) : null;
                  const available = authShares && c.shares_issued != null
                    ? authShares - c.shares_issued : null;
                  return (
                    <ListRow
                      key={c.company_id}
                      href={`/companies/${c.company_id}`}
                      lead={<RowMark tone={c.face_value === null ? "review" : "accent"}>
                        {(c.name || "?").slice(0, 2).toUpperCase()}
                      </RowMark>}
                      title={c.name}
                      sub={c.cin ?? "CIN not recorded"}
                      value={c.face_value === null
                        ? <Badge tone="warn">setup incomplete</Badge>
                        : <span className="text-muted">{inr(available)} shares free</span>}
                    />
                  );
                })}
                <Button variant="ghost" href="/companies" className="w-full">
                  View all companies →
                </Button>
              </div>
            )}
        </section>
      </div>

      {gaps.length > 0 && (
        <section className="space-y-3">
          <SectionTitle hint={`${gaps.length} open`}>Known source gaps</SectionTitle>
          <div className="space-y-2">
            {gaps.map((g) => (
              <ListRow
                key={g.code}
                lead={<Delta tone={g.severity === "BLOCKER" ? "down" : "flat"}>{g.severity}</Delta>}
                title={g.title}
                sub={g.detail}
              />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
