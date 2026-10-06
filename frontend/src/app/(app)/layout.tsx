"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { session, type SessionUser } from "@/lib/api";

const NAV = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/companies", label: "Companies" },
  { href: "/assess", label: "New assessment" },
  { href: "/assessments", label: "History" },
  { href: "/legal", label: "Legal library" },
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

  const initials = (user.full_name || "?")
    .split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]).join("").toUpperCase();

  return (
    // A compliance tool reads better as a full-width application than as a
    // floating panel, so the chrome is a plain bar over a tinted page.
    <div className="min-h-screen">
      <div>
        <header className="sticky top-0 z-20 border-b border-border bg-surface/90 backdrop-blur">
          <div className="mx-auto flex max-w-[1400px] flex-wrap items-center gap-x-5 gap-y-3 px-5 py-3 sm:px-7">
            <Link href="/dashboard" className="flex shrink-0 items-center gap-2.5">
              <span className="grid h-8 w-8 place-items-center rounded-lg bg-accent text-sm
                               font-bold text-white">S</span>
              <span className="hidden text-[15px] font-semibold tracking-tight lg:block">
                Securities<span className="text-muted"> Assessment</span>
              </span>
            </Link>

            {/* Centred pill group; the active item is a white pill. */}
            <nav className="order-last w-full overflow-x-auto md:order-none md:mx-auto md:w-auto">
              <div className="flex items-center gap-1 rounded-lg bg-surface-2 p-1">
                {nav.map((n) => {
                  const active = path === n.href || path.startsWith(n.href + "/");
                  return (
                    <Link key={n.href} href={n.href}
                          aria-current={active ? "page" : undefined}
                          className={`whitespace-nowrap rounded-md px-3.5 py-1.5 text-[13px]
                                      transition-colors ${
                            active ? "bg-surface font-medium text-accent shadow-sm"
                                   : "text-muted hover:text-ink-2"}`}>
                      {n.label}
                    </Link>
                  );
                })}
              </div>
            </nav>

            <div className="ml-auto flex shrink-0 items-center gap-2.5">
              {user.is_demo_org && (
                <span className="hidden rounded-full border border-warn/30 bg-warn-bg px-2.5 py-1
                                 font-mono text-[10px] uppercase tracking-wider text-warn md:inline">
                  Demo data
                </span>
              )}
              <div className="hidden text-right lg:block">
                <div className="text-xs font-medium text-ink-2">{user.full_name}</div>
                <div className="font-mono text-[10px] text-faint">
                  {user.role.replace("_", " ").toLowerCase()} · {user.org_name}
                </div>
              </div>
              <span aria-hidden
                    className="grid h-9 w-9 place-items-center rounded-full bg-accent-dim
                               text-[11px] font-semibold text-accent">
                {initials}
              </span>
              <button onClick={() => { session.clear(); router.push("/login"); }}
                      className="rounded-lg border border-border px-3.5 py-1.5 text-xs
                                 text-muted hover:border-border-lit hover:text-ink-2">
                Sign out
              </button>
            </div>
          </div>
        </header>

        <main className="mx-auto max-w-[1400px] px-5 py-7 sm:px-7">{children}</main>

        <footer className="mx-auto max-w-[1400px] px-5 pb-8 sm:px-7">
          <p className="border-t border-border pt-4 text-xs leading-relaxed text-faint">
            Generated from a legal rules database. Not legal advice; requires professional review.
            Capital capacity and legal issue capacity are reported separately and are not the
            same thing.
          </p>
        </footer>
      </div>
    </div>
  );
}
