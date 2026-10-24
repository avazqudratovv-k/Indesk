import styles from "./RoutePlaceholder.module.css";

// Temporary: shows the route name until each screen is built (ROADMAP section 2).
// Texts move to next-intl in ROADMAP 1.6.
export default function RoutePlaceholder({ route, param }: { route: string; param?: string }) {
  return (
    <main className={styles.main}>
      <p className={styles.eyebrow}>Route</p>
      <h1 className={styles.name}>{route}</h1>
      {param ? <p className={styles.param}>{param}</p> : null}
    </main>
  );
}
