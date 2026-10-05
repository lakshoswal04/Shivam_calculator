"use client";

import { useMemo, useState } from "react";
import { inr, rupees } from "@/lib/api";
import {
  Badge, Banner, Button, Card, Donut, Field, HeroButton, HeroCard,
  Input, MiniBars, SectionTitle, Stat,
} from "@/components/ui";

export default function CalculatorPage() {
  // State inputs
  const [faceValueStr, setFaceValueStr] = useState("10");
  const [authCapitalStr, setAuthCapitalStr] = useState("5000000");
  const [authSharesStr, setAuthSharesStr] = useState("500000");
  const [issuedCapitalStr, setIssuedCapitalStr] = useState("2000000");
  const [issuedSharesStr, setIssuedSharesStr] = useState("200000");
  const [proposedSharesStr, setProposedSharesStr] = useState("100000");
  const [issuePriceStr, setIssuePriceStr] = useState("125");

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
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h1 className="text-[32px] font-semibold leading-tight tracking-tight sm:text-[40px]">
            Capital calculator
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted">
            Maximum additional share capacity, nominal capital, securities premium and the
            post-issue capital position. Arithmetic only — legal issue capacity is a separate
            question, answered by an assessment.
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

      {/* Headline figure, with the stat tiles beside it as in the reference. */}
      <div className="grid gap-4 lg:grid-cols-[1.35fr_1fr]">
        <HeroCard
          tone={isExceeded ? "alert" : "default"}
          label={isExceeded ? "Capacity exceeded" : "Available additional shares"}
          value={isExceeded ? `−${inr(excessShares)}` : inr(availableShares)}
          unit="shares"
          sub={isExceeded
            ? `The proposed ${inr(proposedShares)} shares exceed available capacity of ${inr(availableShares)} by ${inr(excessShares)} — a nominal shortfall of ${rupees(excessNominalCapital)}.`
            : `${rupees(availableNominalCapital)} of nominal capital remains unused within the authorised capital, at a face value of ₹${faceValue}.`}
          actions={
            <>
              <HeroButton href="/assess">Continue to legal assessment</HeroButton>
              {issuePrice > 0 && (
                <HeroButton variant="light">
                  Raises {rupees(potentialConsideration)} at ₹{issuePrice}
                </HeroButton>
              )}
            </>
          }
        />

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-1">
          <Card className="p-5">
            <Stat label="Total amount raised" value={rupees(totalConsideration)}
                  delta={totalPremium > 0 ? `+${rupees(totalPremium)} premium` : "at par"}
                  deltaTone={totalPremium > 0 ? "up" : "flat"}
                  sub={`${inr(proposedShares)} shares × ₹${issuePrice}`} />
          </Card>
          <Card className="p-5">
            <Stat label="Nominal capital increase" value={rupees(nominalIncrease)}
                  delta={isExceeded ? "exceeds authorised" : "within authorised"}
                  deltaTone={isExceeded ? "down" : "up"}
                  sub={`${inr(proposedShares)} shares × ₹${faceValue} face value`} />
          </Card>
        </div>
      </div>

      {/* Section 53 is a prohibition, not a capacity matter, so it stays a banner. */}
      {isDiscount && (
        <Banner tone="warn" title="Prohibition on issue of shares at a discount">
          Under section 53 of the Companies Act, 2013, a share issued below its face value of
          ₹{faceValue} is void, except for sweat equity shares issued under section 54.
        </Banner>
      )}

      {isExceeded && (
        <Banner tone="warn" title="Increasing authorised capital">
          This does not mean the transaction is legally impossible. Additional authorised capital
          may be required before allotment, subject to shareholder approval by special resolution
          and filing Form SH-7 with the Registrar of Companies.
        </Banner>
      )}

      <div className="grid gap-4 xl:grid-cols-[1.1fr_1fr]">
        {/* ---------------------------------------------------------- inputs */}
        <Card className="p-6">
          <SectionTitle hint="every figure derives live">Capital and issue inputs</SectionTitle>

          <div className="mt-4 space-y-2">
            <label className="text-[11px] font-semibold uppercase tracking-[0.09em] text-muted">
              Face value per share (₹)
            </label>
            <div className="flex flex-wrap items-center gap-3">
              <div className="w-32">
                <Input type="number" step="0.01" min="0.01" value={faceValueStr}
                       onChange={(v) => applyFaceValue(Number(v))} />
              </div>
              <div className="flex flex-wrap items-center gap-1.5">
                {[1, 2, 5, 10, 100].map((preset) => (
                  <button key={preset} type="button" onClick={() => applyFaceValue(preset)}
                          aria-pressed={faceValue === preset}
                          className={`rounded-lg px-3.5 py-1.5 text-xs font-medium transition-colors ${
                            faceValue === preset
                              ? "bg-accent text-white"
                              : "border border-border bg-surface text-ink-2 hover:border-accent/50"}`}>
                    ₹{preset}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="mt-6 grid gap-4 sm:grid-cols-2">
            <div className="space-y-3 rounded-2xl border border-border bg-surface-2/40 p-4">
              <div className="text-[11px] font-semibold uppercase tracking-[0.09em] text-accent-hi">
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

            <div className="space-y-3 rounded-2xl border border-border bg-surface-2/40 p-4">
              <div className="text-[11px] font-semibold uppercase tracking-[0.09em] text-accent-hi">
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
          </div>

          <div className="mt-4 space-y-3 rounded-2xl border border-border bg-surface-2/40 p-4">
            <div className="text-[11px] font-semibold uppercase tracking-[0.09em] text-accent-hi">
              3 · Proposed new issue
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="New shares to issue" required>
                <Input type="number" step="1" min="0" value={proposedSharesStr}
                       onChange={setProposedSharesStr} placeholder="e.g. 1,00,000" />
              </Field>
              <Field label="Issue price per share (₹)" required>
                <Input type="number" step="0.01" min="0" value={issuePriceStr}
                       onChange={setIssuePriceStr} placeholder="e.g. 125" />
              </Field>
            </div>
          </div>
        </Card>

        {/* ------------------------------------------------- capital position */}
        <div className="space-y-4">
          <Card className="p-6">
            <div className="flex items-center justify-between gap-3">
              <SectionTitle>Authorised capital, post-issue</SectionTitle>
              <Badge tone={isExceeded ? "block" : "accent"}>
                {isExceeded ? "exceeds capacity" : "within capacity"}
              </Badge>
            </div>
            <div className="mt-2">
              <Donut segments={stack} total={inr(authShares)}
                     caption="How the authorised shares are accounted for after the proposed issue" />
            </div>
            <p className="mt-5 rounded-2xl bg-surface-2 p-3.5 text-xs leading-relaxed text-muted">
              <strong className="text-ink-2">Capacity is arithmetic.</strong> Unused authorised
              capital is authorised minus issued. Whether the company may lawfully issue against
              it is a separate question, evaluated under the applicable statutory provisions.
            </p>
          </Card>

          <Card className="p-6">
            <SectionTitle hint="shares">Capital ladder</SectionTitle>
            <MiniBars
              highlight="Proposed"
              bars={[
                { label: "Authorised", value: authShares, caption: inr(authShares) },
                { label: "Issued", value: issuedShares, caption: inr(issuedShares) },
                { label: "Proposed", value: proposedShares, caption: inr(proposedShares) },
                { label: "Remaining",
                  value: Math.max(0, remainingAuthorisedShares),
                  caption: isExceeded ? `−${inr(excessShares)}` : inr(remainingAuthorisedShares) },
              ]}
            />
          </Card>
        </div>
      </div>

      {/* ------------------------------------------------------------ detail */}
      <div className="grid gap-4 md:grid-cols-2">
        <Card className="p-6">
          <div className="flex items-center justify-between gap-3 border-b border-border pb-3">
            <h3 className="text-[13px] font-semibold uppercase tracking-[0.09em] text-muted">
              Current capital position
            </h3>
            <Badge tone="accent">Cap engine §15</Badge>
          </div>
          <dl className="mt-2 divide-y divide-border/70">
            {[
              ["Authorised capital", rupees(authCapital)],
              ["Face value per share", `₹${faceValue}`],
              ["Total authorised shares", `${inr(authShares)} shares`],
              ["Already issued shares", `${inr(issuedShares)} shares`],
            ].map(([k, v]) => (
              <div key={k} className="flex items-baseline justify-between gap-4 py-2.5 text-sm">
                <dt className="text-muted">{k}</dt>
                <dd className="tnum font-medium text-ink">{v}</dd>
              </div>
            ))}
            <div className="flex items-baseline justify-between gap-4 py-2.5 text-sm">
              <dt className="font-medium text-accent-hi">Available additional shares</dt>
              <dd className="tnum font-semibold text-accent-hi">{inr(availableShares)} shares</dd>
            </div>
            <div className="flex items-baseline justify-between gap-4 py-2.5 text-sm">
              <dt className="font-medium text-accent-hi">Available nominal capital</dt>
              <dd className="tnum font-semibold text-accent-hi">{rupees(availableNominalCapital)}</dd>
            </div>
            {issuePrice > 0 && (
              <div className="flex items-baseline justify-between gap-4 py-2.5 text-sm">
                <dt className="text-muted">Potential consideration at ₹{issuePrice}</dt>
                <dd className="tnum font-medium text-ink">{rupees(potentialConsideration)}</dd>
              </div>
            )}
          </dl>
        </Card>

        <Card className="flex flex-col p-6">
          <div className="flex items-center justify-between gap-3 border-b border-border pb-3">
            <h3 className="text-[13px] font-semibold uppercase tracking-[0.09em] text-muted">
              Proposed issue impact
            </h3>
            <Badge tone={isExceeded ? "block" : "neutral"}>
              {isExceeded ? "exceeds capacity" : "within capacity"}
            </Badge>
          </div>
          <dl className="mt-2 divide-y divide-border/70">
            {[
              ["New shares proposed", `${inr(proposedShares)} shares`],
              ["Issue price per share", `₹${issuePrice}`],
              ["Face value component", `₹${faceValue} / share`],
              ["Premium component", `₹${premiumPerShare} / share · ${rupees(totalPremium)} total`],
              ["Nominal capital increase", rupees(nominalIncrease)],
            ].map(([k, v]) => (
              <div key={k} className="flex items-baseline justify-between gap-4 py-2.5 text-sm">
                <dt className="text-muted">{k}</dt>
                <dd className="tnum font-medium text-ink">{v}</dd>
              </div>
            ))}
            <div className="flex items-baseline justify-between gap-4 py-2.5 text-sm">
              <dt className="font-medium text-ink">Total amount raised</dt>
              <dd className="tnum font-semibold text-ink">{rupees(totalConsideration)}</dd>
            </div>
            <div className="flex items-baseline justify-between gap-4 py-2.5 text-sm">
              <dt className="text-muted">Post-issue shares</dt>
              <dd className="tnum font-medium text-ink">{inr(postIssueShares)} shares</dd>
            </div>
            <div className="flex items-baseline justify-between gap-4 py-2.5 text-sm">
              <dt className="text-muted">Shares remaining after issue</dt>
              <dd className={`tnum font-semibold ${isExceeded ? "text-block" : "text-ink"}`}>
                {isExceeded ? `−${inr(excessShares)} deficit`
                            : `${inr(remainingAuthorisedShares)} shares`}
              </dd>
            </div>
          </dl>
          <div className="mt-6">
            <Button href="/assess" className="w-full">Continue to legal assessment →</Button>
          </div>
        </Card>
      </div>
    </div>
  );
}
