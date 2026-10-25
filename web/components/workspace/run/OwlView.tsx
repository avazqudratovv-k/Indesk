import { useTranslations } from "next-intl";
import type { Artifacts } from "@/lib/run/artifacts";
import ArtifactPane from "./ArtifactPane";
import StepList from "./StepList";
import styles from "./OwlView.module.css";

// Owl's work: its plan, and the question type it chose. The type is chosen by fixed rules, so no scores are shown.
export default function OwlView({ artifacts, finished }: { artifacts: Artifacts; finished: boolean }) {
  const t = useTranslations("workspace");
  const items = artifacts.plan.map((item) => ({ id: item.step, state: item.done ? ("done" as const) : finished ? ("notReached" as const) : ("todo" as const), text: t(`artifacts.owl.steps.${item.step}`, { count: artifacts.plannedClaims }) }));
  return (
    <div className={styles.view}>
      <ArtifactPane className={styles.plan}>
        <h3 className={styles.h3}>{t("artifacts.owl.planTitle")}</h3>
        <StepList items={items} />
      </ArtifactPane>
      <ArtifactPane className={styles.type}>
        <h3 className={styles.h3}>{t("artifacts.owl.typeTitle")}</h3>
        <p className={styles.note}>{t("artifacts.owl.typeNote")}</p>
        {artifacts.questionType ? (
          <p className={styles.chosen}>
            <span className={styles.chosenLabel}>{t("artifacts.owl.typeLabel")}</span>
            <b>{t(`artifacts.types.${artifacts.questionType}`)}</b>
          </p>
        ) : (
          <p className={styles.note}>{t("artifacts.states.waiting")}</p>
        )}
      </ArtifactPane>
    </div>
  );
}
