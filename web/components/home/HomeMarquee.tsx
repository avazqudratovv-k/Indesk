import styles from "./HomeMarquee.module.css";

// Technical keywords, not prose, so they are not translated. Four copies make the -50% loop seamless.
const line = "CSV · pandas · sandbox · checks in code · cited claims · verified or not ·  ";

export default function HomeMarquee() {
  return (
    <div className={styles.wrap} aria-hidden="true">
      <div className={styles.track}>
        {[0, 1, 2, 3].map((i) => (
          <span key={i}>{line}</span>
        ))}
      </div>
    </div>
  );
}
