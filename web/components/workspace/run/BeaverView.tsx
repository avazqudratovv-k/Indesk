import { useFormatter, useTranslations } from "next-intl";
import { getMockRunDetail } from "@/mocks";
import { useScrollable } from "@/lib/use-scrollable";
import type { Artifacts } from "@/lib/run/artifacts";
import ArtifactPane from "./ArtifactPane";
import styles from "./BeaverView.module.css";

// Board "Data": the pandas code Beaver wrote, then the table it produced. The code shows first, the table a few
// events later. The numbers under the code (rows, time, memory) are invented and sit under the Example stamp.
export default function BeaverView({ artifacts }: { artifacts: Artifacts }) {
  const t = useTranslations("workspace");
  const format = useFormatter();
  const { output, highlight } = getMockRunDetail().beaver;
  const { code, table } = artifacts.beaver;
  const { ref: codeRef, scrollable } = useScrollable<HTMLPreElement>();
  return (
    <div className={styles.view}>
      <ArtifactPane code className={styles.codePane}>
        <div className={styles.head}>
          <h3 className={styles.title}>{t("artifacts.beaver.codeTitle")}</h3>
          <span className={styles.sandbox}>{t("artifacts.beaver.sandbox")}</span>
        </div>
        {code ? (
          <>
            <pre ref={codeRef} className={styles.code} {...(scrollable ? { tabIndex: 0, role: "region", "aria-label": t("artifacts.beaver.codeScroll") } : {})}>
              {code.join("\n")}
            </pre>
            {table ? (
              <p className={styles.output}>
                <span>{t("artifacts.beaver.outRows", { count: output.rows })}</span>
                <span>{t("artifacts.beaver.outSeconds", { value: output.seconds })}</span>
                <span>{t("artifacts.beaver.outMemory", { value: output.mb })}</span>
                <span>{t("artifacts.beaver.outNetwork")}</span>
              </p>
            ) : null}
          </>
        ) : (
          <p className={styles.waiting}>{t("artifacts.states.waiting")}</p>
        )}
      </ArtifactPane>
      <ArtifactPane className={styles.tablePane}>
        <h3 className={styles.h3}>{t("artifacts.beaver.tableTitle")}</h3>
        {table ? (
          <>
            <div className={styles.cols} aria-hidden="true">
              <span className={styles.colStation}>{t("artifacts.beaver.colStation")}</span>
              <span className={styles.colNum}>2019</span>
              <span className={styles.colNum}>2025</span>
              <span className={styles.colGrowth}>{t("artifacts.beaver.colGrowth")}</span>
            </div>
            <ul className={styles.rows} aria-label={t("artifacts.beaver.tableTitle")}>
              {table.map((row, index) => (
                <li key={row.station} className={`${styles.row} ${index < highlight ? styles.top : ""}`}>
                  <span className={styles.station}>{row.station}</span>
                  <span className={styles.num}>
                    <span className={styles.yr}>2019 </span>
                    {row.a}
                  </span>
                  <span className={styles.num}>
                    <span className={styles.yr}>2025 </span>
                    {row.b}
                  </span>
                  <span className={styles.growth}>
                    <span className={styles.track} aria-hidden="true">
                      <span className={styles.fill} style={{ width: `${Math.round(row.growth * 5)}%` }} />
                    </span>
                    <span className={styles.pct}>
                      <span className={styles.srOnly}>{t("artifacts.beaver.colGrowth")}: </span>+{format.number(row.growth, { minimumFractionDigits: 1 })}%
                    </span>
                  </span>
                </li>
              ))}
            </ul>
            <p className={styles.unit}>{t("artifacts.beaver.unit")}</p>
          </>
        ) : (
          <p className={styles.waitingTable}>{t("artifacts.states.waiting")}</p>
        )}
      </ArtifactPane>
    </div>
  );
}
