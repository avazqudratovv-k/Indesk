"use client";

import { useEffect, useRef, useState, type CSSProperties } from "react";
import styles from "./HomeTeam.module.css";

type Vars = CSSProperties & { "--agent": string; "--plate"?: string };

// Board "plate": cream card with the animal as a dark silhouette (the webp is an alpha mask) and a "Plate I" label.
// The mask image is only requested when the card is near the viewport, so it is not part of first paint.
export default function PlateMark({ agent, color, label }: { agent: string; color: string; label: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [near, setNear] = useState(false);
  useEffect(() => {
    const node = ref.current;
    if (!node || near) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setNear(true);
          observer.disconnect();
        }
      },
      { rootMargin: "400px" },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [near]);
  const vars: Vars = { "--agent": color };
  if (near) vars["--plate"] = `url(/home/plate-${agent}.webp)`;
  return (
    <div ref={ref} className={styles.plate} style={vars} aria-hidden="true">
      <div className={styles.silhouette} />
      <div className={styles.plateLabel}>
        <span className={styles.plateDot} />
        {label}
      </div>
    </div>
  );
}
