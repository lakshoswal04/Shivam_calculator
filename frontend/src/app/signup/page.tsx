"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api, session } from "@/lib/api";
import { Button, Field, inputCls } from "@/components/ui";

const MIN_PASSWORD = 8;

export default function SignUpPage() {
  const router = useRouter();
  const [fullName, setFullName] = useState("");
  const [orgName, setOrgName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const tooShort = password.length > 0 && password.length < MIN_PASSWORD;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (password.length < MIN_PASSWORD) {
      setError(`Choose a password of at least ${MIN_PASSWORD} characters.`);
      return;
    }
    setBusy(true); setError(null);
    try {
      const r = await api.register({
        email, password, full_name: fullName, org_name: orgName,
      });
      session.save(r.access_token, r.refresh_token, r.user);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create the account.");
    } finally { setBusy(false); }
  }

  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-10">
      <div className="rim-lg w-full max-w-md rounded-[var(--radius-panel)] border border-border
                      bg-surface p-7 sm:p-9">
        <div className="mb-8">
          <div className="mb-3 flex items-center gap-2.5">
            <span className="grid h-9 w-9 place-items-center rounded-lg bg-accent text-sm
                             font-bold text-white">S</span>
            <span className="font-mono text-[11px] uppercase tracking-[0.14em] text-muted">
              Securities Issue Platform
            </span>
          </div>
          <h1 className="text-3xl font-semibold tracking-tight">Create an account</h1>
          <p className="mt-1 text-sm text-muted">
            Your organisation is created with you as its administrator. Nothing is shared
            with any other organisation.
          </p>
        </div>

        <form onSubmit={submit} className="space-y-4">
          <Field label="Your name" required>
            <input className={inputCls} value={fullName} autoComplete="name"
                   onChange={(e) => setFullName(e.target.value)} required />
          </Field>
          <Field label="Organisation" required
                 hint="Your firm or company. This names the workspace your data lives in.">
            <input className={inputCls} value={orgName} autoComplete="organization"
                   onChange={(e) => setOrgName(e.target.value)} required />
          </Field>
          <Field label="Work email" required>
            <input className={inputCls} type="email" value={email} autoComplete="username"
                   onChange={(e) => setEmail(e.target.value)} required />
          </Field>
          <Field label="Password" required
                 hint={`At least ${MIN_PASSWORD} characters.`}
                 error={tooShort ? `At least ${MIN_PASSWORD} characters.` : null}>
            <input className={inputCls} type="password" value={password}
                   autoComplete="new-password" minLength={MIN_PASSWORD}
                   onChange={(e) => setPassword(e.target.value)} required />
          </Field>

          {error && (
            <p className="rounded-xl border border-block/30 bg-block-bg px-3.5 py-2.5 text-sm text-block">
              {error}
            </p>
          )}

          <Button type="submit" disabled={busy} className="w-full">
            {busy ? "Creating your account…" : "Create account"}
          </Button>
        </form>

        <p className="mt-6 text-center text-sm text-muted">
          Already have an account?{" "}
          <Link href="/login" className="text-accent hover:underline">Sign in</Link>
        </p>
      </div>
    </main>
  );
}
