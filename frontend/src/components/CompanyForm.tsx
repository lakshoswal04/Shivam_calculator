"use client";
import { useEffect, useState } from "react";
import { api, ApiError, type CompanyCreateBody } from "@/lib/api";
import { Banner, Button, CheckboxField, Field, Input, Select } from "@/components/ui";

interface RegistryHit {
  symbol: string; name: string; isin: string;
  listing_date: string | null; face_value: string | null;
  listed_status: string; exchanges: string[];
}

const COMPANY_TYPES = [
  { value: "PRIVATE", label: "Private company" },
  { value: "PUBLIC", label: "Public company" },
  { value: "SECTION_8", label: "Section 8 company" },
  { value: "NIDHI", label: "Nidhi company" },
  { value: "GOVERNMENT", label: "Government company" },
];
const EXCHANGES = ["NSE", "BSE", "MSEI"];

// Mirrors company.companies.cin_shape and the backend pattern.
const CIN_RE = /^[LUu][0-9]{5}[A-Za-z]{2}[0-9]{4}[A-Za-z]{3}[0-9]{6}$/;
const ISIN_RE = /^IN[A-Za-z0-9]{9}[0-9]$/;

export interface CreatedCompany {
  company_id: string; name: string; cin: string | null; warnings: string[];
}

