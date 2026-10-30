import { useTranslations } from "next-intl";
import styles from "./UploadInfo.module.css";

// Board block "What you can upload": what works and what does not. The board's "Pasted text" chip is left out (no paste input yet).
export default function UploadInfo() {
  const t = useTranslations("workspace");
  const ok = t.raw("info.okItems") as string[];
  const no = t.raw("info.noItems") as string[];
  const later = t.raw("info.laterItems") as string[];
  return (
    <section className={styles.sec} aria-labelledby="ws-info-title">
      <div>
        <h2 id="ws-info-title" className={styles.title}>
          {t("info.title")}
        </h2>
        <p className={styles.sub}>{t("info.note")}</p>
      </div>
      <div className={styles.grid}>
        <div className={styles.box}>
          <div className={`${styles.label} ${styles.okLabel}`}>{t("info.ok")}</div>
          <ul className={styles.pills}>
            {ok.map((item) => (
              <li key={item} className={`${styles.pill} ${styles.okPill}`}>
                {item}
              </li>
            ))}
          </ul>
        </div>
        <div className={styles.box}>
          <div className={`${styles.label} ${styles.noLabel}`}>{t("info.no")}</div>
          <ul className={styles.pills}>
            {no.map((item) => (
              <li key={item} className={`${styles.pill} ${styles.noPill}`}>
                {item}
              </li>
            ))}
          </ul>
        </div>
        <div className={`${styles.box} ${styles.wide}`}>
          <div className={`${styles.label} ${styles.laterLabel}`}>{t("info.later")}</div>
          <ul className={styles.pills}>
            {later.map((item) => (
              <li key={item} className={`${styles.pill} ${styles.laterPill}`}>
                {item}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}
