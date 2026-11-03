"use client";
import { motion } from "framer-motion";
import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/workspace", label: "Workspace" },
  { href: "/performance", label: "Model performance" },
  { href: "/reports", label: "Reports" },
  { href: "/about", label: "Methodology" },
];

export function Nav() {
  const pathname = usePathname();
  return (
    <header className="sticky top-0 z-30 border-b border-line bg-ivory/90 backdrop-blur-sm">
      <nav className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-5 py-3">
        <Link href="/" className="flex items-center gap-2 font-display text-xl">
          <span className="inline-block h-5 w-5 rounded-full bg-mint ring-2 ring-coral" aria-hidden />
          Sylvan Watch
        </Link>
        <ul className="flex items-center gap-1 overflow-x-auto text-sm">
          {LINKS.map((l) => {
            const active = pathname.startsWith(l.href);
            return (
              <li key={l.href} className="relative">
                <Link href={l.href} className={`block whitespace-nowrap rounded-full px-3 py-1.5 transition-colors ${active ? "text-ink" : "text-muted hover:text-ink"}`}>
                  {l.label}
                </Link>
                {active && <motion.span layoutId="nav-pill" className="absolute inset-0 -z-10 rounded-full bg-butter" transition={{ type: "spring", stiffness: 380, damping: 30 }} />}
              </li>
            );
          })}
        </ul>
      </nav>
    </header>
  );
}
