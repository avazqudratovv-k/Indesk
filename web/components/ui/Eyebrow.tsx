import type { ReactNode } from "react";
import styles from "./Eyebrow.module.css";

export default function Eyebrow({ dot = true, children }: { dot?: boolean; children: ReactNode }) {
  return (
    <p className={styles.eyebrow}>
      {dot ? <i className={styles.dot} aria-hidden="true" /> : null}
      {children}
    </p>
  );
}
