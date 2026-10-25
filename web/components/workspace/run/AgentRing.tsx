import type { AgentState, RunAgent } from "@/lib/run/mock-run";
import styles from "./AgentRing.module.css";

export type RingState = AgentState | "flagged";

const badges: Partial<Record<RingState, string>> = { done: "✓", skipped: "–", failed: "!", flagged: "!" };

// The board's agent medallion (88 px box): the mascot, a state ring and a small badge. Decorative: the state is always
// written out next to it. Spin and bob stop under prefers-reduced-motion.
export default function AgentRing({ agent, state, size = 88 }: { agent: RunAgent; state: RingState; size?: number }) {
  const badge = badges[state];
  return (
    <svg className={`${styles.ring} ${styles[state]}`} width={size} height={size} viewBox="0 0 88 88" aria-hidden="true" focusable="false">
      <circle className={styles.disc} cx="44" cy="44" r="33" />
      <image className={styles.mascot} href={`/workspace/agent-${agent}.png`} x="12" y="12" width="64" height="64" />
      <circle className={styles.track} cx="44" cy="44" r="40" />
      {badge ? (
        <>
          <circle className={styles.badge} cx="72" cy="72" r="11" />
          <text className={styles.badgeText} x="72" y="77" textAnchor="middle">
            {badge}
          </text>
        </>
      ) : null}
    </svg>
  );
}
