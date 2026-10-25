import { useTranslations } from "next-intl";
import { getMockRunDetail } from "@/mocks";
import { useScrollable } from "@/lib/use-scrollable";
import type { Artifacts } from "@/lib/run/artifacts";
import ArtifactPane from "./ArtifactPane";
import styles from "./ChameleonView.module.css";

// Board "Vision": the chart photo with what Chameleon detected drawn over it, and the rows it read. The photo is a
// static drawing (public/workspace/ridership-chart-photo.svg) and keeps its own colours; the outlines and value tags
// are drawn here, in the light token set because they sit on the fixed cream paper in both themes. The paper is
// tilted 2 degrees, so the overlay is tilted the same way and uses the board's paper-relative coordinates.
export default function ChameleonView({ artifacts }: { artifacts: Artifacts }) {
  const t = useTranslations("workspace");
  const { file, bars } = getMockRunDetail().chameleon;
  const shown = artifacts.chameleon;
  const { ref: scrollRef, scrollable } = useScrollable<HTMLDivElement>();
  // Row messages and arguments come from the mock, so they cannot be checked against the message types here.
  const message = t as unknown as (key: string, values?: Record<string, string | number>) => string;
  return (
    <div className={styles.view}>
      <ArtifactPane className={styles.photoPane}>
        <div className={styles.head}>
          <h3 className={styles.h3}>{t("artifacts.chameleon.photoTitle")}</h3>
          <span className={styles.file}>{file}</span>
        </div>
        <div ref={scrollRef} className={styles.scroll} {...(scrollable ? { tabIndex: 0, role: "region", "aria-label": t("artifacts.chameleon.photoScroll") } : {})}>
          <div className={styles.photo} role="img" aria-label={t("artifacts.chameleon.photoAria")}>
            {/* eslint-disable-next-line @next/next/no-img-element -- a static SVG drawing, nothing for next/image to optimise */}
            <img src="/workspace/ridership-chart-photo.svg" alt="" width={400} height={270} className={styles.drawing} />
            <div data-theme="light" className={styles.paper} aria-hidden="true">
              {shown.textBox ? <span className={styles.textBox} style={{ left: shown.textBox.left, top: shown.textBox.top, width: shown.textBox.width, height: shown.textBox.height }} /> : null}
              {bars.map((bar, index) => {
                const h = Math.round(bar.value * 8);
                const x = 32 + index * 38;
                const top = 204 - h;
                return (
                  <span key={bar.name}>
                    {shown.barBoxes ? <span className={styles.barBox} style={{ left: x - 4, top: top - 18, height: h + 18 }} /> : null}
                    {shown.valueTags ? (
                      <span className={styles.tagValue} style={{ left: x - 2, top: top - 17 }}>
                        {bar.value.toFixed(1)}
                      </span>
                    ) : null}
                  </span>
                );
              })}
            </div>
          </div>
        </div>
        <div className={styles.legend}>
          <span className={styles.legendItem}>
            <span className={`${styles.swatch} ${styles.swatchBar}`} aria-hidden="true" />
            {t("artifacts.chameleon.legendBar")}
          </span>
          <span className={styles.legendItem}>
            <span className={`${styles.swatch} ${styles.swatchText}`} aria-hidden="true" />
            {t("artifacts.chameleon.legendText")}
          </span>
        </div>
      </ArtifactPane>
      <ArtifactPane className={styles.readPane}>
        <h3 className={styles.h3}>{t("artifacts.chameleon.readTitle")}</h3>
        <p className={styles.note}>{t("artifacts.chameleon.note")}</p>
        {shown.rows.length === 0 ? (
          <p className={styles.note}>{t("artifacts.states.waiting")}</p>
        ) : (
          <ul className={styles.rows} aria-label={t("artifacts.chameleon.readTitle")}>
            {shown.rows.map((row) => (
              <li key={`${row.source}-${row.text ?? row.msg}-${row.args?.n ?? ""}`} className={styles.row}>
                <span className={`${styles.source} ${row.source === "ocr" ? styles.ocr : styles.vision}`}>{t(row.source === "ocr" ? "artifacts.chameleon.sourceOcr" : "artifacts.chameleon.sourceVision")}</span>
                <span className={styles.text}>{row.msg ? message(`artifacts.chameleon.rows.${row.msg}`, row.args) : row.text}</span>
                <span className={styles.conf}>
                  <span className={styles.srOnly}>{t("artifacts.chameleon.confidence")} </span>
                  {row.conf}
                </span>
              </li>
            ))}
          </ul>
        )}
      </ArtifactPane>
    </div>
  );
}
