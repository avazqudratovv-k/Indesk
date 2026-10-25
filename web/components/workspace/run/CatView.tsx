import { useLocale, useTranslations } from "next-intl";
import type { Artifacts } from "@/lib/run/artifacts";
import ArtifactPane from "./ArtifactPane";
import styles from "./CatView.module.css";

// Cat's work: each claim with its verdict, the reason and the evidence it points to. An unsupported claim is shown,
// in the warning tint, never hidden. Evidence chips are plain labels (the report page opens them in 2.7).
export default function CatView({ artifacts }: { artifacts: Artifacts }) {
  const t = useTranslations("workspace");
  const locale = useLocale();
  // Reason keys and arguments come from the mock, so they cannot be checked against the message types here.
  const message = t as unknown as (key: string, values?: Record<string, string | number>) => string;
  return (
    <ArtifactPane>
      <p className={styles.note}>{t("artifacts.cat.note")}</p>
      {artifacts.claims.length === 0 ? (
        <p className={styles.note}>{t("artifacts.states.waiting")}</p>
      ) : (
        <ul className={styles.list} aria-label={t("artifacts.cat.listLabel")}>
          {artifacts.claims.map((claim) => {
            const bad = claim.status === "unsupported";
            return (
              <li key={claim.n} className={`${styles.row} ${bad ? styles.bad : ""}`}>
                <span className={styles.mark} aria-hidden="true">
                  {bad ? "!" : "✓"}
                </span>
                <span className={styles.text}>
                  <b className={styles.claim}>
                    <span className={styles.srOnly}>{t(bad ? "artifacts.cat.unsupported" : "artifacts.cat.ok")}: </span>
                    {locale === "ko" ? claim.text.ko : claim.text.en}
                  </b>
                  <span className={styles.reason}>{message(`artifacts.reasons.${claim.reason.msg}`, claim.reason.args)}</span>
                </span>
                {claim.evidence.length > 0 ? (
                  <ul className={styles.chips} aria-label={t("artifacts.cat.evidenceLabel")}>
                    {claim.evidence.map((code) => (
                      <li key={code} className={styles.chip}>
                        {code}
                      </li>
                    ))}
                  </ul>
                ) : null}
              </li>
            );
          })}
        </ul>
      )}
    </ArtifactPane>
  );
}
