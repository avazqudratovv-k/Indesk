import { useTranslations } from "next-intl";
import Button from "@/components/ui/Button";
import styles from "./SignedOutCard.module.css";

// Visitors cannot upload or ask (SPEC section 3), so they see this card instead of the upload area.
export default function SignedOutCard() {
  const t = useTranslations("workspace");
  return (
    <section className={styles.card} aria-labelledby="ws-signedout-title">
      <h2 id="ws-signedout-title" className={styles.title}>
        {t("signedOut.title")}
      </h2>
      <p className={styles.body}>{t("signedOut.body")}</p>
      <div className={styles.actions}>
        <Button href="/login" variant="primary">
          {t("signedOut.login")}
        </Button>
        <Button href="/signup">{t("signedOut.signup")}</Button>
      </div>
    </section>
  );
}
