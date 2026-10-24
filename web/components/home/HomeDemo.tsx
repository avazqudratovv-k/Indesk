"use client";

import { useEffect, useState, useSyncExternalStore, type CSSProperties } from "react";
import { useTranslations } from "next-intl";
import AgentMark from "./AgentMark";
import { agentColor, agentIds, type AgentId } from "./agents";
import styles from "./HomeDemo.module.css";

// The numbers shown here (verified / total claims) are PLACEHOLDERS from the mock report rep_01 (web/mocks),
// passed in by the page. The question text is the mock run r_01 question, kept in the message files for i18n.
type Props = { verified: number; total: number };
type AgentStyle = CSSProperties & { "--agent": string };

const TICK_MS = 100;
const TYPE_TICKS = 18;
const STEP_TICKS = 13;
const FINAL_TICKS = 38;
// Agents light up in this order; Chameleon is not needed for a CSV question and stays dimmed.
const workOrder = ["owl", "beaver", "hound", "cat"] as const;
const FINAL_STEP = workOrder.length;
const END_TICK = TYPE_TICKS + workOrder.length * STEP_TICKS;
const LOOP_TICKS = END_TICK + FINAL_TICKS;

const reducedQuery = "(prefers-reduced-motion: reduce)";

function subscribeReduced(onChange: () => void) {
  const media = window.matchMedia(reducedQuery);
  media.addEventListener("change", onChange);
  return () => media.removeEventListener("change", onChange);
}

// Step -1 = typing, 0 to 3 = the agent in workOrder is working, 4 = final answer.
function stepAt(tick: number): number {
  if (tick < TYPE_TICKS) return -1;
  return Math.min(FINAL_STEP, Math.floor((tick - TYPE_TICKS) / STEP_TICKS));
}

type AgentPhase = "waiting" | "working" | "done" | "skipped";

function phaseOf(agent: AgentId, step: number): AgentPhase {
  const index = workOrder.findIndex((id) => id === agent);
  if (index === -1) return "skipped";
  if (step < index) return "waiting";
  return step === index ? "working" : "done";
}

export default function HomeDemo({ verified, total }: Props) {
  const t = useTranslations("home.demo");
  const tTeam = useTranslations("home.team");
  const [tick, setTick] = useState(0);
  const [playing, setPlaying] = useState(true);
  // Server and reduced-motion users get the static final frame.
  const reduced = useSyncExternalStore(
    subscribeReduced,
    () => window.matchMedia(reducedQuery).matches,
    () => true,
  );

  useEffect(() => {
    if (reduced || !playing) return;
    const timer = window.setInterval(() => setTick((value) => (value + 1) % LOOP_TICKS), TICK_MS);
    return () => window.clearInterval(timer);
  }, [reduced, playing]);

  const shown = reduced ? END_TICK : tick;
  const step = stepAt(shown);
  const question = t("question");
  const typed = step === -1 ? question.slice(0, Math.floor((question.length * shown) / TYPE_TICKS)) : question;

  return (
    <figure className={styles.figure} aria-label={t("label")}>
      <p className={styles.srOnly}>{t("description", { verified, total })}</p>
      {/* Everything below repeats the description, so screen readers skip it. */}
      <div className={`dk ${styles.panel}`} aria-hidden="true">
        <div className={styles.question}>
          <span className={styles.qLabel}>{t("questionLabel")}</span>
          <span className={styles.qBox}>
            {/* The sizer holds the full text so the box never changes height while typing. */}
            <span className={styles.qSizer}>{question}</span>
            <span className={styles.qTyped}>
              {typed}
              {step === -1 ? <i className={styles.caret} /> : null}
            </span>
          </span>
        </div>

        <ul className={styles.agents}>
          {agentIds.map((id) => {
            const phase = phaseOf(id, step);
            return (
              <li key={id} className={`${styles.agent} ${styles[phase]}`} style={{ "--agent": agentColor[id] } as AgentStyle}>
                <span className={styles.mark}>
                  <AgentMark agent={id} size={30} />
                </span>
                <span className={styles.name}>{tTeam(`${id}.name`)}</span>
                {/* All variants share one grid cell; only the current one shows, so the row height is fixed. */}
                <span className={styles.status}>
                  {id === "chameleon" ? (
                    <span className={styles.on}>{t("status.skipped")}</span>
                  ) : (
                    <>
                      <span className={phase === "waiting" ? styles.on : styles.off}>{t("status.waiting")}</span>
                      <span className={phase === "working" ? styles.on : styles.off}>{t(`working.${id as (typeof workOrder)[number]}`)}</span>
                      <span className={phase === "done" ? styles.on : styles.off}>{t("status.done")}</span>
                    </>
                  )}
                </span>
              </li>
            );
          })}
        </ul>

        <div className={styles.slot}>
        <div className={`${styles.paper} ${step === FINAL_STEP ? styles.paperOn : ""}`}>
          <div className={styles.paperHead}>
            <p className={styles.paperTitle}>{t("paper.title")}</p>
            <span className={styles.stamp}>{t("paper.stamp", { verified, total })}</span>
          </div>
          <p className={styles.flag}>
            <span className={styles.flagMark}>{t("paper.flaggedMark")}</span> {t("paper.flagged")}
          </p>
        </div>
        </div>
      </div>

      {/* Hidden while static, but it keeps its space so nothing moves when the page hydrates. */}
      <button type="button" className={styles.toggle} onClick={() => setPlaying((value) => !value)} aria-pressed={!playing} style={{ visibility: reduced ? "hidden" : "visible" }} tabIndex={reduced ? -1 : 0}>
        {playing ? t("pause") : t("play")}
      </button>
    </figure>
  );
}
