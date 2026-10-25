import type { CSSProperties } from "react";
import { useTranslations } from "next-intl";
import { useScrollable } from "@/lib/use-scrollable";
import { agentColor } from "@/components/home/agents";
import { deriveFlow, owlBubble, type AgentView, type RunAgent, type RunEvent, type RunScenario } from "@/lib/run/mock-run";
import AgentSprite from "./AgentSprite";
import { endedKey } from "./agent-status";
import styles from "./TeamStage.module.css";

type Vars = CSSProperties & Record<`--${string}`, string | number>;

// Node boxes of the board's 760 x 500 stage: [x, y, height]. Every node is 190 px wide.
const POS: Record<RunAgent, [number, number, number]> = { owl: [285, 40, 72], chameleon: [10, 190, 72], beaver: [285, 190, 72], hound: [565, 190, 72], cat: [285, 330, 72] };
const ORDER: RunAgent[] = ["owl", "chameleon", "beaver", "hound", "cat"];
const REPORT = { x: 285, y: 440, h: 52 };

// Board connector paths (Owl to the three workers, the three to Cat, Cat to Report) and the time one envelope takes to cross.
const EDGES: { d: string; dur: string }[] = [
  { d: "M380 112 C380 150 105 150 105 190", dur: "1.1s" },
  { d: "M380 112 L380 190", dur: "1s" },
  { d: "M380 112 C380 150 660 150 660 190", dur: "1.1s" },
  { d: "M105 262 C105 300 380 292 380 330", dur: "1.2s" },
  { d: "M380 262 L380 330", dur: "0.9s" },
  { d: "M660 262 C660 300 380 292 380 330", dur: "1.2s" },
  { d: "M380 402 L380 440", dur: "0.8s" },
];

const SPARKLE = "M12 1l2.600 7.400L22 11l-7.400 2.600L12 21l-2.600-7.400L2 11l7.400-2.600z";
const SWEAT = "M5 0C5 0 0 6 0 9a5 5 0 0 0 10 0C10 6 5 0 5 0z";

type Props = {
  agents: Record<RunAgent, AgentView>;
  events: RunEvent[];
  step: number;
  reportReady: boolean;
  scenario: RunScenario;
  finished: boolean;
};

