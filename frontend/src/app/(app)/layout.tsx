"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { session, type SessionUser } from "@/lib/api";

const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: "▦" },
  { href: "/companies", label: "Companies", icon: "▤" },
  { href: "/assess", label: "New assessment", icon: "✚" },
  { href: "/assessments", label: "History", icon: "◷" },
  { href: "/calculator", label: "Calculator", icon: "∑" },
  { href: "/admin", label: "Legal review", icon: "✓",
    roles: ["LEGAL_REVIEWER", "ADMINISTRATOR"] },
];

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const path = usePathname();
  const [user, setUser] = useState<SessionUser | null>(null);

  // Always starts closed. The sidebar is a drawer you summon, not furniture:
  // it floats over the page rather than pushing it, so nothing on the page
  // moves when it opens, and it gets out of the way as soon as it is used.
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const u = session.user;
    if (!u) { router.replace("/login"); return; }
    setUser(u);
  }, [router]);

  // Closes on every navigation, at every width. Previously this only applied
  // below 1024px, so on a desktop the drawer stayed open over the page you had
  // just asked for.
  useEffect(() => { setOpen(false); }, [path]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  if (!user) return <div className="p-10 text-sm text-muted">Loading…</div>;

  const nav = NAV.filter((n) => !n.roles || n.roles.includes(user.role));
  const initials = (user.full_name || "?")
    .split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]).join("").toUpperCase();

  return (
    <div className="min-h-screen">
      {/* Backdrop at every width now: the drawer overlays the page everywhere,
          so clicking beside it must dismiss it everywhere. */}
      {open && (
        <button aria-label="Close navigation" onClick={() => setOpen(false)}
                className="fixed inset-0 z-30 bg-ink/25 backdrop-blur-sm" />
      )}

      {/* ------------------------------------------------------------ sidebar */}
      <aside
        id="app-nav"
        aria-hidden={!open}
        className={`fixed inset-y-0 left-0 z-40 w-[260px] border-r border-border bg-surface
                    transition-transform duration-200 ease-out
                    ${open ? "translate-x-0" : "-translate-x-full"}`}>
        <div className="flex h-full flex-col">
          <div className="flex items-center gap-2.5 px-5 py-4">
            <Link href="/dashboard" className="flex items-center gap-2.5">
              <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-accent
                               text-sm font-bold text-white">S</span>
              <span className="text-[15px] font-semibold tracking-tight">
                Securities<span className="text-muted"> Assessment</span>
              </span>
            </Link>
          </div>

          <nav className="flex-1 overflow-y-auto px-3 py-2">
            <ul className="space-y-1">
              {nav.map((n) => {
                const active = path === n.href || path.startsWith(n.href + "/");
                return (
                  <li key={n.href}>
                    <Link href={n.href} aria-current={active ? "page" : undefined}
                          className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-[13px]
                                      transition-colors ${
                            active ? "bg-accent-dim font-medium text-accent"
                                   : "text-muted hover:bg-surface-2 hover:text-ink-2"}`}>
                      <span aria-hidden className="w-4 text-center text-[13px]">{n.icon}</span>
                      {n.label}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </nav>

          <div className="border-t border-border p-3">
            <div className="flex items-center gap-2.5 rounded-lg px-2 py-2">
              <span aria-hidden
                    className="grid h-9 w-9 shrink-0 place-items-center rounded-full
                               bg-accent-dim text-[11px] font-semibold text-accent">
                {initials}
              </span>
              <div className="min-w-0 flex-1">
                <div className="truncate text-xs font-medium text-ink-2">{user.full_name}</div>
                <div className="truncate font-mono text-[10px] text-faint">
                  {user.role.replace("_", " ").toLowerCase()} · {user.org_name}
                </div>
              </div>
            </div>
            {user.is_demo_org && (
              <span className="mt-1 ml-2 inline-block rounded-full border border-warn/30
                               bg-warn-bg px-2.5 py-1 font-mono text-[10px] uppercase
                               tracking-wider text-warn">
                Demo data
              </span>
            )}
            <button onClick={() => { session.clear(); router.push("/login"); }}
                    className="mt-2 w-full rounded-lg border border-border px-3 py-2 text-xs
                               text-muted hover:border-border-lit hover:text-ink-2">
              Sign out
            </button>
          </div>
        </div>
      </aside>

      {/* -------------------------------------------------------- content ----
          The left margin tracks the sidebar so the two never overlap. Below lg
          there is no margin at all, because there the sidebar is an overlay. */}
      {/* No margin that tracks the sidebar any more. The drawer floats above
          the page, so opening it must not reflow anything underneath. */}
      <div>
        <header className="sticky top-0 z-20 border-b border-border bg-surface/90 backdrop-blur">
          <div className="flex items-center gap-3 px-4 py-3 sm:px-6">
            <button onClick={() => setOpen((v) => !v)}
                    aria-expanded={open} aria-controls="app-nav"
                    aria-label={open ? "Close navigation" : "Open navigation"}
                    className="grid h-9 w-9 shrink-0 place-items-center rounded-lg border
                               border-border text-muted hover:border-accent/50 hover:text-accent">
              {/* Three bars that fold into a cross when open. */}
              <span aria-hidden className="relative block h-3.5 w-4">
                <span className={`absolute left-0 block h-[1.5px] w-4 rounded bg-current
                                  transition-transform duration-200
                                  ${open ? "top-1.5 rotate-45" : "top-0"}`} />
                <span className={`absolute left-0 top-1.5 block h-[1.5px] w-4 rounded bg-current
                                  transition-opacity duration-200 ${open ? "opacity-0" : ""}`} />
                <span className={`absolute left-0 block h-[1.5px] w-4 rounded bg-current
                                  transition-transform duration-200
                                  ${open ? "top-1.5 -rotate-45" : "top-3"}`} />
              </span>
            </button>

            {/* The top bar is now the permanent home for the wordmark: the drawer
                is closed by default and floats above the page when open, so this
                must not appear and disappear as it is toggled. */}
            <Link href="/dashboard" className="flex items-center gap-2">
              <span className="grid h-7 w-7 place-items-center rounded-md bg-accent text-xs
                               font-bold text-white">S</span>
              <span className="hidden text-sm font-semibold tracking-tight sm:block">
                Securities<span className="text-muted"> Assessment</span>
              </span>
            </Link>
          </div>
        </header>

        <main className="mx-auto max-w-[1400px] px-4 py-7 sm:px-6">{children}</main>

        <footer className="mx-auto max-w-[1400px] px-4 pb-8 sm:px-6">
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
