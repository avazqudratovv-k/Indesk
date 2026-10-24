import styles from "./HomeOrbit.module.css";

// Home-only background: dotted rings with the five agent colours orbiting the page centre (board `.orbit`).
export default function HomeOrbit() {
  return (
    <svg className={styles.orbit} viewBox="0 0 780 780" fill="none" aria-hidden="true" focusable="false">
      <circle cx="390" cy="390" r="290" stroke="var(--rule2)" strokeDasharray="2 9" />
      <circle cx="390" cy="390" r="345" stroke="var(--rule)" />
      <circle cx="390" cy="390" r="385" stroke="var(--rule2)" strokeDasharray="2 11" />
      <g className={`${styles.o} ${styles.o1}`}>
        <circle cx="680" cy="390" r="5" fill="var(--c-owl)" />
        <circle cx="100" cy="390" r="5" fill="var(--c-cham)" />
      </g>
      <g className={`${styles.o} ${styles.o2}`}>
        <circle cx="390" cy="45" r="5" fill="var(--c-hou)" />
        <circle cx="390" cy="735" r="5" fill="var(--c-bea)" />
      </g>
      <g className={`${styles.o} ${styles.o3}`}>
        <circle cx="662" cy="118" r="5" fill="var(--c-cat)" />
      </g>
    </svg>
  );
}
