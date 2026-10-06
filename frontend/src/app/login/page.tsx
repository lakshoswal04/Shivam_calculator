"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api, session } from "@/lib/api";
import { Button, Field, inputCls } from "@/components/ui";

const DEMO = [
  { email: "cs@demo.test", role: "Company Secretary" },
  { email: "cfo@demo.test", role: "Finance" },
  { email: "legal@demo.test", role: "Legal Reviewer" },
  { email: "owner@demo.test", role: "Administrator" },
];

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("cs@demo.test");
  const [password, setPassword] = useState("demo1234");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setError(null);
    try {
      const r = await api.login(email, password);
      session.save(r.access_token, r.refresh_token, r.user);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign in failed.");
    } finally { setBusy(false); }
  }

  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-10">
      {/* Same floating panel as the app shell, so signing in does not look like
          a different product from the thing behind it. */}
      <div className="rim-lg w-full max-w-md rounded-[var(--radius-panel)] border border-border
                      bg-surface p-7 sm:p-9">
        <div className="mb-8">
          <div className="mb-3 flex items-center gap-2.5">
            <span className="grid h-9 w-9 place-items-center rounded-lg bg-accent text-sm font-bold text-white">S</span>
            <span className="font-mono text-[11px] uppercase tracking-[0.14em] text-muted">
              Securities Issue Platform
            </span>
          </div>
          <h1 className="text-3xl font-semibold tracking-tight">Sign in</h1>
          <p className="mt-1 text-sm text-muted">
            Assess a proposed issue against the legal rules database.
          </p>
        </div>

        <form onSubmit={submit} className="space-y-4">
          <Field label="Email">
            <input className={inputCls} type="email" value={email} autoComplete="username"
                   onChange={(e) => setEmail(e.target.value)} required />
          </Field>
          <Field label="Password">
            <input className={inputCls} type="password" value={password} autoComplete="current-password"
                   onChange={(e) => setPassword(e.target.value)} required />
          </Field>
          {error && (
            <p className="rounded-xl border border-block/30 bg-block-bg px-3.5 py-2.5 text-sm text-block">
              {error}
            </p>
          )}
          <Button type="submit" disabled={busy} className="w-full">
            {busy ? "Signing in…" : "Sign in"}
          </Button>
        </form>

        <p className="mt-6 text-center text-sm text-muted">
          No account yet?{" "}
          <Link href="/signup" className="text-accent hover:underline">Create one</Link>
        </p>

        <div className="mt-8 rim rounded-[var(--radius-card)] border border-border bg-surface-2 p-4">
          <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.09em] text-muted">
            Demonstration accounts
          </p>
          <div className="space-y-1">
            {DEMO.map((d) => (
              <button key={d.email} onClick={() => { setEmail(d.email); setPassword("demo1234"); }}
                      className="flex w-full items-center justify-between rounded px-2 py-1
                                 text-left text-xs hover:bg-surface-2">
                <span className="font-mono text-ink-2">{d.email}</span>
                <span className="text-faint">{d.role}</span>
              </button>
            ))}
          </div>
          <p className="mt-3 text-[11px] leading-relaxed text-faint">
            Password <span className="font-mono">demo1234</span>. Rules in this environment were
            approved by a demonstration reviewer, not by a qualified legal reviewer.
          </p>
        </div>
      </div>
    </main>
  );
}
