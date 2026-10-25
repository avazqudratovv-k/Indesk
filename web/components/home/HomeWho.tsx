import { useTranslations } from "next-intl";
import HomeSection from "./HomeSection";
import styles from "./HomeWho.module.css";

const items = ["publish", "paper", "weekly", "board"] as const;

// Example use cases only: the demo has no customers, so nothing here says that anyone already uses it.
export default function HomeWho() {
  const t = useTranslations("home.who");
  return (
    <HomeSection id="who" title={t("title")}>
      <ul className={styles.grid}>
        {items.map((key) => (
          <li key={key} className={styles.item}>
            <h3 className={styles.name}>{t(`items.${key}.title`)}</h3>
            <p className={styles.text}>{t(`items.${key}.text`)}</p>
          </li>
        ))}
      </ul>
    </HomeSection>
  );
}
