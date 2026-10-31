import { useTranslations } from "next-intl";
import DemoNotice from "@/components/ui/DemoNotice";
import styles from "./Footer.module.css";

export default function Footer() {
  const t = useTranslations("footer");
  return (
    <footer data-print="hide" className={styles.foot}>
      <DemoNotice />
      <p className={styles.tagline}>{t("tagline")}</p>
    </footer>
  );
}
