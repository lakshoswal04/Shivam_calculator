"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { session, type SessionUser } from "@/lib/api";

/** Public chrome. Kept separate from the authenticated shell in (app) so a
 *  signed-out visitor never loads the app's navigation, and so the landing
 *  page is not gated behind a session check. */
export default function MarketingLayout({ children }: { children: React.ReactNode }) {
  // Read on the client only: the server has no session, and rendering a
  // "Sign in" link that flips to "Dashboard" after hydration is the honest
  // trade for keeping this page static.
  const [user, setUser] = useState<SessionUser | null>(null);
  useEffect(() => { setUser(session.user); }, []);

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-20 border-b border-border bg-surface/90 backdrop-blur">
        <div className="mx-auto flex max-w-[1180px] items-center gap-4 px-5 py-3.5 sm:px-7">
          <Link href="/" className="flex items-center gap-2.5">
            <span className="grid h-8 w-8 place-items-center rounded-lg bg-accent text-sm
                             font-bold text-white">S</span>
            <span className="text-[15px] font-semibold tracking-tight">
              Securities<span className="text-muted"> Assessment</span>
            </span>
          </Link>
          <nav className="ml-auto flex items-center gap-2">
            <Link href="/calculator"
                  className="hidden rounded-lg px-3 py-1.5 text-sm text-muted
                             hover:text-ink sm:block">
              Calculator
            </Link>
            {user ? (
              <Link href="/dashboard"
                    className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white
                               hover:bg-accent-hi">
                Go to dashboard
              </Link>
            ) : (
              <>
                <Link href="/login"
                      className="rounded-lg px-3 py-1.5 text-sm text-ink-2 hover:text-accent">
                  Sign in
                </Link>
                <Link href="/signup"
                      className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white
                                 hover:bg-accent-hi">
                  Get started
                </Link>
              </>
            )}
          </nav>
        </div>
      </header>

      <div className="flex-1">{children}</div>

      <footer className="border-t border-border bg-surface">
        <div className="mx-auto max-w-[1180px] px-5 py-8 sm:px-7">
          <p className="max-w-3xl text-xs leading-relaxed text-faint">
            Generated from a legal rules database. Not legal advice; requires professional
            review. Capital capacity and legal issue capacity are reported separately and are
            not the same thing.
          </p>
        </div>
      </footer>
    </div>
  );
}
