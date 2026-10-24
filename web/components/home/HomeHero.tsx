import { useTranslations } from "next-intl";
import Button from "@/components/ui/Button";
import Eyebrow from "@/components/ui/Eyebrow";
import HomeDemo from "./HomeDemo";
import { exampleHref, workspaceHref } from "./agents";
import styles from "./HomeHero.module.css";

export default function HomeHero({ verified, total }: { verified: number; total: number }) {
  const t = useTranslations("home.hero");
  return (
    <section className={styles.hero} aria-labelledby="hero-title">
      <div className={`dk ${styles.panel}`}>
        <div className={styles.copy}>
          <Eyebrow>{t("eyebrow")}</Eyebrow>
          <h1 id="hero-title" className={styles.title}>
            {t("title")}
          </h1>
          <p className={styles.lede}>{t("lede")}</p>
          <div className={styles.actions}>
            <Button href={exampleHref} variant="primary" size="lg">
              {t("tryExample")} <span aria-hidden="true">→</span>
            </Button>
            <Button href={workspaceHref} size="lg">
              {t("workspace")}
            </Button>
          </div>
        </div>
        <HomeDemo verified={verified} total={total} />
      </div>
    </section>
  );
}
