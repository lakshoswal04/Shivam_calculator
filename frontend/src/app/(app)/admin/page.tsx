"use client";
import { useEffect, useState } from "react";
import { api, session, type ReviewItem } from "@/lib/api";
import { Banner, Button, Card, Empty, SectionTitle, Stat } from "@/components/ui";

export default function AdminPage() {
  const [items, setItems] = useState<ReviewItem[] | null>(null);
  const [stats, setStats] = useState<Record<string, Record<string, number>> | null>(null);
  const [checks, setChecks] = useState<{ checks: { check_name: string; failing_rows: number }[];
                                         all_clear: boolean } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = () => {
    api.reviewQueue().then((r) => setItems(r.items)).catch((e) => setError(e.message));
    api.stats().then(setStats).catch(() => {});
    // Quality checks are administrator-only; a reviewer would just get a 403.
    if (session.user?.role === "ADMINISTRATOR") {
      api.qualityChecks().then(setChecks).catch(() => {});
    }
  };
  useEffect(load, []);

  async function decide(id: string, decision: string) {
    setBusy(id);
    try { await api.reviewRule(id, decision); load(); }
    catch (e) { setError(e instanceof Error ? e.message : "Review failed"); }
    finally { setBusy(null); }
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Legal review</h1>
        <p className="mt-1 text-sm text-muted">
          A rule reaches production only when a named reviewer approves it. The database
          refuses an approved rule without a reviewer, so this cannot be bypassed.
        </p>
      </div>

      {error && <Banner tone="block" title="Error">{error}</Banner>}

      {stats && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Card className="p-5"><Stat label="Rules approved"
            value={`${stats.rules.approved} / ${stats.rules.total}`} /></Card>
          <Card className="p-5"><Stat label="Awaiting review"
            value={stats.rules.pending} tone={stats.rules.pending ? "accent" : "muted"} /></Card>
          <Card className="p-5"><Stat label="Demo approvals"
            value={stats.rules.demo_approved}
            sub="Not qualified legal sign-off" /></Card>
          <Card className="p-5"><Stat label="Provisions indexed"
            value={stats.provisions.total.toLocaleString("en-IN")}
            sub={`${stats.corpus.primary_law} primary-law sources`} /></Card>
        </div>
      )}

      {checks && !checks.all_clear && (
        <Banner tone="warn" title="Data quality checks are not clear">
          {checks.checks.filter((c) => c.failing_rows > 0)
            .map((c) => `${c.check_name}: ${c.failing_rows}`).join(" · ")}
        </Banner>
      )}

      <section>
        <SectionTitle hint={items ? `${items.length} pending` : ""}>Review queue</SectionTitle>
        {items === null ? <p className="text-sm text-muted">Loading…</p>
          : items.length === 0
          ? <Empty title="Nothing awaiting review">
              Every authored rule has a decision recorded against it.
            </Empty>
          : (
          <div className="space-y-3">
            {items.map((it) => (
              <Card key={it.rule_version_id} className="p-5">
                <div className="mb-3 flex flex-wrap items-center gap-2">
                  <span className="font-mono text-[11px] font-semibold text-accent-hi">
                    {it.rule_code}
                  </span>
                  <span className="text-sm font-medium text-ink">{it.title}</span>
                  <span className="ml-auto rounded border border-border-lit bg-surface-2
                                   px-2 py-0.5 font-mono text-[10px] text-muted">
                    {it.legal_review_status}
                  </span>
                </div>

                <div className="grid gap-4 lg:grid-cols-2">
                  <div>
                    <p className="mb-1 text-[11px] uppercase tracking-wider text-muted">
                      Drafted rule
                    </p>
                    <p className="text-[13px] leading-relaxed text-ink-2">{it.requirement}</p>
                    <ul className="mt-2 space-y-1">
                      {it.conditions.map((c, i) => (
                        <li key={i} className="font-mono text-[11px] text-muted">
                          <span className="text-faint">{c.condition_role.toLowerCase()}:</span>{" "}
                          {c.expr_text}
                        </li>
                      ))}
                    </ul>
                    <p className="mt-2 font-mono text-[11px] text-faint">
                      fail → {it.result_if_fail} · severity {it.severity} ·
                      in force from {it.effective_from}
                    </p>
                  </div>
                  <div>
                    <p className="mb-1 text-[11px] uppercase tracking-wider text-muted">
                      Source provision {it.page_from ? `· p.${it.page_from}` : ""}
                    </p>
                    <p className="max-h-40 overflow-y-auto border-l-2 border-accent/40 pl-3
                                  text-[13px] leading-relaxed text-ink-2">
                      {it.display_text || "(provision text unavailable)"}
                    </p>
                    <p className="mt-2 font-mono text-[11px] text-faint">
                      {it.citation} · {it.source_priority}
                    </p>
                  </div>
                </div>

                <div className="mt-4 flex gap-2 border-t border-border pt-4">
                  <Button onClick={() => decide(it.rule_version_id, "APPROVED")}
                          disabled={busy === it.rule_version_id}>Approve</Button>
                  <Button variant="ghost" onClick={() => decide(it.rule_version_id, "NEEDS_INFO")}
                          disabled={busy === it.rule_version_id}>Needs info</Button>
                  <Button variant="danger" onClick={() => decide(it.rule_version_id, "REJECTED")}
                          disabled={busy === it.rule_version_id}>Reject</Button>
                </div>
              </Card>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
