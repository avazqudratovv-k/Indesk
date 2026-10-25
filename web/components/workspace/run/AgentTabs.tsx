import { useRef } from "react";
import { useTranslations } from "next-intl";
import { RUN_AGENTS, type AgentView, type RunAgent } from "@/lib/run/mock-run";
import { tabStatus } from "./agent-status";
import styles from "./AgentTabs.module.css";

type Props = {
  agents: Record<RunAgent, AgentView>;
  finished: boolean;
  selected: RunAgent;
  idPrefix: string;
  onPick: (agent: RunAgent) => void;
};

export const tabId = (prefix: string, agent: RunAgent) => `${prefix}-tab-${agent}`;
export const panelId = (prefix: string) => `${prefix}-panel`;

// WAI-ARIA tabs for the five agents: one tab stop (roving tabindex), Left/Right/Home/End move and select, and one
// tabpanel (owned by AgentWork) that the selected tab controls. The status word is read out with the name.
export default function AgentTabs({ agents, finished, selected, idPrefix, onPick }: Props) {
  const t = useTranslations("workspace");
  const home = useTranslations("home.team");
  const refs = useRef<Partial<Record<RunAgent, HTMLButtonElement | null>>>({});

  function onKeyDown(event: React.KeyboardEvent, index: number) {
    const last = RUN_AGENTS.length - 1;
    const target = { ArrowRight: index === last ? 0 : index + 1, ArrowLeft: index === 0 ? last : index - 1, Home: 0, End: last }[event.key];
    if (target === undefined) return;
    event.preventDefault();
    const agent = RUN_AGENTS[target];
    onPick(agent);
    refs.current[agent]?.focus();
  }

  return (
    <div className={styles.list} role="tablist" aria-label={t("artifacts.tabsLabel")}>
      {RUN_AGENTS.map((agent, index) => {
        const status = tabStatus(agents[agent], finished);
        const on = agent === selected;
        return (
          <button
            key={agent}
            ref={(node) => {
              refs.current[agent] = node;
            }}
            id={tabId(idPrefix, agent)}
            type="button"
            role="tab"
            aria-selected={on}
            aria-controls={panelId(idPrefix)}
            tabIndex={on ? 0 : -1}
            className={`${styles.tab} ${on ? styles.on : ""}`}
            onClick={() => onPick(agent)}
            onKeyDown={(event) => onKeyDown(event, index)}
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={`/workspace/agent-${agent}.png`} alt="" width={34} height={34} className={styles.icon} />
            {home(`${agent}.name`)}
            <span className={`${styles.dot} ${styles[`d_${status}`]}`} aria-hidden="true" />
            <span className={styles.srOnly}>
              {" "}
              ({t(`artifacts.status.${status}`)})
            </span>
          </button>
        );
      })}
    </div>
  );
}