// The board's "The team" map (desktop, 761 px and up): a contour-line map with a scale bar and compass, five agent
// cards joined by dotted connectors that turn solid as work is handed over, envelopes travelling along them, speech
// bubbles, a Report node and, at the end, a stamp. Purely visual (the map is aria-hidden): the same state is in the timeline list. Where the card is narrower than the
// map its box scrolls sideways, and only then is it a labelled tab stop.
export default function TeamStage({ agents, events, step, reportReady, scenario, finished }: Props) {
  const t = useTranslations("workspace");
  const home = useTranslations("home.team");
  const flow = deriveFlow(agents, reportReady);
  const bubbleOwl = owlBubble(events, step);
  const { ref: scrollRef, scrollable } = useScrollable<HTMLDivElement>();

  return (
    <div ref={scrollRef} className={styles.scroll} {...(scrollable ? { tabIndex: 0, role: "region", "aria-label": t("live.stageScroll") } : {})}>
      <div className={styles.bench} aria-hidden="true">
        <i className={`${styles.tpg} ${styles.mn}`} />
        <i className={`${styles.tpg} ${styles.mj}`} />
        <svg className={styles.tcmp} width="760" height="500" viewBox="0 0 760 500">
          <g transform="translate(700 448)" className={styles.compass}>
            <circle r="24" />
            <circle r="3" />
            <path d="M0 -24 L5 0 L0 24 L-5 0Z" className={styles.needle} />
            <path d="M-24 0 H24" />
            <text y="-30" textAnchor="middle">
              N
            </text>
          </g>
          <g transform="translate(40 470)" className={styles.scale}>
            <path d="M0 0 H120 M0 -5 V5 M60 -3 V3 M120 -5 V5" />
            <text x="0" y="-9">
              0 - 120 M
            </text>
          </g>
        </svg>
        <svg className={styles.edges} width="760" height="500" viewBox="0 0 760 500">
          {EDGES.map((edge, i) => (
            <path key={edge.d} d={edge.d} className={flow.edges[i] ? styles.edgeOn : styles.edgeOff} />
          ))}
          {EDGES.map((edge, i) => (
            <g key={`pk-${edge.d}`} className={`${styles.pk} ${i === 6 ? styles.pkOk : i >= 3 ? styles.pkBad : ""}`} opacity={flow.envelopes[i] ? 1 : 0}>
              <animateMotion dur={edge.dur} repeatCount="indefinite" path={edge.d} />
              <rect x="-8" y="-6" width="16" height="12" rx="2.5" strokeWidth="2" />
              <path d="M-8 -6 L0 1 L8 -6" fill="none" strokeWidth="1.6" />
            </g>
          ))}
        </svg>

        {ORDER.map((id, index) => {
          const view = agents[id];
          const key = endedKey(view, finished);
          const [x, y, h] = POS[id];
          const bubble = id === "owl" ? (bubbleOwl ? t(`live.bubbles.${bubbleOwl}`) : "") : view.state === "working" ? t(`live.bubbles.${id}`) : "";
          const bad = key === "flagged" || key === "failed";
          const idle = key === "didNotRun" ? "waiting" : key;
          const pool = view.state === "working" ? 1 : bad ? 0.7 : view.state === "done" ? 0.4 : 0;
          const live = view.state === "working" ? "on" : view.state === "waiting" ? "dim" : "";
          const bob = id === "owl" ? !!bubble : view.state === "working";
          const motion = bad ? styles.shake : bob ? styles.bob : "";
          const vars = { left: x, top: y, height: h, "--pc": bad ? "var(--bad)" : agentColor[id], "--po": pool } as Vars;
          return (
            <div key={id} className={`${styles.node} ${styles[`s_${idle}`]}`} style={vars}>
              {bubble ? (
                <div className={styles.bubble}>
                  {bubble}
                  <span className={styles.tail} />
                </div>
              ) : null}
              <span className={`${styles.pool} ${view.state === "working" ? styles.poolRun : ""}`} />
              <span className={styles.mascot}>
                <AgentSprite agent={id} live={live} size={62} phase={index} className={`${styles.sprite} ${motion}`} />
                {view.state === "waiting" && !finished ? <span className={styles.zz}>z</span> : null}
                {view.state === "done" ? (
                  <svg className={styles.sparkle} width="15" height="15" viewBox="0 0 24 24">
                    <path d={SPARKLE} />
                  </svg>
                ) : null}
                {bad ? (
                  <svg className={styles.sweat} width="10" height="14" viewBox="0 0 10 14">
                    <path d={SWEAT} />
                  </svg>
                ) : null}
              </span>
              <span className={styles.label}>
                <span className={styles.name}>
                  {home(`${id}.name`)} · {home(`${id}.role`)}
                </span>
                <span className={styles.status}>{key === "flagged" ? t("live.status.flagged", { count: view.flags }) : t(`live.status.${key}`)}</span>
              </span>
              {id !== "owl" && view.state === "working" ? (
                <svg className={styles.spinner} width="18" height="18" viewBox="0 0 34 34">
                  <circle cx="17" cy="17" r="14" fill="none" strokeWidth="5" opacity="0.5" />
                  <path d="M17 3a14 14 0 0 1 14 14" fill="none" strokeWidth="5" strokeLinecap="round" />
                </svg>
              ) : null}
            </div>
          );
        })}

        <div className={`${styles.node} ${reportReady ? styles.s_done : styles.s_waiting}`} style={{ left: REPORT.x, top: REPORT.y, height: REPORT.h } as Vars}>
          <span className={styles.reportIcon}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
              <path d="M5 12.5l5 5 9-10" />
            </svg>
          </span>
          <span className={styles.label}>
            <span className={styles.name}>{t("live.reportNode.name")}</span>
            <span className={styles.status}>{t(reportReady ? "live.reportNode.ready" : finished ? "live.reportNode.notReached" : "live.reportNode.waiting")}</span>
          </span>
        </div>

        {finished && scenario !== "failed" ? <div className={`${styles.stamp} ${scenario === "partial" ? styles.stampWarn : ""}`}>{t(`live.stamp.${scenario}`)}</div> : null}
      </div>
    </div>
  );
}
