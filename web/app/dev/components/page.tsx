import { useTranslations } from "next-intl";
import Gallery from "./Gallery";
import styles from "./page.module.css";

// Dev-only gallery for ROADMAP 1.4. Hidden in production by app/dev/layout.tsx.
export default function ComponentsPage() {
  const d = useTranslations("dev.components");
  return (
    <main className={styles.page}>
      <h1 className={styles.h1}>{d("title")}</h1>
      <p className={styles.lede}>{d("lede")}</p>
      <div className={styles.panels}>
        <Gallery title={`${d("themes")} · ${d("light")}`} theme="light" />
        <Gallery title={`${d("themes")} · ${d("dark")}`} theme="dark" />
      </div>
    </main>
  );
}
