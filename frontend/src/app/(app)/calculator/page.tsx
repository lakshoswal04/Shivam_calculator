"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { inr, rupees } from "@/lib/api";
import { Banner, Button, Field, Input, SectionTitle } from "@/components/ui";

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

  return (
    <div className="mx-auto max-w-5xl space-y-8">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-ink-1">
            Authorised Capital & Share Issue Capacity Calculator
          </h1>
          <p className="mt-1 text-sm text-muted">
            Determine maximum additional share capacity, nominal capital, securities premium, and post-issue capital position.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" onClick={loadStandardExample} className="text-xs">
            PRD Standard Example (10L @ ₹125)
          </Button>
          <Button variant="secondary" onClick={loadExceedsExample} className="text-xs">
            Exceeds Capacity Example (4L shares)
          </Button>
        </div>
      </div>

      {/* Input Section */}
      <div className="rounded-xl border border-border bg-ground p-6 shadow-sm">
        <SectionTitle hint="All calculations derive dynamically">Company Capital & Issue Inputs</SectionTitle>

        {/* Face Value Selector */}
        <div className="mt-4 space-y-2">
          <label className="text-xs font-semibold uppercase tracking-wider text-muted">
            Face Value per Share (₹)
          </label>
          <div className="flex flex-wrap items-center gap-3">
            <div className="w-36">
              <Input
                type="number"
                step="0.01"
                min="0.01"
                value={faceValueStr}
                onChange={(v) => applyFaceValue(Number(v))}
              />
            </div>
            <div className="flex items-center gap-1.5">
              {[1, 2, 5, 10, 100].map((preset) => (
                <button
                  key={preset}
                  type="button"
                  onClick={() => applyFaceValue(preset)}
                  className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                    faceValue === preset
                      ? "bg-accent text-white"
                      : "border border-border bg-surface-1 text-ink-2 hover:bg-surface-2"
                  }`}
                >
                  ₹{preset}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Capital Inputs Grid */}
        <div className="mt-6 grid gap-6 sm:grid-cols-2">
          {/* Authorised Capital */}
          <div className="space-y-3 rounded-lg border border-border/80 bg-surface-1/40 p-4">
            <div className="text-xs font-semibold uppercase tracking-wider text-accent">
              1. Authorised Capital
            </div>
            <Field label="Authorised Share Capital (₹)">
              <Input
                type="number"
                step="1"
                value={authCapitalStr}
                onChange={handleAuthCapitalChange}
                placeholder="e.g. 50,00,000"
              />
            </Field>
            <Field label="Total Authorised Shares">
              <Input
                type="number"
                step="1"
                value={authSharesStr}
                onChange={handleAuthSharesChange}
                placeholder="e.g. 5,00,000"
              />
            </Field>
            <div className="text-[11px] text-faint">
              {faceValue > 0
                ? `${rupees(authCapital)} ÷ ₹${faceValue} = ${inr(authShares)} authorised shares`
                : "Enter face value to derive shares"}
            </div>
          </div>

          {/* Existing Issued Capital */}
          <div className="space-y-3 rounded-lg border border-border/80 bg-surface-1/40 p-4">
            <div className="text-xs font-semibold uppercase tracking-wider text-accent">
              2. Existing Issued Capital
            </div>
            <Field label="Existing Issued Share Capital (₹)">
              <Input
                type="number"
                step="1"
                value={issuedCapitalStr}
                onChange={handleIssuedCapitalChange}
                placeholder="e.g. 20,00,000"
              />
            </Field>
            <Field label="Already Issued Shares">
              <Input
                type="number"
                step="1"
                value={issuedSharesStr}
                onChange={handleIssuedSharesChange}
                placeholder="e.g. 2,00,000"
              />
            </Field>
            <div className="text-[11px] text-faint">
              {faceValue > 0
                ? `${rupees(issuedCapital)} ÷ ₹${faceValue} = ${inr(issuedShares)} shares already issued`
                : "Enter face value to derive shares"}
            </div>
          </div>
        </div>

        {/* Proposed Issue Inputs Grid */}
        <div className="mt-6 space-y-3 rounded-lg border border-border/80 bg-surface-1/40 p-4">
          <div className="text-xs font-semibold uppercase tracking-wider text-accent">
            3. Proposed New Issue
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="How many new shares do you want to issue? (Proposed Shares)" required>
              <Input
                type="number"
                step="1"
                min="0"
                value={proposedSharesStr}
                onChange={setProposedSharesStr}
                placeholder="e.g. 1,00,000"
              />
            </Field>
            <Field label="Issue Price per Share (₹)" required>
              <Input
                type="number"
                step="0.01"
                min="0"
                value={issuePriceStr}
                onChange={setIssuePriceStr}
                placeholder="e.g. 125"
              />
            </Field>
          </div>
        </div>
      </div>

      {/* Takeaway Headline Banner (Requirement 6) */}
      <Banner tone="info" title="Current Capital Capacity Takeaway">
        At a <strong>₹{faceValue}</strong> face value, the company currently has capacity for{" "}
        <strong className="text-accent">{inr(availableShares)} additional shares</strong> (₹
        {inr(availableNominalCapital)} nominal capital) within its existing authorised capital.
      </Banner>

      {/* Validation Banners */}
      {isExceeded && (
        <Banner tone="warn" title="⚠ Proposed issue exceeds current authorised share capacity">
          <div className="mt-1 space-y-2 text-sm">
            <p>
              The proposed issue of <strong>{inr(proposedShares)} shares</strong> exceeds the available authorised capacity of <strong>{inr(availableShares)} shares</strong> by <strong>{inr(excessShares)} shares</strong> (Nominal Shortfall: {rupees(excessNominalCapital)}).
            </p>
            <div className="rounded border border-warn/30 bg-warn-bg/50 p-3 text-xs leading-relaxed text-ink-1">
              <strong>Legal Note:</strong> This does not mean the transaction is legally impossible. Additional authorised capital may be required before allotment, subject to shareholder approval (Special Resolution in EGM) and filing Form SH-7 with the Registrar of Companies (ROC).
            </div>
          </div>
        </Banner>
      )}

      {isDiscount && (
        <Banner tone="warn" title="⚠ Prohibition on Issue of Shares at a Discount">
          Under Section 53 of the Companies Act, 2013, any share issued by a company at a discounted price (below face value of ₹{faceValue}) shall be void, except in the case of sweat equity shares issued under Section 54.
        </Banner>
      )}

      {/* Summary Dashboard (Requirement 13) */}
      <div className="grid gap-6 md:grid-cols-2">
        {/* CURRENT CAPITAL POSITION Card */}
        <div className="flex flex-col justify-between rounded-xl border border-border bg-ground p-6 shadow-sm">
          <div>
            <div className="flex items-center justify-between border-b border-border pb-3">
              <h3 className="text-xs font-bold uppercase tracking-wider text-accent">
                Current Capital Position
              </h3>
              <span className="rounded bg-accent-dim/40 px-2 py-0.5 font-mono text-[11px] text-accent">
                Cap Engine §15
              </span>
            </div>

            <dl className="mt-4 divide-y divide-border/60">
              <div className="flex justify-between py-2 text-sm">
                <dt className="text-muted">Authorised Capital</dt>
                <dd className="font-semibold text-ink-1">{rupees(authCapital)}</dd>
              </div>
              <div className="flex justify-between py-2 text-sm">
                <dt className="text-muted">Face Value per Share</dt>
                <dd className="font-medium text-ink-1">₹{faceValue}</dd>
              </div>
              <div className="flex justify-between py-2 text-sm">
                <dt className="text-muted">Total Authorised Shares</dt>
                <dd className="font-semibold text-ink-1">{inr(authShares)} shares</dd>
              </div>
              <div className="flex justify-between py-2 text-sm">
                <dt className="text-muted">Already Issued Shares</dt>
                <dd className="font-medium text-ink-1">{inr(issuedShares)} shares</dd>
              </div>
              <div className="flex justify-between py-2 text-sm bg-accent-dim/20 px-2 rounded">
                <dt className="font-semibold text-accent">Available Additional Shares</dt>
                <dd className="font-bold text-accent">{inr(availableShares)} shares</dd>
              </div>
              <div className="flex justify-between py-2 text-sm bg-accent-dim/20 px-2 rounded">
                <dt className="font-semibold text-accent">Available Nominal Capital</dt>
                <dd className="font-bold text-accent">{rupees(availableNominalCapital)}</dd>
              </div>
              {issuePrice > 0 && (
                <div className="flex justify-between py-2 text-sm">
                  <dt className="text-muted">Potential Issue Consideration (at ₹{issuePrice})</dt>
                  <dd className="font-semibold text-ink-1">{rupees(potentialConsideration)}</dd>
                </div>
              )}
            </dl>
          </div>

          <div className="mt-6 rounded-lg bg-surface-1 p-3 text-xs text-muted">
            <strong>Capacity Definition:</strong> Unused authorised capital is arithmetic (Authorised − Issued). Legal issue capacity is evaluated separately under applicable statutory provisions.
          </div>
        </div>

        {/* PROPOSED ISSUE Card */}
        <div className="flex flex-col justify-between rounded-xl border border-border bg-ground p-6 shadow-sm">
          <div>
            <div className="flex items-center justify-between border-b border-border pb-3">
              <h3 className="text-xs font-bold uppercase tracking-wider text-accent">
                Proposed Issue Impact
              </h3>
              <span className={`rounded px-2 py-0.5 font-mono text-[11px] ${isExceeded ? "bg-warn-bg text-warn font-semibold" : "bg-surface-2 text-muted"}`}>
                {isExceeded ? "Exceeds Capacity" : "Within Capacity"}
              </span>
            </div>

            <dl className="mt-4 divide-y divide-border/60">
              <div className="flex justify-between py-2 text-sm">
                <dt className="text-muted">New Shares Proposed</dt>
                <dd className="font-semibold text-ink-1">{inr(proposedShares)} shares</dd>
              </div>
              <div className="flex justify-between py-2 text-sm">
                <dt className="text-muted">Issue Price per Share</dt>
                <dd className="font-medium text-ink-1">₹{issuePrice}</dd>
              </div>
              <div className="flex justify-between py-2 text-sm">
                <dt className="text-muted">Face Value Component</dt>
                <dd className="font-medium text-ink-1">₹{faceValue} / share</dd>
              </div>
              <div className="flex justify-between py-2 text-sm">
                <dt className="text-muted">Premium Component</dt>
                <dd className="font-medium text-ink-1">
                  ₹{premiumPerShare} / share ({rupees(totalPremium)} total)
                </dd>
              </div>
              <div className="flex justify-between py-2 text-sm">
                <dt className="text-muted">Nominal Capital Increase</dt>
                <dd className="font-semibold text-ink-1">{rupees(nominalIncrease)}</dd>
              </div>
              <div className="flex justify-between py-2 text-sm bg-accent-dim/30 px-2 rounded">
                <dt className="font-semibold text-ink-1">Total Amount Raised (Consideration)</dt>
                <dd className="font-bold text-ink-1">{rupees(totalConsideration)}</dd>
              </div>
              <div className="flex justify-between py-2 text-sm">
                <dt className="text-muted">Post-Issue Shares</dt>
                <dd className="font-medium text-ink-1">{inr(postIssueShares)} shares</dd>
              </div>
              <div className="flex justify-between py-2 text-sm">
                <dt className="text-muted">Shares Remaining After Issue</dt>
                <dd className={`font-semibold ${isExceeded ? "text-warn" : "text-ink-1"}`}>
                  {isExceeded ? `-${inr(excessShares)} (Deficit)` : `${inr(remainingAuthorisedShares)} shares`}
                </dd>
              </div>
            </dl>
          </div>

          <div className="mt-6">
            <Link
              href={`/assess`}
            >
              <Button className="w-full">
                Continue to Legal Assessment →
              </Button>
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
