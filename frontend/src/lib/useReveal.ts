"use client";
import { useEffect, useRef, useState } from "react";

const REDUCED = "(prefers-reduced-motion: reduce)";

/** Reveals `.reveal` descendants as they scroll into view.
 *
 * The hidden state lives behind `.reveal-armed`, which this hook adds only once
 * the observer actually exists. Content is therefore visible before hydration,
 * to a crawler, and if the script fails — the animation is additive, never a
 * precondition for reading the page. */
export function useReveal<T extends HTMLElement>() {
  const root = useRef<T | null>(null);

  useEffect(() => {
    const el = root.current;
    if (!el) return;
    // Honour the OS setting here too, not just in CSS: there is no reason to
    // run an observer for an effect that will not be shown.
    if (typeof window === "undefined" || !("IntersectionObserver" in window)
        || window.matchMedia?.(REDUCED).matches) {
      return;
    }

    el.classList.add("reveal-armed");
    const targets = Array.from(el.querySelectorAll<HTMLElement>(".reveal"));
    const io = new IntersectionObserver((entries) => {
      for (const e of entries) {
        if (e.isIntersecting) {
          e.target.classList.add("is-visible");
          io.unobserve(e.target);   // reveal once, not on every pass
        }
      }
    }, { rootMargin: "0px 0px -8% 0px", threshold: 0.08 });

    targets.forEach((t) => io.observe(t));
    return () => io.disconnect();
  }, []);

  return root;
}

/** Counts up to `value` once it is known. Returns the value unchanged when the
 *  viewer has asked for reduced motion, so the figure is still correct. */
export function useCountUp(value: number | null, ms = 1100) {
  const [n, setN] = useState(0);

  useEffect(() => {
    if (value == null) return;
    if (typeof window === "undefined" || window.matchMedia?.(REDUCED).matches) {
      setN(value); return;
    }
    let raf = 0;
    const start = performance.now();
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / ms);
      // easeOutCubic: fast first, settling on the real figure.
      setN(Math.round(value * (1 - Math.pow(1 - t, 3))));
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value, ms]);

  return value == null ? 0 : n;
}
