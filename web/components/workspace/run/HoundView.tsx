import { useFormatter, useTranslations } from "next-intl";
import { getMockRunDetail } from "@/mocks";
import type { Artifacts, PassageRecord } from "@/lib/run/artifacts";
import ArtifactPane from "./ArtifactPane";
import StepList from "./StepList";
import styles from "./HoundView.module.css";

// Board "Retrieval": how Hound searched (the query and four steps) and the best three of the five passages it found.
// Passage text, file name and query are document content, so they are shown as the mock has them, untranslated.
export default function HoundView({ artifacts, finished }: { artifacts: Artifacts; finished: boolean }) {
  const t = useTranslations("workspace");
  const format = useFormatter();
  const { query, file, matched } = getMockRunDetail().hound;
  const { steps, passages, searching } = artifacts.hound;
  const items = steps.map((step) => ({ id: step.id, state: step.done ? ("done" as const) : finished ? ("notReached" as const) : ("todo" as const), text: t(`artifacts.hound.steps.${step.id}`) }));
  const score = (value: number) => format.number(value, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return (
    <div className={styles.view}>
      <ArtifactPane className={styles.how}>
        <h3 className={styles.h3}>{t("artifacts.hound.howTitle")}</h3>
        <p className={styles.query}>
          <span className={styles.srOnly}>{t("artifacts.hound.queryLabel")}: </span>“{query}”
        </p>
        <StepList items={items} />
      </ArtifactPane>
      <ArtifactPane className={styles.found}>
        <div className={styles.head}>
          <h3 className={styles.h3}>{t("artifacts.hound.matchesTitle")}</h3>
          {passages ? <span className={styles.count}>{t("artifacts.hound.topOf", { shown: passages.length, total: matched })}</span> : null}
        </div>
        {passages ? (
          <ul className={styles.list} aria-label={t("artifacts.hound.matchesTitle")}>
            {passages.map((passage: PassageRecord) => (
              <li key={passage.page} className={styles.card}>
                <div className={styles.meta}>
                  <span className={styles.file}>{t("artifacts.hound.pageOf", { file, page: passage.page })}</span>
                  <span className={`${styles.tag} ${passage.tag === "best" ? styles.best : ""}`}>{t(`artifacts.hound.tags.${passage.tag}`)}</span>
                </div>
                <p className={styles.text}>
                  {passage.pre}
                  <mark className={styles.hl}>{passage.hl}</mark>
                  {passage.post}
                </p>
                <div className={styles.bars}>
                  <Bar label={t("artifacts.hound.keywords")} value={passage.keyword} shown={score(passage.keyword)} color="keyword" />
                  <Bar label={t("artifacts.hound.meaning")} value={passage.meaning} shown={score(passage.meaning)} color="meaning" />
                  <Bar label={t("artifacts.hound.combined")} value={passage.combined} shown={score(passage.combined)} color="combined" strong />
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <p className={styles.waiting}>{searching ? t("artifacts.hound.searching") : t("artifacts.states.waiting")}</p>
        )}
      </ArtifactPane>
    </div>
  );
}

function Bar({ label, value, shown, color, strong = false }: { label: string; value: number; shown: string; color: "keyword" | "meaning" | "combined"; strong?: boolean }) {
  return (
    <div className={styles.bar}>
      <div className={`${styles.barHead} ${strong ? styles.strong : ""}`}>
        <span>{label}</span>
        <span className={styles.score}>{shown}</span>
      </div>
      <div className={styles.track} aria-hidden="true">
        <div className={`${styles.fill} ${styles[color]}`} style={{ width: `${Math.round(value * 100)}%` }} />
      </div>
    </div>
  );
}
