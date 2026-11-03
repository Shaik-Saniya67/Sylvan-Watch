import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Nav } from "@/components/Nav";
import "./globals.css";

export const metadata: Metadata = {
  title: "Sylvan Watch · satellite forest-loss detection",
  description: "Detect and measure forest-cover loss from Sentinel-2 imagery with transparent validation.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen">
        <Nav />
        <main>{children}</main>
        <footer className="mt-24 border-t border-line px-5 py-8 text-center text-xs text-muted">
          Sentinel-2 (Copernicus) · Hansen Global Forest Change (UMD) · ESA WorldCover. Motion patterns adapted from NullMotion (MIT).
        </footer>
      </body>
    </html>
  );
}
