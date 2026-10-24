import type { ReactNode } from "react";
import styles from "./HomeSection.module.css";

export default function HomeSection({ id, title, sub, children }: { id: string; title: string; sub?: string; children: ReactNode }) {
  return (
    <section className={styles.section} aria-labelledby={`${id}-title`}>
      <h2 id={`${id}-title`} className={styles.title}>
        {title}
      </h2>
      {sub ? <p className={styles.sub}>{sub}</p> : null}
      {children}
    </section>
  );
}
