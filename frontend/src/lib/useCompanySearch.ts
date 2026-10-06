"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, type Company } from "@/lib/api";

/** Debounced, abortable company search with append-style paging.
 *
 * Extracted from CompanySearch so the wizard's selector and the companies list
 * share one implementation — the abort-the-previous-request rule below is the
 * kind of thing that only gets fixed in one copy otherwise. */
export function useCompanySearch(pageSize: number) {
  const [query, setQuery] = useState("");
  const [rows, setRows] = useState<Company[]>([]);
  const [total, setTotal] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inFlight = useRef<AbortController | null>(null);

  const load = useCallback(async (q: string, offset: number) => {
    // Cancel the previous request so a slow earlier response cannot land after
    // a newer one and overwrite the list the user is looking at.
    inFlight.current?.abort();
    const ctl = new AbortController();
    inFlight.current = ctl;
    setBusy(true); setError(null);
    try {
      const r = await api.searchCompanies(q, { limit: pageSize, offset, signal: ctl.signal });
      setRows((prev) => (offset === 0 ? r.companies : [...prev, ...r.companies]));
      setTotal(r.total);
    } catch (e) {
      if ((e as Error).name === "AbortError") return;
      setError(e instanceof Error ? e.message : "Could not load companies.");
    } finally {
      if (inFlight.current === ctl) setBusy(false);
    }
  }, [pageSize]);

  useEffect(() => {
    const t = setTimeout(() => { void load(query, 0); }, 250);
    return () => clearTimeout(t);
  }, [query, load]);

  return {
    query, setQuery, rows, total, busy, error,
    hasMore: rows.length < total,
    loadMore: () => void load(query, rows.length),
    reload: () => void load(query, 0),
  };
}
