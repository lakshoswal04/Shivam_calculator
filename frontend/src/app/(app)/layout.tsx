"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { session, type SessionUser } from "@/lib/api";

const NAV = [
  { href: "/companies", label: "Companies" },
  { href: "/calculator", label: "Calculator" },
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
    // The whole app is one rounded panel floating on the backdrop painted by
    // body::before, as in the reference.
    <div className="mx-auto max-w-[1480px] p-3 sm:p-5 lg:p-7">
      <div className="rim overflow-hidden rounded-[var(--radius-panel)] border border-white/10
                      bg-ground shadow-[0_30px_80px_-20px_rgb(0_0_0/0.55)]">
        <header className="sticky top-0 z-20 bg-ground/85 backdrop-blur">
          <div className="flex flex-wrap items-center gap-x-5 gap-y-3 px-5 py-4 sm:px-7">
            <Link href="/companies" className="flex shrink-0 items-center gap-2.5">
              <span className="grid h-8 w-8 place-items-center rounded-xl bg-hero text-sm
                               font-bold text-black">S</span>
              <span className="hidden text-[15px] font-semibold tracking-tight lg:block">
                Securities<span className="text-muted"> Assessment</span>
              </span>
            </Link>

            {/* Centred pill group; the active item is a white pill. */}
            <nav className="order-last w-full overflow-x-auto md:order-none md:mx-auto md:w-auto">
              <div className="flex items-center gap-1 rounded-full bg-surface-2/70 p-1
                              ring-1 ring-border">
                {nav.map((n) => {
                  const active = path === n.href || path.startsWith(n.href + "/");
                  return (
                    <Link key={n.href} href={n.href}
                          aria-current={active ? "page" : undefined}
                          className={`whitespace-nowrap rounded-full px-3.5 py-1.5 text-[13px]
                                      transition-colors ${
                            active ? "bg-ink font-medium text-ground"
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
                    className="grid h-9 w-9 place-items-center rounded-full bg-surface-2
                               text-[11px] font-semibold text-ink-2 ring-1 ring-border">
                {initials}
              </span>
              <button onClick={() => { session.clear(); router.push("/login"); }}
                      className="rounded-full border border-border px-3.5 py-1.5 text-xs
                                 text-muted hover:border-border-lit hover:text-ink-2">
                Sign out
              </button>
            </div>
          </div>
        </header>

        <main className="px-5 pb-8 pt-2 sm:px-7">{children}</main>

        <footer className="px-5 pb-7 sm:px-7">
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
