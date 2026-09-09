"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { session, type SessionUser } from "@/lib/api";

const NAV = [
  { href: "/companies", label: "Companies" },
  { href: "/assess", label: "New assessment" },
  { href: "/assessments", label: "History" },
  { href: "/admin", label: "Legal review", roles: ["LEGAL_REVIEWER", "ADMINISTRATOR"] },
];

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const path = usePathname();
  const [user, setUser] = useState<SessionUser | null>(null);

  useEffect(() => {
    const u = session.user;
    if (!u) { router.replace("/login"); return; }
    setUser(u);
  }, [router]);

  if (!user) return <div className="p-10 text-sm text-muted">Loading…</div>;

  const nav = NAV.filter((n) => !n.roles || n.roles.includes(user.role));

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 border-b border-border bg-ground/95 backdrop-blur">
        <div className="mx-auto flex max-w-[1400px] items-center gap-6 px-6 py-3">
          <Link href="/companies" className="flex items-center gap-2">
            <span className="grid h-7 w-7 place-items-center rounded bg-accent text-xs font-bold text-white">S</span>
            <span className="hidden text-sm font-semibold tracking-tight sm:block">
              Securities Issue Assessment
            </span>
          </Link>
          <nav className="flex items-center gap-1">
            {nav.map((n) => {
              const active = path === n.href || path.startsWith(n.href + "/");
              return (
                <Link key={n.href} href={n.href}
                      className={`rounded-md px-3 py-1.5 text-sm transition-colors ${
                        active ? "bg-accent-dim/50 text-accent-hi"
                               : "text-muted hover:bg-surface-2 hover:text-ink-2"}`}>
                  {n.label}
                </Link>
              );
            })}
          </nav>
          <div className="ml-auto flex items-center gap-3">
            {user.is_demo_org && (
              <span className="hidden rounded border border-warn/30 bg-warn-bg px-2 py-0.5
                               font-mono text-[10px] uppercase tracking-wider text-warn md:inline">
                Demo data
              </span>
            )}
            <div className="hidden text-right sm:block">
              <div className="text-xs font-medium text-ink-2">{user.full_name}</div>
              <div className="font-mono text-[10px] text-faint">
                {user.role.replace("_", " ").toLowerCase()} · {user.org_name}
              </div>
            </div>
            <button onClick={() => { session.clear(); router.push("/login"); }}
                    className="rounded-md border border-border px-2.5 py-1.5 text-xs
                               text-muted hover:border-border-lit hover:text-ink-2">
              Sign out
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-[1400px] px-6 py-8">{children}</main>
      <footer className="mx-auto max-w-[1400px] px-6 pb-10">
        <p className="border-t border-border pt-4 text-xs leading-relaxed text-faint">
          Generated from a legal rules database. Not legal advice; requires professional review.
          Capital capacity and legal issue capacity are reported separately and are not the
          same thing.
        </p>
      </footer>
    </div>
  );
}
