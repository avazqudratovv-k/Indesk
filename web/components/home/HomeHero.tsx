import { useTranslations } from "next-intl";
import Button from "@/components/ui/Button";
import Eyebrow from "@/components/ui/Eyebrow";
import FilmStage from "./FilmStage";
import HideWhenSignedIn from "./HideWhenSignedIn";
import HomeFilm from "./HomeFilm";
import HomeOrbit from "./HomeOrbit";
import { workspaceHref } from "./agents";
import styles from "./HomeHero.module.css";

// Hero panel from the board: dark photo panel, copy on the left, demo film on the right (stacked on phones).
export default function HomeHero() {
  const t = useTranslations("home.hero");
  return (
    <div className={styles.wrap}>
      <div className={`dk ${styles.panel}`}>
        <div className={styles.grain} />
        <section className={styles.hero} aria-labelledby="hero-title">
          <div className={styles.copy}>
            <Eyebrow>{t("eyebrow")}</Eyebrow>
            <h1 id="hero-title" className={styles.title}>
              {t("title")}
            </h1>
            <svg className={styles.squiggle} width="260" height="16" viewBox="0 0 260 16" fill="none" aria-hidden="true">
              <path d="M3 11C34 2 70 15 108 7S188 3 257 10" stroke="var(--accent)" strokeWidth="3" strokeLinecap="round" />
            </svg>
            <p className={styles.lede}>{t("lede")}</p>
            <div className={styles.actions}>
              <Button href={workspaceHref} variant="primary" size="lg">
                {t("tryDemo")}
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M5 12h14M13 6l6 6-6 6" />
                </svg>
              </Button>
              <HideWhenSignedIn>
                <Button href="/signup" size="lg">
                  {t("signUp")}
                </Button>
              </HideWhenSignedIn>
            </div>
            <HideWhenSignedIn>
              <p className={styles.note}>{t("note")}</p>
            </HideWhenSignedIn>
          </div>
          <div className={styles.stage}>
            <HomeOrbit />
            <HomeFilm stage={<FilmStage />} />
          </div>
        </section>
      </div>
    </div>
  );
}
