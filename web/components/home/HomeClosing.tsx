import { useTranslations } from "next-intl";
import Button from "@/components/ui/Button";
import DemoNotice from "@/components/ui/DemoNotice";
import { exampleHref } from "./agents";
import styles from "./HomeClosing.module.css";

export default function HomeClosing() {
  const t = useTranslations("home.closing");
  return (
    <section className={styles.wrap} aria-labelledby="closing-title">
      <div className={`dk ${styles.band}`}>
        <div className={styles.text}>
          <h2 id="closing-title" className={styles.title}>
            {t("title")}
          </h2>
          <p className={styles.body}>{t("body")}</p>
          <DemoNotice />
        </div>
        <Button href={exampleHref} variant="primary" size="lg">
          {t("tryExample")} <span aria-hidden="true">→</span>
        </Button>
      </div>
    </section>
  );
}