export function CompanyForm({ onCreated, onCancel, submitLabel = "Create company" }: {
  onCreated: (c: CreatedCompany) => void;
  onCancel?: () => void;
  submitLabel?: string;
}) {
  const [cin, setCin] = useState("");
  const [name, setName] = useState("");
  const [incorporated, setIncorporated] = useState("");
  const [office, setOffice] = useState("");
  const [companyType, setCompanyType] = useState("PRIVATE");
  const [listed, setListed] = useState(false);
  const [exchanges, setExchanges] = useState<string[]>([]);
  const [ticker, setTicker] = useState("");
  const [isin, setIsin] = useState("");
  const [isSme, setIsSme] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [lookupStatus, setLookupStatus] = useState<"idle" | "loading" | "found" | "existing" | "not_found" | "error">("idle");
  const [lookupError, setLookupError] = useState<string | null>(null);
  const [registryQuery, setRegistryQuery] = useState("");
  const [registryHits, setRegistryHits] = useState<RegistryHit[]>([]);
  const [registryBusy, setRegistryBusy] = useState(false);
  const [registrySearched, setRegistrySearched] = useState(false);
  const [derived, setDerived] = useState<{
    incorporation_year: number | null; state_code: string;
    registered_office_hint: string | null; company_type: string;
    company_class_code: string; cin_series: string;
  } | null>(null);
  const [existingCompany, setExistingCompany] = useState<{ id: string; name: string } | null>(null);

  async function fetchCinDetails(rawCin?: string) {
    const targetCin = (rawCin ?? cin).trim().toUpperCase();
    if (!targetCin || !CIN_RE.test(targetCin)) {
      setLookupError("Invalid CIN format.");
      setLookupStatus("error");
      return;
    }
    setLookupStatus("loading");
    setLookupError(null);
    setExistingCompany(null);
    try {
      const res = await api.lookupCin(targetCin);
      if (res && res.found) {
        // found=true now means only one thing: this CIN is already on file for
        // this organisation, so every field below is real data the user entered
        // themselves. Nothing is synthesised any more.
        if (res.name) setName(res.name);
        if (res.company_type) setCompanyType(res.company_type);
        if (res.incorporation_date) setIncorporated(res.incorporation_date);
        if (res.registered_office) setOffice(res.registered_office);

        const isListedComp = res.listed_status === "LISTED";
        setListed(isListedComp);
        if (isListedComp) {
          if (res.ticker_symbol) setTicker(res.ticker_symbol);
          if (res.isin) setIsin(res.isin);
          if (res.exchanges?.length) setExchanges(res.exchanges);
        }

        if (res.is_existing && res.company_id && res.name) {
          setExistingCompany({ id: res.company_id, name: res.name });
          setLookupStatus("existing");
        } else {
          setLookupStatus("found");
        }
      } else {
        // Unknown CIN. Pre-fill ONLY what the CIN itself encodes, and leave the
        // name alone — there is no public registry to resolve it against.
        const d = res?.derived;
        if (d) {
          setCompanyType(d.company_type);
          if (d.registered_office_hint) setOffice(d.registered_office_hint);
          setDerived(d);
        }
        setLookupStatus("not_found");
      }
    } catch {
      setLookupStatus("error");
      setLookupError("Unable to fetch company details right now. You can enter details manually.");
    }
  }

  // Debounced registry search, with the previous request aborted so a slow
  // earlier response cannot overwrite a newer one.
  useEffect(() => {
    const q = registryQuery.trim();
    if (q.length < 2) { setRegistryHits([]); setRegistrySearched(false); return; }
    const ctl = new AbortController();
    const t = setTimeout(() => {
      setRegistryBusy(true);
      api.searchRegistry(q, ctl.signal)
        .then((r) => { setRegistryHits(r.results); setRegistrySearched(true); })
        .catch((e) => { if ((e as Error).name !== "AbortError") setRegistryHits([]); })
        .finally(() => setRegistryBusy(false));
    }, 250);
    return () => { clearTimeout(t); ctl.abort(); };
  }, [registryQuery]);

  function applyRegistry(c: RegistryHit) {
    // Everything here came from NSE, so it is safe to fill in directly. The CIN
    // is deliberately NOT set: NSE does not publish one, and guessing it would
    // be the very thing this change removes.
    setName(c.name);
    setTicker(c.symbol);
    setIsin(c.isin);
    setListed(true);
    setExchanges(c.exchanges?.length ? c.exchanges : ["NSE"]);
    setCompanyType("PUBLIC");
    setRegistryHits([]);
    setRegistryQuery(c.name);
  }

  // Automatic lookup when a valid 21-character CIN is entered
  useEffect(() => {
    const clean = cin.trim().toUpperCase();
    if (clean.length === 21 && CIN_RE.test(clean) && lookupStatus === "idle") {
      fetchCinDetails(clean);
    }
  }, [cin, lookupStatus]);

  const cinError = cin.trim() && !CIN_RE.test(cin.trim())
    ? "A CIN is 21 characters, for example U27100MH2016PLC123456." : null;
  const isinError = isin.trim() && !ISIN_RE.test(isin.trim())
    ? "An ISIN is 12 characters beginning IN, for example INE123A01024." : null;
  const exchangeError = listed && exchanges.length === 0
    ? "Choose at least one exchange." : null;
  const nameError = name.trim().length > 0 && name.trim().length < 2
    ? "Enter the company's full name." : null;

  const ready = name.trim().length >= 2 && !cinError && !isinError && !exchangeError;

  async function submit() {
    setBusy(true); setError(null);
    const body: CompanyCreateBody = {
      name: name.trim(),
      cin: cin.trim() || null,
      incorporation_date: incorporated || null,
      registered_office: office.trim() || null,
      company_type: companyType,
      listed_status: listed ? "LISTED" : "UNLISTED",
      exchanges: listed ? exchanges : [],
      ticker_symbol: listed && ticker.trim() ? ticker.trim() : null,
      isin: listed && isin.trim() ? isin.trim() : null,
      is_sme: isSme,
    };
    try {
      onCreated(await api.createCompany(body));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not create the company.");
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      {error && <Banner tone="block" title="Could not create the company">{error}</Banner>}

      {/* Listed companies can be filled in from real data; a CIN cannot, so the
          registry search comes first. */}
      <Field label="Find a listed company"
             hint="Search by name, NSE symbol or ISIN. Verified data, NSE-listed companies only.">
        <div className="relative">
          <Input value={registryQuery} onChange={setRegistryQuery}
                 placeholder="Reliance, RELIANCE or INE002A01018" />
          {registryBusy && (
            <span className="absolute right-3 top-1/2 -translate-y-1/2 text-[11px] text-faint">
              searching…
            </span>
          )}
        </div>
        {registryHits.length > 0 && (
          <ul className="mt-2 divide-y divide-border overflow-hidden rounded-xl border border-border">
            {registryHits.map((c) => (
              <li key={c.isin || c.symbol}>
                <button type="button" onClick={() => applyRegistry(c)}
                        className="flex w-full items-center justify-between gap-3 px-3 py-2.5
                                   text-left hover:bg-surface-2">
                  <span className="min-w-0">
                    <span className="block truncate text-[13px] text-ink">{c.name}</span>
                    <span className="block font-mono text-[10px] text-faint">
                      {c.symbol} · {c.isin}
                      {c.face_value ? ` · face ₹${c.face_value}` : ""}
                    </span>
                  </span>
                  <span className="shrink-0 text-[11px] text-accent">Use</span>
                </button>
              </li>
            ))}
          </ul>
        )}
        {registrySearched && !registryBusy && registryHits.length === 0 && (
          <p className="mt-1.5 text-xs text-muted">
            No listed company matches that. Unlisted companies are not in any source that
            permits automated access — enter the details by hand below.
          </p>
        )}
      </Field>

      <Field label="CIN" error={cinError || (lookupStatus === "error" ? lookupError : null)}
             hint="Optional. A CIN cannot be resolved to a company name — MCA exposes no public lookup — but its structure is read for you.">
        <div className="flex gap-2">
          <Input value={cin} onChange={(v) => { setCin(v.toUpperCase()); setLookupStatus("idle"); setLookupError(null); }} placeholder="U27100MH2016PLC123456"
                 invalid={!!cinError || lookupStatus === "error"} />
          <Button type="button" variant="ghost" className="whitespace-nowrap text-xs"
                  onClick={() => fetchCinDetails()} disabled={!cin.trim() || lookupStatus === "loading"}>
            {lookupStatus === "loading" ? "Fetching…" : "Fetch details"}
          </Button>
        </div>

        {lookupStatus === "loading" && (
          <p className="mt-1.5 flex items-center gap-1 text-xs text-muted">
            <span className="animate-spin font-mono">⟳</span> Fetching company details…
          </p>
        )}

        {lookupStatus === "found" && (
          <p className="mt-1.5 text-xs font-medium text-pass">✓ Company details fetched</p>
        )}

        {lookupStatus === "existing" && existingCompany && (
          <div className="mt-2 rounded-xl border border-accent/30 bg-accent-dim/20 p-2.5 text-xs text-ink-2">
            <p className="font-semibold text-accent">✓ Company already exists on file</p>
            <p className="mt-0.5 text-muted">{existingCompany.name} (CIN: {cin})</p>
          </div>
        )}

        {lookupStatus === "not_found" && (
          <div className="mt-2 rounded-xl border border-warn/30 bg-warn-bg p-3 text-xs">
            <p className="font-semibold text-ink">No public registry resolves a CIN to a name</p>
            <p className="mt-1 leading-relaxed text-ink-2">
              MCA does not expose a lookup, so the company name has to be entered by hand.
              If the company is listed, search for it above by name or ISIN to fill in
              verified details instead.
            </p>
            {derived && (
              <>
                <p className="mt-2.5 text-[11px] uppercase tracking-[0.07em] text-muted">
                  Read from the CIN itself
                </p>
                <dl className="mt-1 grid grid-cols-2 gap-x-4 gap-y-1 text-[12px] text-ink-2">
                  {derived.incorporation_year != null && (
                    <><dt className="text-muted">Incorporated</dt>
                      <dd className="tnum">{derived.incorporation_year}</dd></>
                  )}
                  <dt className="text-muted">State</dt>
                  <dd>{derived.registered_office_hint ?? derived.state_code}</dd>
                  <dt className="text-muted">Class</dt>
                  <dd>{derived.company_type.toLowerCase()} ({derived.company_class_code})</dd>
                  <dt className="text-muted">CIN series</dt>
                  <dd>{derived.cin_series.toLowerCase()}</dd>
                </dl>
                <p className="mt-2 text-[11px] leading-relaxed text-faint">
                  A company that has since delisted keeps its original CIN series, so confirm
                  the listing status rather than relying on it.
                </p>
              </>
            )}
          </div>
        )}
      </Field>

      {/* Remaining Form Fields */}
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Company name" required error={nameError}>
          <Input value={name} onChange={setName} placeholder="Acme Industries Limited"
                 invalid={!!nameError} />
        </Field>
        <Field label="Company type" required>
          <Select value={companyType} onChange={setCompanyType} options={COMPANY_TYPES}
                  placeholder="Select a type" />
        </Field>
        <Field label="Date of incorporation">
          <Input type="date" value={incorporated} onChange={setIncorporated} />
        </Field>
        <Field label="Registered office">
          <Input value={office} onChange={setOffice} placeholder="City, State" />
        </Field>
      </div>

      <div className="rounded-xl border border-border bg-surface-2/40 p-4">
        <p className="mb-3 text-sm text-ink-2">Is the company listed?</p>
        <div className="flex gap-2">
          <Button variant={listed ? "primary" : "ghost"} onClick={() => setListed(true)}>Yes</Button>
          <Button variant={!listed ? "primary" : "ghost"}
                  onClick={() => { setListed(false); setExchanges([]); setTicker(""); setIsin(""); }}>
            No
          </Button>
        </div>

        {listed && (
          <div className="mt-4 space-y-4">
            <Field label="Stock exchange" required error={exchangeError}>
              <div className="flex flex-wrap gap-2">
                {EXCHANGES.map((x) => (
                  <Button key={x} variant={exchanges.includes(x) ? "primary" : "ghost"}
                          onClick={() => setExchanges(exchanges.includes(x)
                            ? exchanges.filter((e) => e !== x) : [...exchanges, x])}>
                    {x}
                  </Button>
                ))}
              </div>
            </Field>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Ticker / symbol">
                <Input value={ticker} onChange={setTicker} placeholder="ACME" />
              </Field>
              <Field label="ISIN" error={isinError}>
                <Input value={isin} onChange={setIsin} placeholder="INE123A01024"
                       invalid={!!isinError} />
              </Field>
            </div>
            <CheckboxField label="Listed on an SME platform" checked={isSme} onChange={setIsSme} />
          </div>
        )}
      </div>

      <p className="text-xs text-faint">
        Enter a CIN to automatically fetch and populate the company&apos;s details. You can review and edit the information before creating the company.
      </p>

      <div className="flex gap-2">
        <Button onClick={submit} disabled={!ready || busy}>
          {busy ? "Creating…" : submitLabel}
        </Button>
        {onCancel && <Button variant="ghost" onClick={onCancel}>Cancel</Button>}
      </div>
    </div>
  );
}
