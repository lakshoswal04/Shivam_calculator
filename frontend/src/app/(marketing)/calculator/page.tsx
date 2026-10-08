"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { inr, rupees } from "@/lib/api";
import {
  Badge, Banner, Button, Card, Delta, Donut, Field, HeroButton, HeroCard,
  Input, inputCls, MiniBars, SectionTitle, StackedBar, Stat, ThresholdFlag,
} from "@/components/ui";

type Detail = "summary" | "detailed";
const DETAIL_KEY = "calc.detail";

export default function CalculatorPage() {
  // State inputs
  // The calculator opens empty: these are the user's own figures, not a
  // worked example dressed up as data. Face value is the one exception —
  // ₹10 is the overwhelming default for Indian equity and every other field
  // derives from it, so leaving it blank makes the form look broken. The
  // example buttons remain, as a deliberate opt-in.
  const [faceValueStr, setFaceValueStr] = useState("10");
  const [authCapitalStr, setAuthCapitalStr] = useState("");
  const [authSharesStr, setAuthSharesStr] = useState("");
  const [issuedCapitalStr, setIssuedCapitalStr] = useState("");
  const [issuedSharesStr, setIssuedSharesStr] = useState("");
  const [proposedSharesStr, setProposedSharesStr] = useState("");
  const [issuePriceStr, setIssuePriceStr] = useState("");

  // Investment side. Promoter holding is left blank rather than defaulting to
  // zero: a silent zero would report promoters diluted from 0%, which looks
  // like a bug rather than like missing input.
  const [promoterSharesStr, setPromoterSharesStr] = useState("");
  const [investorLabel, setInvestorLabel] = useState("New investor");

  // Summary by default: most visitors want one number. The preference is
  // remembered per browser, and every access is guarded because a private
  // window or blocked site data makes the accessor itself throw.
  const [detail, setDetail] = useState<Detail>("summary");
  useEffect(() => {
    try {
      const saved = localStorage.getItem(DETAIL_KEY);
      if (saved === "summary" || saved === "detailed") setDetail(saved);
    } catch { /* storage unavailable; the default stands */ }
  }, []);
  useEffect(() => {
    try { localStorage.setItem(DETAIL_KEY, detail); } catch { /* not essential */ }
  }, [detail]);

  // Track active input mode for authorised & issued (capital vs shares)
  const [lastAuthEdit, setLastAuthEdit] = useState<"capital" | "shares">("capital");
  const [lastIssuedEdit, setLastIssuedEdit] = useState<"capital" | "shares">("capital");

  const faceValue = Number(faceValueStr) || 0;

  // Derived input numbers with proper bi-directional sync
  const authCapital = useMemo(() => {
    if (lastAuthEdit === "shares" && faceValue > 0) {
      return (Number(authSharesStr) || 0) * faceValue;
    }
    return Number(authCapitalStr) || 0;
  }, [authCapitalStr, authSharesStr, faceValue, lastAuthEdit]);

  const authShares = useMemo(() => {
    if (lastAuthEdit === "capital" && faceValue > 0) {
      return Math.floor((Number(authCapitalStr) || 0) / faceValue);
    }
    return Number(authSharesStr) || 0;
  }, [authCapitalStr, authSharesStr, faceValue, lastAuthEdit]);

  const issuedCapital = useMemo(() => {
    if (lastIssuedEdit === "shares" && faceValue > 0) {
      return (Number(issuedSharesStr) || 0) * faceValue;
    }
    return Number(issuedCapitalStr) || 0;
  }, [issuedCapitalStr, issuedSharesStr, faceValue, lastIssuedEdit]);

  const issuedShares = useMemo(() => {
    if (lastIssuedEdit === "capital" && faceValue > 0) {
      return Math.floor((Number(issuedCapitalStr) || 0) / faceValue);
    }
    return Number(issuedSharesStr) || 0;
  }, [issuedCapitalStr, issuedSharesStr, faceValue, lastIssuedEdit]);

  const proposedShares = Number(proposedSharesStr) || 0;
  const issuePrice = Number(issuePriceStr) || 0;

  // Calculations (strictly unit-safe)
  const availableShares = Math.max(0, authShares - issuedShares);
  const availableNominalCapital = availableShares * faceValue;
  const potentialConsideration = issuePrice > 0 ? availableShares * issuePrice : 0;

  const nominalIncrease = proposedShares * faceValue;
  const premiumPerShare = issuePrice > faceValue ? issuePrice - faceValue : 0;
  const totalPremium = proposedShares * premiumPerShare;
  const totalConsideration = proposedShares * issuePrice;

  const postIssueShares = issuedShares + proposedShares;
  const remainingAuthorisedShares = authShares - postIssueShares;
  const remainingNominalCapital = remainingAuthorisedShares * faceValue;

  // ------------------------------------------------------------ investment
  // Pure arithmetic, mirroring the shape of compute_dilution() in
  // backend/app/domain/calc_engine.py without calling it — this page runs with
  // no account and therefore no API.
  const promoterShares = Math.max(0, Number(promoterSharesStr) || 0);
  const hasPromoterInput = promoterSharesStr.trim() !== "" && promoterShares > 0;

  // Every ratio below guards its denominator: an empty field makes issuedShares
  // zero, and 0/0 would render as NaN across the whole panel.
  const pct = (part: number, whole: number) => (whole > 0 ? (part / whole) * 100 : 0);

  const otherPreShares = Math.max(0, issuedShares - promoterShares);
  const promoterPctPre = pct(promoterShares, issuedShares);
  const otherPctPre = pct(otherPreShares, issuedShares);

  // The new shares are assumed to go wholly to the incoming investor, which is
  // what "investment side" means here; a rights issue would differ and is
  // handled by an assessment, not by this page.
  const promoterPctPost = pct(promoterShares, postIssueShares);
  const otherPctPost = pct(otherPreShares, postIssueShares);
  const investorPctPost = pct(proposedShares, postIssueShares);

  const preMoney = issuedShares * issuePrice;
  const postMoney = postIssueShares * issuePrice;
  const dilutionPct = pct(proposedShares, postIssueShares);
  const priceToFace = faceValue > 0 ? issuePrice / faceValue : 0;

  // A threshold is reported only when the issue actually moves promoter holding
  // across it. Each names its provision and stops there.
  const THRESHOLDS = [
    { at: 75, title: "75% — special resolution majority",
      detail: "Companies Act, 2013, s.114(2). A special resolution needs votes in favour of at least three times the votes against." },
    { at: 50, title: "50% — simple majority",
      detail: "Ordinary resolutions carry on a simple majority of votes cast." },
    { at: 25, title: "25% — SAST open-offer trigger",
      detail: "SEBI (SAST) Regulations, 2011, reg. 3(1). Acquiring 25% or more of the voting rights of a listed company triggers an open offer." },
  ];
  const crossings = hasPromoterInput && proposedShares > 0
    ? THRESHOLDS.filter((t) => promoterPctPre >= t.at && promoterPctPost < t.at)
    : [];

  const isExceeded = proposedShares > availableShares;
  const excessShares = isExceeded ? proposedShares - availableShares : 0;
  const excessNominalCapital = excessShares * faceValue;
  const isDiscount = issuePrice > 0 && faceValue > 0 && issuePrice < faceValue;

  // Handlers for face value presets and example loading
  function applyFaceValue(fv: number) {
    setFaceValueStr(String(fv));
    if (lastAuthEdit === "capital") {
      setAuthSharesStr(String(Math.floor(authCapital / fv)));
    } else {
      setAuthCapitalStr(String(authShares * fv));
    }
    if (lastIssuedEdit === "capital") {
      setIssuedSharesStr(String(Math.floor(issuedCapital / fv)));
    } else {
      setIssuedCapitalStr(String(issuedShares * fv));
    }
  }

  function handleAuthCapitalChange(val: string) {
    setLastAuthEdit("capital");
    setAuthCapitalStr(val);
    const num = Number(val) || 0;
    if (faceValue > 0) {
      setAuthSharesStr(String(Math.floor(num / faceValue)));
    }
  }

  function handleAuthSharesChange(val: string) {
    setLastAuthEdit("shares");
    setAuthSharesStr(val);
    const num = Number(val) || 0;
    if (faceValue > 0) {
      setAuthCapitalStr(String(num * faceValue));
    }
  }

  function handleIssuedCapitalChange(val: string) {
    setLastIssuedEdit("capital");
    setIssuedCapitalStr(val);
    const num = Number(val) || 0;
    if (faceValue > 0) {
      setIssuedSharesStr(String(Math.floor(num / faceValue)));
    }
  }

  function handleIssuedSharesChange(val: string) {
    setLastIssuedEdit("shares");
    setIssuedSharesStr(val);
    const num = Number(val) || 0;
    if (faceValue > 0) {
      setIssuedCapitalStr(String(num * faceValue));
    }
  }

  // --------------------------------------------------------------- solvers
  // Each solves for a share count and writes it back into the inputs, so the
  // whole page recomputes around the answer rather than showing it in isolation.
  type SolveMode = "raise" | "stake" | "floor";

  function solve(mode: SolveMode, target: number):
      { shares: number } | { error: string } {
    if (!Number.isFinite(target) || target <= 0) {
      return { error: "Enter a target above zero." };
    }
    if (mode === "raise") {
      if (issuePrice <= 0) return { error: "Set an issue price first." };
      return { shares: Math.ceil(target / issuePrice) };
    }
    if (mode === "stake") {
      if (target >= 100) return { error: "A new investor cannot take 100% of the company." };
      if (issuedShares <= 0) return { error: "Set the issued shares first." };
      const y = target / 100;
      return { shares: Math.round((y * issuedShares) / (1 - y)) };
    }
    // floor: promoter / (issued + N) >= z
    if (!hasPromoterInput) return { error: "Enter the promoter holding first." };
    if (target > 100) return { error: "A holding cannot exceed 100%." };
    const n = promoterShares / (target / 100) - issuedShares;
    if (n < 0) {
      // Clamping to zero here would say "issue nothing and you are fine", which
      // is false — the floor is already breached before any new issue.
      return { error: `Promoters already hold ${promoterPctPre.toFixed(2)}%, below ${target}%. No issue preserves that floor.` };
    }
    return { shares: Math.floor(n) };
  }

  function loadStandardExample() {
    setFaceValueStr("10");
    setAuthCapitalStr("5000000");
    setAuthSharesStr("500000");
    setIssuedCapitalStr("2000000");
    setIssuedSharesStr("200000");
    setProposedSharesStr("100000");
    setIssuePriceStr("125");
    setLastAuthEdit("capital");
    setLastIssuedEdit("capital");
  }

  function loadExceedsExample() {
    setFaceValueStr("10");
    setAuthCapitalStr("5000000");
    setAuthSharesStr("500000");
    setIssuedCapitalStr("2000000");
    setIssuedSharesStr("200000");
    setProposedSharesStr("400000");
    setIssuePriceStr("125");
    setLastAuthEdit("capital");
    setLastIssuedEdit("capital");
  }

  // Post-issue authorised capital splits three ways. Shown as proportions of
  // the authorised total, which is what "capacity" is measured against.
  const stack = [
    { label: "Already issued", value: issuedShares, color: "var(--color-review)" },
    { label: "Proposed", value: Math.min(proposedShares, Math.max(0, authShares - issuedShares)),
      color: "var(--color-accent)" },
    { label: "Unused headroom", value: Math.max(0, remainingAuthorisedShares),
      color: "var(--color-surface-2)" },
  ];

  return (
    <div className="mx-auto max-w-[1180px] px-5 py-10 sm:px-7">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h1 className="text-[32px] font-semibold leading-tight tracking-tight sm:text-[38px]">
            Capital calculator
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted">
            Maximum additional share capacity, nominal capital, securities premium and the
            post-issue position. Arithmetic only — legal issue capacity is a separate question,
            answered by an assessment.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="secondary" onClick={loadStandardExample} className="text-xs">
            Standard example
          </Button>
          <Button variant="secondary" onClick={loadExceedsExample} className="text-xs">
            Exceeds-capacity example
          </Button>
        </div>
      </div>

      {/* Inputs on the left, the answer on the right. The results column is
          sticky so the figure stays in view while the inputs are edited. */}
      {/* Two explicit column wrappers, not three auto-placed children: with the
          solver pinned to column 1 as a sibling, grid auto-placement put the
          results in row 2 and left the top-right cell empty, so the answer only
          appeared after scrolling. */}
      <div className="mt-8 grid items-start gap-6 lg:grid-cols-[minmax(0,400px)_1fr]">

        {/* --------------------------------------------------- left column */}
        <div className="space-y-6">
        {/* ------------------------------------------------------- inputs */}
        <Card className="p-6">
          <SectionTitle hint="every figure derives live">Your inputs</SectionTitle>

          <div className="mt-4 space-y-2">
            <label className="text-[11px] font-semibold uppercase tracking-[0.09em] text-muted">
              Face value per share (₹)
            </label>
            <div className="flex flex-wrap items-center gap-2">
              <div className="w-28">
                <Input type="number" step="0.01" min="0.01" value={faceValueStr}
                       onChange={(v) => applyFaceValue(Number(v))} />
              </div>
              <div className="flex flex-wrap items-center gap-1.5">
                {[1, 2, 5, 10, 100].map((preset) => (
                  <button key={preset} type="button" onClick={() => applyFaceValue(preset)}
                          aria-pressed={faceValue === preset}
                          className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                            faceValue === preset
                              ? "bg-accent text-white"
                              : "border border-border bg-surface text-ink-2 hover:border-accent/50"}`}>
                    ₹{preset}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="mt-6 space-y-4">
            <div className="space-y-3 rounded-xl border border-border bg-surface-2/60 p-4">
              <div className="text-[11px] font-semibold uppercase tracking-[0.09em] text-accent">
                1 · Authorised capital
              </div>
              <Field label="Authorised share capital (₹)">
                <Input type="number" step="1" value={authCapitalStr}
                       onChange={handleAuthCapitalChange} placeholder="e.g. 50,00,000" />
              </Field>
              <Field label="Total authorised shares">
                <Input type="number" step="1" value={authSharesStr}
                       onChange={handleAuthSharesChange} placeholder="e.g. 5,00,000" />
              </Field>
              <div className="text-[11px] leading-relaxed text-faint">
                {faceValue > 0
                  ? `${rupees(authCapital)} ÷ ₹${faceValue} = ${inr(authShares)} authorised shares`
                  : "Enter a face value to derive shares"}
              </div>
            </div>

            <div className="space-y-3 rounded-xl border border-border bg-surface-2/60 p-4">
              <div className="text-[11px] font-semibold uppercase tracking-[0.09em] text-accent">
                2 · Existing issued capital
              </div>
              <Field label="Existing issued share capital (₹)">
                <Input type="number" step="1" value={issuedCapitalStr}
                       onChange={handleIssuedCapitalChange} placeholder="e.g. 20,00,000" />
              </Field>
              <Field label="Already issued shares">
                <Input type="number" step="1" value={issuedSharesStr}
                       onChange={handleIssuedSharesChange} placeholder="e.g. 2,00,000" />
              </Field>
              <div className="text-[11px] leading-relaxed text-faint">
                {faceValue > 0
                  ? `${rupees(issuedCapital)} ÷ ₹${faceValue} = ${inr(issuedShares)} shares already issued`
                  : "Enter a face value to derive shares"}
              </div>
            </div>

            <div className="space-y-3 rounded-xl border border-border bg-surface-2/60 p-4">
              <div className="text-[11px] font-semibold uppercase tracking-[0.09em] text-accent">
                3 · Proposed new issue
              </div>
              <Field label="New shares to issue" required>
                <Input type="number" step="1" min="0" value={proposedSharesStr}
                       onChange={setProposedSharesStr} placeholder="e.g. 1,00,000" />
              </Field>
              <Field label="Issue price per share (₹)" required>
                <Input type="number" step="0.01" min="0" value={issuePriceStr}
                       onChange={setIssuePriceStr} placeholder="e.g. 125" />
              </Field>
            </div>

            <div className="space-y-3 rounded-xl border border-border bg-surface-2/60 p-4">
              <div className="text-[11px] font-semibold uppercase tracking-[0.09em] text-accent">
                4 · Investment &amp; ownership
              </div>
              <Field label="Promoter / existing holder shares"
                     hint="Used for dilution and the control thresholds. Leave blank to skip.">
                <Input type="number" step="1" min="0" value={promoterSharesStr}
                       onChange={setPromoterSharesStr} placeholder="e.g. 1,20,000" />
              </Field>
              <Field label="Incoming investor">
                <Input value={investorLabel} onChange={setInvestorLabel}
                       placeholder="New investor" />
              </Field>
            </div>
          </div>
        </Card>

        <SolverCard solve={solve} onApply={(n) => setProposedSharesStr(String(n))} />
        </div>

        {/* -------------------------------------------------- right column */}
        <div className="space-y-4 lg:sticky lg:top-24">
          <div className="flex items-center justify-between gap-3">
            <SectionTitle>Result</SectionTitle>
            {/* Two depths, because "how much can I issue" and "show me the
                whole position" are different questions from different people. */}
            <div className="flex items-center gap-1 rounded-lg bg-surface-2 p-1">
              {([["summary", "Summary"], ["detailed", "Detailed"]] as const).map(([id, label]) => (
                <button key={id} type="button" onClick={() => setDetail(id)}
                        aria-pressed={detail === id}
                        className={`rounded-md px-3.5 py-1.5 text-[12px] transition-colors ${
                          detail === id ? "bg-surface font-medium text-accent shadow-sm"
                                        : "text-muted hover:text-ink-2"}`}>
                  {label}
                </button>
              ))}
            </div>
          </div>

          <HeroCard
            tone={isExceeded ? "alert" : "default"}
            label={isExceeded ? "Capacity exceeded" : "Available additional shares"}
            value={isExceeded ? `−${inr(excessShares)}` : inr(availableShares)}
            unit="shares"
            sub={isExceeded
              ? `The proposed ${inr(proposedShares)} shares exceed available capacity of ${inr(availableShares)} by ${inr(excessShares)} — a nominal shortfall of ${rupees(excessNominalCapital)}.`
              : `${rupees(availableNominalCapital)} of nominal capital remains unused within the authorised capital, at a face value of ₹${faceValue}.`}
            actions={<HeroButton href="/signup">Check the legal position →</HeroButton>}
          />

          <div className="grid gap-4 sm:grid-cols-3">
            <Card className="p-5">
              <Stat label="Total raised" value={rupees(totalConsideration)}
                    delta={totalPremium > 0 ? "incl. premium" : "at par"}
                    deltaTone={totalPremium > 0 ? "up" : "flat"} />
            </Card>
            <Card className="p-5">
              <Stat label="Nominal increase" value={rupees(nominalIncrease)} />
            </Card>
            <Card className="p-5">
              <Stat label="Shares remaining"
                    value={isExceeded ? `−${inr(excessShares)}` : inr(remainingAuthorisedShares)}
                    tone={isExceeded ? "muted" : "default"}
                    delta={isExceeded ? "deficit" : "within authorised"}
                    deltaTone={isExceeded ? "down" : "up"} />
            </Card>
          </div>

          {/* Statutory warnings show at BOTH levels. They are not detail —
              they are the reason the figure above might be unusable. */}
          {isDiscount && (
            <Banner tone="warn" title="Prohibition on issue of shares at a discount">
              Under section 53 of the Companies Act, 2013, a share issued below its face value
              of ₹{faceValue} is void, except for sweat equity shares issued under section 54.
            </Banner>
          )}
          {isExceeded && (
            <Banner tone="warn" title="Increasing authorised capital">
              This does not mean the transaction is impossible. Additional authorised capital
              may be required before allotment, subject to shareholder approval by special
              resolution and filing Form SH-7 with the Registrar of Companies.
            </Banner>
          )}

          {/* ------------------------------------------------- ownership */}
          <Card className="p-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <SectionTitle>Ownership after the issue</SectionTitle>
              <Badge tone="accent">{dilutionPct.toFixed(2)}% diluted</Badge>
            </div>

            {!hasPromoterInput ? (
              <p className="text-[13px] leading-relaxed text-muted">
                Enter the promoter or existing-holder shares on the left to see how this issue
                changes who owns what, and which control thresholds it crosses.
              </p>
            ) : (
              <>
                <StackedBar
                  caption="Shareholding immediately after the proposed issue"
                  ticks={[25, 50, 75]}
                  segments={[
                    { label: "Promoters", value: promoterShares, color: "var(--color-accent)" },
                    { label: "Other existing", value: otherPreShares, color: "var(--color-review)" },
                    { label: investorLabel || "New investor", value: proposedShares,
                      color: "var(--color-pass)" },
                  ]}
                />

                <dl className="mt-6 divide-y divide-border">
                  {([
                    ["Promoters", promoterPctPre, promoterPctPost],
                    ["Other existing holders", otherPctPre, otherPctPost],
                    [investorLabel || "New investor", 0, investorPctPost],
                  ] as const).map(([label, pre, post]) => (
                    <div key={label}
                         className="flex items-baseline justify-between gap-4 py-2.5 text-sm">
                      <dt className="text-muted">{label}</dt>
                      <dd className="tnum flex items-baseline gap-2">
                        <span className="text-faint">{pre.toFixed(2)}%</span>
                        <span className="text-faint" aria-hidden>→</span>
                        <span className="font-semibold text-ink">{post.toFixed(2)}%</span>
                        <Delta tone={post - pre < -0.005 ? "down" : post - pre > 0.005 ? "up" : "flat"}>
                          {post - pre >= 0 ? "+" : ""}{(post - pre).toFixed(2)} pp
                        </Delta>
                      </dd>
                    </div>
                  ))}
                </dl>

                {crossings.length > 0 && (
                  <div className="mt-5 space-y-2">
                    {crossings.map((t) => (
                      <ThresholdFlag key={t.at}
                                     title={`This issue takes promoters below ${t.at}%`}
                                     detail={<>
                                       {t.detail}{" "}
                                       Whether that matters here is a legal question —{" "}
                                       <Link href="/signup" className="text-accent hover:underline">
                                         run an assessment
                                       </Link>.
                                     </>} />
                    ))}
                  </div>
                )}
              </>
            )}
          </Card>

          {/* ------------------------------------------------- valuation */}
          <Card className="p-6">
            <SectionTitle hint="implied by the issue price">Valuation</SectionTitle>
            <div className="grid gap-4 sm:grid-cols-3">
              <Stat label="Pre-money" value={rupees(preMoney)}
                    sub={`${inr(issuedShares)} shares × ₹${issuePrice}`} />
              <Stat label="Post-money" value={rupees(postMoney)}
                    sub={`${inr(postIssueShares)} shares × ₹${issuePrice}`} />
              <Stat label="Price to face value"
                    value={priceToFace > 0 ? `${priceToFace.toFixed(2)}×` : "—"}
                    sub={`₹${issuePrice} against ₹${faceValue} face value`} />
            </div>
            <p className="mt-4 text-[11px] leading-relaxed text-faint">
              Implied values only. The issue price is an input here; whether it satisfies a
              statutory pricing floor is determined by an assessment.
            </p>
          </Card>

          {detail === "detailed" && (
            <>
              <div className="grid gap-4 md:grid-cols-2">
                <Card className="p-6">
                  <div className="flex items-center justify-between gap-3">
                    <SectionTitle>Authorised capital, post-issue</SectionTitle>
                    <Badge tone={isExceeded ? "block" : "accent"}>
                      {isExceeded ? "exceeds" : "within"}
                    </Badge>
                  </div>
                  <Donut segments={stack} total={inr(authShares)}
                         caption="How the authorised shares are accounted for after the proposed issue" />
                </Card>

                <Card className="p-6">
                  <SectionTitle hint="shares">Capital ladder</SectionTitle>
                  <MiniBars
                    highlight="Proposed"
                    bars={[
                      { label: "Authorised", value: authShares, caption: inr(authShares) },
                      { label: "Issued", value: issuedShares, caption: inr(issuedShares) },
                      { label: "Proposed", value: proposedShares, caption: inr(proposedShares) },
                      { label: "Remaining", value: Math.max(0, remainingAuthorisedShares),
                        caption: isExceeded ? `−${inr(excessShares)}` : inr(remainingAuthorisedShares) },
                    ]}
                  />
                </Card>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <Card className="p-6">
                  <div className="flex items-center justify-between gap-3 border-b border-border pb-3">
                    <h3 className="text-[13px] font-semibold uppercase tracking-[0.09em] text-muted">
                      Current capital position
                    </h3>
                    <Badge tone="accent">Cap engine §15</Badge>
                  </div>
                  <dl className="mt-2 divide-y divide-border">
                    {([
                      ["Authorised capital", rupees(authCapital)],
                      ["Face value per share", `₹${faceValue}`],
                      ["Total authorised shares", `${inr(authShares)} shares`],
                      ["Already issued shares", `${inr(issuedShares)} shares`],
                    ] as const).map(([k, v]) => (
                      <div key={k} className="flex items-baseline justify-between gap-4 py-2.5 text-sm">
                        <dt className="text-muted">{k}</dt>
                        <dd className="tnum font-medium text-ink">{v}</dd>
                      </div>
                    ))}
                    <div className="flex items-baseline justify-between gap-4 py-2.5 text-sm">
                      <dt className="font-medium text-accent">Available additional shares</dt>
                      <dd className="tnum font-semibold text-accent">{inr(availableShares)} shares</dd>
                    </div>
                    <div className="flex items-baseline justify-between gap-4 py-2.5 text-sm">
                      <dt className="font-medium text-accent">Available nominal capital</dt>
                      <dd className="tnum font-semibold text-accent">{rupees(availableNominalCapital)}</dd>
                    </div>
                    {issuePrice > 0 && (
                      <div className="flex items-baseline justify-between gap-4 py-2.5 text-sm">
                        <dt className="text-muted">Potential consideration at ₹{issuePrice}</dt>
                        <dd className="tnum font-medium text-ink">{rupees(potentialConsideration)}</dd>
                      </div>
                    )}
                  </dl>
                </Card>

                <Card className="p-6">
                  <div className="flex items-center justify-between gap-3 border-b border-border pb-3">
                    <h3 className="text-[13px] font-semibold uppercase tracking-[0.09em] text-muted">
                      Proposed issue impact
                    </h3>
                    <Badge tone={isExceeded ? "block" : "neutral"}>
                      {isExceeded ? "exceeds capacity" : "within capacity"}
                    </Badge>
                  </div>
                  <dl className="mt-2 divide-y divide-border">
                    {([
                      ["New shares proposed", `${inr(proposedShares)} shares`],
                      ["Issue price per share", `₹${issuePrice}`],
                      ["Face value component", `₹${faceValue} / share`],
                      ["Premium component", `₹${premiumPerShare} / share · ${rupees(totalPremium)} total`],
                      ["Nominal capital increase", rupees(nominalIncrease)],
                      ["Post-issue shares", `${inr(postIssueShares)} shares`],
                    ] as const).map(([k, v]) => (
                      <div key={k} className="flex items-baseline justify-between gap-4 py-2.5 text-sm">
                        <dt className="text-muted">{k}</dt>
                        <dd className="tnum font-medium text-ink">{v}</dd>
                      </div>
                    ))}
                    <div className="flex items-baseline justify-between gap-4 py-2.5 text-sm">
                      <dt className="font-medium text-ink">Total amount raised</dt>
                      <dd className="tnum font-semibold text-ink">{rupees(totalConsideration)}</dd>
                    </div>
                  </dl>
                </Card>
              </div>
            </>
          )}

          <p className="rounded-xl bg-surface-2 p-4 text-xs leading-relaxed text-muted">
            <strong className="text-ink-2">Capacity is arithmetic.</strong> Unused authorised
            capital is authorised minus issued. Whether the company may lawfully issue against it
            is a separate question, evaluated under the applicable statutory provisions.{" "}
            <Link href="/signup" className="text-accent hover:underline">
              Create an account to run a legal assessment
            </Link>.
          </p>
        </div>
      </div>
    </div>
  );
}


/** "Work backwards": pick a goal, get the share count that reaches it, and
 *  apply it to the inputs so the rest of the page recomputes. */
function SolverCard({ solve, onApply }: {
  solve: (mode: "raise" | "stake" | "floor", target: number) =>
    { shares: number } | { error: string };
  onApply: (shares: number) => void;
}) {
  const MODES = [
    { id: "raise" as const, label: "Raise an amount", unit: "₹", placeholder: "1,25,00,000",
      hint: "How many shares raise this much at the issue price?" },
    { id: "stake" as const, label: "Investor takes", unit: "%", placeholder: "20",
      hint: "How many shares give the investor this stake after the issue?" },
    { id: "floor" as const, label: "Promoters stay at least", unit: "%", placeholder: "51",
      hint: "The largest issue that keeps promoters at or above this." },
  ];
  const [mode, setMode] = useState<"raise" | "stake" | "floor">("raise");
  const [target, setTarget] = useState("");
  const active = MODES.find((m) => m.id === mode)!;
  const result = target.trim() === "" ? null : solve(mode, Number(target));

  return (
    <Card className="p-6">
      <SectionTitle hint="solve in reverse">Work backwards</SectionTitle>
      <div className="mt-3 flex flex-wrap gap-1.5">
        {MODES.map((m) => (
          <button key={m.id} type="button" onClick={() => setMode(m.id)}
                  aria-pressed={mode === m.id}
                  className={`rounded-lg px-3 py-1.5 text-[12px] transition-colors ${
                    mode === m.id ? "bg-accent text-white"
                                  : "border border-border bg-surface text-muted hover:border-accent/40"}`}>
            {m.label}
          </button>
        ))}
      </div>

      <p className="mt-3 text-[12px] leading-relaxed text-muted">{active.hint}</p>

      <div className="mt-3 flex items-center gap-2">
        <span className="text-sm text-muted">{active.unit}</span>
        <input type="number" min="0" value={target} placeholder={active.placeholder}
               onChange={(e) => setTarget(e.target.value)}
               aria-label={`${active.label} target`}
               className={inputCls} />
      </div>

      {result && "error" in result && (
        <p className="mt-3 rounded-lg border border-warn/30 bg-warn-bg px-3 py-2 text-[12px] text-ink-2">
          {result.error}
        </p>
      )}
      {result && "shares" in result && (
        <div className="mt-3 rounded-xl border border-accent/30 bg-accent-dim p-3.5">
          <p className="text-[11px] uppercase tracking-[0.07em] text-muted">Issue</p>
          <p className="tnum mt-1 text-[22px] font-semibold text-accent">
            {inr(result.shares)} <span className="text-[13px] font-medium text-muted">shares</span>
          </p>
          <Button className="mt-3 w-full" onClick={() => onApply(result.shares)}>
            Apply to the calculator
          </Button>
        </div>
      )}
    </Card>
  );
}
