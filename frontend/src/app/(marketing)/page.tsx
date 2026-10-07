"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useCountUp, useReveal } from "@/lib/useReveal";

const PIPELINE = [
  "Company information", "Transaction type", "Capital structure",
  "Legal rules", "Calculation", "Compliance result",
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
  const root = useReveal<HTMLElement>();
  const [facts, setFacts] = useState<{ sources: number; provisions: number } | null>(null);

  useEffect(() => {
    api.sources()
      .then((r) => setFacts({
        sources: r.count,
        provisions: r.sources.reduce((n, s) => n + s.provision_count, 0),
      }))
      .catch(() => { /* a marketing page must not depend on an API call */ });
  }, []);

  const sources = useCountUp(facts?.sources ?? null);
  const provisions = useCountUp(facts?.provisions ?? null);

  return (
    <main ref={root}>
      {/* ------------------------------------------------------------ hero */}
      <section className="relative overflow-hidden bg-hero">
        {/* Two slow-drifting light sources and a faint grid give the navy some
            depth without any image weight. */}
        <span aria-hidden className="drift pointer-events-none absolute -left-40 -top-40 h-[34rem] w-[34rem]
                                     rounded-full bg-[#4F7DF3]/25 blur-3xl" />
        <span aria-hidden className="drift-slow pointer-events-none absolute -right-32 top-20 h-[28rem] w-[28rem]
                                     rounded-full bg-[#7C5CFF]/20 blur-3xl" />
        <span aria-hidden
              className="pointer-events-none absolute inset-0 opacity-[0.07]"
              style={{
                backgroundImage:
                  "linear-gradient(to right, #fff 1px, transparent 1px),"
                  + "linear-gradient(to bottom, #fff 1px, transparent 1px)",
                backgroundSize: "56px 56px",
                maskImage: "radial-gradient(ellipse 70% 60% at 50% 0%, #000 40%, transparent 100%)",
              }} />

        <div className="relative mx-auto max-w-[1180px] px-5 py-24 sm:px-7 sm:py-32">
          <p className="reveal font-mono text-[11px] uppercase tracking-[0.16em] text-white/55">
            For company secretaries, chartered accountants and corporate advisors
          </p>
          <h1 className="reveal reveal-d1 mt-5 max-w-3xl text-[40px] font-semibold leading-[1.08]
                         tracking-tight text-white sm:text-[60px]">
            Know how much your company{" "}
            <span className="bg-gradient-to-r from-[#9DBBFF] to-white bg-clip-text text-transparent">
              can issue.
            </span>
          </h1>
          <p className="reveal reveal-d2 mt-6 max-w-2xl text-[17px] leading-relaxed text-white/75">
            Calculate permissible share issuance, understand applicable legal conditions, and
            identify required compliances — all in one place.
          </p>
          <div className="reveal reveal-d3 mt-9 flex flex-wrap items-center gap-3">
            <Link href="/signup"
                  className="lift rounded-lg bg-white px-6 py-3 text-sm font-semibold text-[#111C3A]
                             shadow-lg shadow-black/20 hover:bg-white/90">
              Get started
            </Link>
            <Link href="/calculator"
                  className="lift rounded-lg border border-white/25 px-6 py-3 text-sm font-medium
                             text-white backdrop-blur hover:border-white/55 hover:bg-white/5">
              Explore calculator
            </Link>
          </div>

          <dl className="reveal reveal-d4 mt-16 flex flex-wrap gap-x-14 gap-y-6 border-t
                         border-white/15 pt-8">
            {[
              [facts ? sources.toLocaleString() : "—", "source documents held"],
              [facts ? provisions.toLocaleString() : "—", "citable provisions"],
              ["SEBI · MCA · NSE · BSE", "authorities covered"],
            ].map(([v, k]) => (
              <div key={k}>
                <dt className="tnum text-[28px] font-semibold text-white">{v}</dt>
                <dd className="mt-1 text-[12px] text-white/55">{k}</dd>
              </div>
            ))}
          </dl>
        </div>
      </section>

      {/* ------------------------------------------------------- authorities */}
      <div className="overflow-hidden border-b border-border bg-surface py-5">
        <div className="flex w-max gap-14 marquee" aria-hidden>
          {/* Duplicated so the -50% translate loops seamlessly. The list is
              announced once to assistive tech by the sr-only line below. */}
          {[0, 1].map((copy) => (
            <div key={copy} className="flex shrink-0 gap-14">
              {["SEBI ICDR", "SEBI LODR", "SEBI SAST", "Companies Act 2013",
                "MCA Rules", "NSE", "BSE", "SEBI Master Circulars"].map((a) => (
                <span key={a} className="whitespace-nowrap font-mono text-[12px]
                                         uppercase tracking-[0.14em] text-faint">
                  {a}
                </span>
              ))}
            </div>
          ))}
        </div>
        <p className="sr-only">
          Sources covered: SEBI ICDR, LODR and SAST Regulations, the Companies Act 2013,
          MCA Rules, NSE, BSE and the SEBI master circulars.
        </p>
      </div>

      {/* -------------------------------------------- what the platform does */}
      <section className="mx-auto max-w-[1180px] px-5 py-20 sm:px-7 sm:py-24">
        <div className="reveal">
          <h2 className="text-[28px] font-semibold tracking-tight sm:text-[34px]">
            What the platform does
          </h2>
          <span aria-hidden className="mt-4 block h-px w-24 bg-gradient-to-r from-accent to-transparent" />
          <p className="mt-4 max-w-2xl text-sm leading-relaxed text-muted">
            Your company&rsquo;s facts are run against a versioned database of the law in force,
            and every answer carries the provision it came from.
          </p>
        </div>

        <div className="relative mt-12">
          {/* The connector sits behind the cards and carries a travelling sheen. */}
          <span aria-hidden
                className="sheen absolute left-0 right-0 top-[38px] hidden h-px
                           overflow-hidden bg-border lg:block" />
          <ol className="relative grid gap-3 sm:grid-cols-2 lg:grid-cols-6">
            {PIPELINE.map((label, i) => (
              <li key={label} className={`reveal reveal-d${Math.min(4, i)}`}>
                <div className="lift rim h-full rounded-[var(--radius-card)] border border-border
                                bg-surface p-4 hover:border-accent/40 hover:shadow-md">
                  <span className="tnum font-mono text-[11px] text-accent">
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <p className="mt-2 text-[13px] font-medium leading-snug text-ink">{label}</p>
                </div>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* ------------------------------------------------------ how it works */}
      <section className="border-y border-border bg-surface">
        <div className="mx-auto max-w-[1180px] px-5 py-20 sm:px-7 sm:py-24">
          <div className="reveal">
            <h2 className="text-[28px] font-semibold tracking-tight sm:text-[34px]">
              How it works
            </h2>
            <span aria-hidden className="mt-4 block h-px w-24 bg-gradient-to-r from-accent to-transparent" />
          </div>
          <ol className="mt-12 grid gap-x-10 gap-y-9 md:grid-cols-2 lg:grid-cols-3">
            {STEPS.map((s, i) => (
              <li key={s.n} className={`reveal reveal-d${Math.min(4, i)} flex gap-4`}>
                <span aria-hidden
                      className="tnum grid h-10 w-10 shrink-0 place-items-center rounded-full
                                 bg-accent-dim text-sm font-semibold text-accent
                                 ring-4 ring-accent/5">
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
      <section className="relative overflow-hidden bg-hero">
        <span aria-hidden className="drift pointer-events-none absolute -left-24 top-0 h-[22rem] w-[22rem]
                                     rounded-full bg-[#4F7DF3]/25 blur-3xl" />
        <div className="relative mx-auto max-w-[1180px] px-5 py-24 text-center sm:px-7">
        <div className="reveal">
          <h2 className="text-[28px] font-semibold tracking-tight text-white sm:text-[34px]">
            Start with your own company
          </h2>
          <p className="mx-auto mt-4 max-w-xl text-sm leading-relaxed text-white/70">
            Creating an account sets up a workspace for your organisation. Nothing you enter is
            shared with any other organisation.
          </p>
          <div className="mt-9 flex flex-wrap items-center justify-center gap-3">
            <Link href="/signup"
                  className="lift rounded-lg bg-white px-6 py-3 text-sm font-semibold text-[#111C3A]
                             shadow-lg shadow-black/20 hover:bg-white/90">
              Create an account
            </Link>
            <Link href="/calculator"
                  className="lift rounded-lg border border-white/25 px-6 py-3 text-sm
                             font-medium text-white hover:border-white/55 hover:bg-white/5">
              Try the calculator first
            </Link>
          </div>
        </div>
        </div>
      </section>
    </main>
  );
}
