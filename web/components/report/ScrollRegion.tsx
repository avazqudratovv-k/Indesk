"use client";

import type { ReactNode } from "react";
import { useScrollable } from "@/lib/use-scrollable";

// A box that scrolls sideways. It is a keyboard tab stop only while there is something to scroll (DECISIONS #84).
export default function ScrollRegion({ label, className, children }: { label: string; className?: string; children: ReactNode }) {
  const { ref, scrollable } = useScrollable<HTMLDivElement>();
  return (
    <div ref={ref} className={className} tabIndex={scrollable ? 0 : undefined} role={scrollable ? "region" : undefined} aria-label={scrollable ? label : undefined}>
      {children}
    </div>
  );
}
