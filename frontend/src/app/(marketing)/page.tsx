"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card } from "@/components/ui";

/** The pipeline the platform runs, in the order a user meets it. */
const PIPELINE = [
  "Company information",
  "Transaction type",
  "Capital structure",
  "Legal rules",
  "Calculation",
  "Compliance result",
];

const STEPS = [
  { n: 1, title: "Add your company",
    body: "Name, CIN, listing status. A company that is not registered yet is fine — it is marked as user-entered wherever it appears." },
  { n: 2, title: "Select the proposed issue",
    body: "Rights, preferential, bonus, private placement and more. Each route carries its own statutory conditions." },
  { n: 3, title: "Enter capital and share information",
    body: "Authorised and issued capital, face value, shareholders and previous issues. Anything already on file is skipped." },
  { n: 4, title: "Get the calculated result",
    body: "Capital capacity and legal issue capacity, reported separately — because they are different questions with different answers." },
  { n: 5, title: "View the detailed legal analysis",
    body: "Every conclusion traces to an exact provision, page and source document, with the text shown inline." },
];

export default function LandingPage() {
  // Real figures from the corpus. The audience here is sceptical by trade, so
  // the honest version of social proof is the actual size of the rule base —
  // and if the API is unreachable the strip simply does not render.
  const [facts, setFacts] = useState<{ sources: number; provisions: number } | null>(null);
  useEffect(() => {
    api.health()
      .then(() => api.sources())
      .then((r) => setFacts({
        sources: r.count,
        provisions: r.sources.reduce((n, s) => n + s.provision_count, 0),
      }))
      .catch(() => { /* a marketing page must not depend on an API call */ });
  }, []);

  return (
    <main>
      {/* ------------------------------------------------------------ hero */}
      <section className="bg-hero">
        <div className="mx-auto max-w-[1180px] px-5 py-20 sm:px-7 sm:py-28">
          <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-white/60">
            For company secretaries, chartered accountants and corporate advisors
          </p>
          <h1 className="mt-5 max-w-3xl text-[38px] font-semibold leading-[1.1] tracking-tight
                         text-white sm:text-[56px]">
            Know how much your company can issue.
          </h1>
          <p className="mt-6 max-w-2xl text-[17px] leading-relaxed text-white/75">
            Calculate permissible share issuance, understand applicable legal conditions, and
            identify required compliances — all in one place.
          </p>
          <div className="mt-9 flex flex-wrap items-center gap-3">
            <Link href="/signup"
                  className="rounded-lg bg-white px-6 py-3 text-sm font-semibold text-[#111C3A]
                             hover:bg-white/90">
              Get started
            </Link>
            <Link href="/calculator"
                  className="rounded-lg border border-white/25 px-6 py-3 text-sm font-medium
                             text-white hover:border-white/50">
              Explore calculator
            </Link>
          </div>

          {facts && (
            <dl className="mt-14 flex flex-wrap gap-x-12 gap-y-6 border-t border-white/15 pt-8">
              {[
                [facts.sources.toLocaleString(), "source documents held"],
                [facts.provisions.toLocaleString(), "citable provisions"],
                ["SEBI · MCA · NSE · BSE", "authorities covered"],
              ].map(([v, k]) => (
                <div key={k}>
                  <dt className="tnum text-[26px] font-semibold text-white">{v}</dt>
                  <dd className="mt-1 text-[12px] text-white/60">{k}</dd>
                </div>
              ))}
            </dl>
          )}
        </div>
      </section>

      {/* -------------------------------------------- what the platform does */}
      <section className="mx-auto max-w-[1180px] px-5 py-16 sm:px-7 sm:py-20">
        <h2 className="text-[26px] font-semibold tracking-tight sm:text-[32px]">
          What the platform does
        </h2>
        <p className="mt-3 max-w-2xl text-sm leading-relaxed text-muted">
          Your company&rsquo;s facts are run against a versioned database of the law in force,
          and every answer carries the provision it came from.
        </p>

        <ol className="mt-10 grid gap-3 sm:grid-cols-2 lg:grid-cols-6">
          {PIPELINE.map((label, i) => (
            <li key={label} className="relative">
              <Card className="h-full p-4">
                <span className="tnum font-mono text-[11px] text-accent">
                  {String(i + 1).padStart(2, "0")}
                </span>
                <p className="mt-2 text-[13px] font-medium leading-snug text-ink">{label}</p>
              </Card>
              {i < PIPELINE.length - 1 && (
                <span aria-hidden
                      className="absolute -right-2 top-1/2 hidden -translate-y-1/2 text-border-lit
                                 lg:block">
                  ›
                </span>
              )}
            </li>
          ))}
        </ol>
      </section>

      {/* ------------------------------------------------------ how it works */}
      <section className="border-y border-border bg-surface">
        <div className="mx-auto max-w-[1180px] px-5 py-16 sm:px-7 sm:py-20">
          <h2 className="text-[26px] font-semibold tracking-tight sm:text-[32px]">How it works</h2>
          <ol className="mt-10 grid gap-x-10 gap-y-8 md:grid-cols-2 lg:grid-cols-3">
            {STEPS.map((s) => (
              <li key={s.n} className="flex gap-4">
                <span aria-hidden
                      className="tnum grid h-9 w-9 shrink-0 place-items-center rounded-full
                                 bg-accent-dim text-sm font-semibold text-accent">
                  {s.n}
                </span>
                <div>
                  <h3 className="text-[15px] font-semibold tracking-tight text-ink">{s.title}</h3>
                  <p className="mt-1.5 text-[13px] leading-relaxed text-muted">{s.body}</p>
                </div>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* -------------------------------------------------------------- cta */}
      <section className="mx-auto max-w-[1180px] px-5 py-20 text-center sm:px-7">
        <h2 className="text-[26px] font-semibold tracking-tight sm:text-[32px]">
          Start with your own company
        </h2>
        <p className="mx-auto mt-3 max-w-xl text-sm leading-relaxed text-muted">
          Creating an account sets up a workspace for your organisation. Nothing you enter is
          shared with any other organisation.
        </p>
        <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
          <Link href="/signup"
                className="rounded-lg bg-accent px-6 py-3 text-sm font-semibold text-white
                           hover:bg-accent-hi">
            Create an account
          </Link>
          <Link href="/calculator"
                className="rounded-lg border border-border-lit px-6 py-3 text-sm font-medium
                           text-ink-2 hover:border-accent/50 hover:text-accent">
            Try the calculator first
          </Link>
        </div>
      </section>
    </main>
  );
}
