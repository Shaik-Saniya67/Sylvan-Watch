"use client";
import { motion, useReducedMotion } from "framer-motion";

/**
 * Adapted from NullMotion "22-kinetic-headline" (MIT): two word groups slide in from opposite sides
 * with blur, a pill squashes and springs into place between them, and a sheen sweeps across it.
 */
export function KineticHeadline({ left, pill, right }: { left: string; pill: string; right: string }) {
  const reduce = useReducedMotion();
  const word = (dir: 1 | -1, delay: number) => ({
    initial: reduce ? false : { x: 80 * dir, y: 14 * dir, opacity: 0, filter: "blur(8px)" },
    animate: { x: 0, y: 0, opacity: 1, filter: "blur(0px)" },
    transition: { duration: 0.75, delay, ease: [0.16, 1, 0.3, 1] as const },
  });
  return (
    <h1 className="font-display text-5xl leading-[1.05] tracking-tight sm:text-7xl">
      <motion.span className="inline-block" {...word(-1, 0.1)}>{left}</motion.span>{" "}
      <motion.span
        className="relative mx-1 inline-block overflow-hidden rounded-full bg-mint px-5 align-middle text-ink"
        initial={reduce ? false : { scaleX: 0.9, scaleY: 1.08, opacity: 0, y: 12 }}
        animate={{ scaleX: 1, scaleY: 1, opacity: 1, y: 0 }}
        transition={{ type: "spring", stiffness: 260, damping: 14, delay: 0.45 }}
      >
        {pill}
        <motion.span
          aria-hidden
          className="absolute inset-y-0 -left-1/2 w-1/3 -skew-x-12 bg-white/70"
          initial={{ x: "0%" }} animate={{ x: "480%" }} transition={{ duration: 0.9, delay: 1.2, ease: "easeInOut" }}
        />
      </motion.span>{" "}
      <motion.span className="inline-block" {...word(1, 0.2)}>{right}</motion.span>
    </h1>
  );
}
