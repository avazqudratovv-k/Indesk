import styles from "./PageBackground.module.css";

// Page-wide background from the design boards (same on every screen): contour art, fine noise, top fade.
// Sits behind the whole shell and never takes clicks.
export default function PageBackground() {
  return (
    <div className={styles.bg} data-print="hide" aria-hidden="true">
      <i className={styles.art} />
      <i className={styles.noise} />
    </div>
  );
}
