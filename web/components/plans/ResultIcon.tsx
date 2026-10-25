import styles from "./Checkout.module.css";

// Animated badge for the checkout result: the shapes and timings follow the Moments board (payment received, card declined).
export default function ResultIcon({ kind }: { kind: "success" | "declined" }) {
  const ok = kind === "success";
  return (
    <svg className={styles.icon} width="96" height="96" viewBox="0 0 96 96" fill="none" aria-hidden="true" focusable="false">
      {ok ? <circle className={styles.ring} cx="48" cy="48" r="36" stroke="var(--ok)" strokeWidth="3" /> : null}
      <circle className={styles.badge} cx="48" cy="48" r="36" fill={ok ? "var(--ok)" : "var(--bad)"} />
      {ok ? (
        <path className={styles.draw} pathLength={1} d="M32 49 L43 60 L65 36" stroke="#fff" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" />
      ) : (
        <>
          <path className={`${styles.draw} ${styles.drawX1}`} pathLength={1} d="M35 35 L61 61" stroke="#fff" strokeWidth="5" strokeLinecap="round" />
          <path className={`${styles.draw} ${styles.drawX2}`} pathLength={1} d="M61 35 L35 61" stroke="#fff" strokeWidth="5" strokeLinecap="round" />
        </>
      )}
    </svg>
  );
}
