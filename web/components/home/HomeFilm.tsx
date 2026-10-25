"use client";

import { useState, type CSSProperties, type ReactNode } from "react";
import { useTranslations } from "next-intl";
import { agentColor, agentIds } from "./agents";
import { film } from "./film-data";
import styles from "./HomeFilm.module.css";

const stepKeys = ["upload", "ask", "work", "check", "report"] as const;

// Wraps the film stage (a server-rendered child) with the pause control, step captions and trace log.
// The loop itself is pure CSS; this component only toggles animation-play-state through a class.
export default function HomeFilm({ stage, verified, total }: { stage: ReactNode; verified: number; total: number }) {
  const t = useTranslations("home.film");
  const [paused, setPaused] = useState(false);
  return (
    <figure className={`${styles.loop} ${paused ? styles.paused : ""}`} aria-label={t("label")}>
      <p className={styles.srOnly}>{t("description", { verified, total })}</p>
      {/* The picture repeats the description above, so screen readers skip it. */}
      <div aria-hidden="true">{stage}</div>
      <div className={styles.controls}>
        <button type="button" className={styles.pauseBtn} onClick={() => setPaused((value) => !value)} aria-label={paused ? t("play") : t("pause")}>
          {paused ? (
            <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <path d="M7 4.5v15l12-7.5z" />
            </svg>
          ) : (
            <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <rect x="5" y="4" width="5" height="16" />
              <rect x="14" y="4" width="5" height="16" />
            </svg>
          )}
        </button>
        <div className={styles.track} aria-hidden="true">
          <div className={styles.fprog} />
        </div>
        <span className={styles.fine}>{t("duration")}</span>
      </div>
      <ol className={styles.captions} aria-hidden="true">
        {stepKeys.map((key, i) => (
          <li key={key} className={styles[`fcap${i}`]}>
            <span>{String(i + 1).padStart(2, "0")}</span> {t(`steps.${key}`)}
          </li>
        ))}
      </ol>
      <div className={styles.trace} aria-hidden="true">
        <div className={styles.traceHead}>
          <span>{t("trace.head", { no: film.caseNo })}</span>
          <span>{t("trace.live")}</span>
        </div>
        <div className={styles.traceBody}>
          {film.trace.map((line, i) => {
            const id = agentIds[i];
            return (
              <div key={id} className={styles[`tl${i}`]} style={{ "--agent": agentColor[id] } as CSSProperties}>
                <i className={styles.led} />
                <span className={styles.traceTime}>{line.time}</span>
                <span className={styles.traceWho}>{t(`trace.${id}`)}</span>
                {line.detail ? line.detail : (
                  <>
                    <span style={{ color: "var(--green)" }}>✓ ✓</span> <span className={styles.bad}>✗ {t("trace.flagged")}</span>
                  </>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </figure>
  );
}
