"use client";
import { motion, useInView, useReducedMotion } from "framer-motion";
import { useRef, type ReactNode } from "react";

/**
 * Adapted from NullMotion "12-blur-reveal" (MIT): content starts blurred and dim, then a light
 * sweep passes over it while it sharpens. Re-implemented with Framer Motion; no GSAP dependency.
 */
export function BlurReveal({ children, className = "", delay = 0 }: { children: ReactNode; className?: string; delay?: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "-10% 0px" });
  const reduce = useReducedMotion();
  if (reduce) return <div className={className}>{children}</div>;
  return (
    <div ref={ref} className={`relative overflow-hidden ${className}`}>
      <motion.div
        initial={{ filter: "blur(14px)", opacity: 0.35, y: 24 }}
        animate={inView ? { filter: "blur(0px)", opacity: 1, y: 0 } : undefined}
        transition={{ duration: 0.9, delay, ease: [0.22, 1, 0.36, 1] }}
      >
        {children}
      </motion.div>
      <motion.span
        aria-hidden
        className="pointer-events-none absolute inset-y-0 -left-1/3 w-1/3 -skew-x-12 bg-gradient-to-r from-transparent via-white/70 to-transparent"
        initial={{ x: "0%" }}
        animate={inView ? { x: "420%" } : undefined}
        transition={{ duration: 1.1, delay: delay + 0.25, ease: "easeInOut" }}
      />
    </div>
  );
}
