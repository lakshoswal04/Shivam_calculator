"use client";
import { useState } from "react";
import { api, ApiError, type CompanyCreateBody } from "@/lib/api";
import { Banner, Button, CheckboxField, Field, Input, Select } from "@/components/ui";

const COMPANY_TYPES = [
  { value: "PRIVATE", label: "Private company" },
  { value: "PUBLIC", label: "Public company" },
  { value: "SECTION_8", label: "Section 8 company" },
  { value: "NIDHI", label: "Nidhi company" },
  { value: "GOVERNMENT", label: "Government company" },
];
const EXCHANGES = ["NSE", "BSE", "MSEI"];

// Mirrors company.companies.cin_shape and the backend pattern, so the user is
// told before submitting rather than after.
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
  const [name, setName] = useState("");
  const [cin, setCin] = useState("");
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

      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Company name" required error={nameError}>
          <Input value={name} onChange={setName} placeholder="Acme Industries Limited"
                 invalid={!!nameError} />
        </Field>
        <Field label="CIN" error={cinError}
               hint="Optional. Leave it blank to model a company that is not registered yet.">
          <Input value={cin} onChange={setCin} placeholder="U27100MH2016PLC123456"
                 invalid={!!cinError} />
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

      <div className="rounded-md border border-border bg-surface-2/40 p-4">
        <p className="mb-3 text-sm text-ink-2">Is the company listed?</p>
        <div className="flex gap-2">
          <Button variant={listed ? "primary" : "ghost"} onClick={() => setListed(true)}>Yes</Button>
          <Button variant={!listed ? "primary" : "ghost"}
                  onClick={() => { setListed(false); setExchanges([]); setTicker(""); setIsin(""); }}>
            No
          </Button>
        </div>

        {/* Exchange, ticker and ISIN are only meaningful while listed, and the
            database refuses them on an unlisted company, so they are hidden
            rather than merely ignored. */}
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
        A CIN is checked for its format only. Nothing here is verified against the
        MCA register, and a company you add is your own record.
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
