"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { TOOL_CALL_LIMIT } from "@/lib/run/mock-run";
import styles from "./RunTiles.module.css";

// Seconds on the real clock since the tile mounted (a run mounts it fresh), frozen when the run finishes. This is the
// playback time of the demo, measured; the rest of the tiles come from the script.
function useElapsed(finished: boolean, fixed: boolean): number {
  const [start] = useState(() => performance.now());
  const [now, setNow] = useState(start);
  useEffect(() => {
    if (fixed) return;
    if (finished) {
      const id = setTimeout(() => setNow(performance.now()), 0);
      return () => clearTimeout(id);
    }
    const id = setInterval(() => setNow(performance.now()), 100);
    return () => clearInterval(id);
  }, [finished, fixed]);
  return (now - start) / 1000;
}

// `real` is set for a real run: the time runs from the run's start to its end (or to now while it is going) and the other
// tiles are counted from the run's own events, so the "Example" and "Demo playback" tags are left out.
// The current time, refreshed twice a second while `active`.
function useNow(active: boolean): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!active) return;
    const id = setInterval(() => setNow(Date.now()), 500);
    return () => clearInterval(id);
  }, [active]);
  return now;
}

// Seconds a real run took. A finished run uses only the server's own start and finish times, so a reload or a resumed
// run shows the same number as the first time. A running one counts up from the server start to the browser clock.
// (Not done: a skew offset between the two clocks; the API sends no server time yet, see the report.)
export function runSeconds(real: { startMs: number | null; endMs: number | null }, now: number): number | null {
  if (real.startMs === null) return null;
  return Math.max(0, ((real.endMs ?? now) - real.startMs) / 1000);
}

type Props = { toolCalls: number; tokens: number; agentsDone: number; agentCount: number; finished: boolean; real?: { startMs: number | null; endMs: number | null } };

// Board summary tiles, in step with the events. Time is the real elapsed clock; Tokens and Tool calls are scripted
// ("Example"); Agents done replaces the board's Cost tile (no cost is shown to users, DECISIONS #74).
export default function RunTiles({ toolCalls, tokens, agentsDone, agentCount, finished, real }: Props) {
  const t = useTranslations("workspace");
  const playback = useElapsed(finished, real !== undefined);
  const now = useNow(real !== undefined && real.endMs === null);
  const elapsed = real ? runSeconds(real, now) : playback;
  const tiles = [
    { id: "time", value: elapsed === null ? "—" : `${elapsed.toFixed(1)}s`, tag: t("live.tilesTag.playback") },
    { id: "tokens", value: tokens.toLocaleString("en-US"), tag: t("live.tilesTag.example") },
    { id: "agents", value: `${agentsDone} / ${agentCount}`, tag: t("live.tilesTag.example") },
    { id: "tools", value: `${toolCalls} / ${TOOL_CALL_LIMIT}`, tag: t("live.tilesTag.example") },
  ];
  return (
    <section className={styles.tiles} aria-label={t("live.tilesLabel")}>
      {tiles.map((tile) => (
        <div key={tile.id} className={styles.tile}>
          <div className={styles.name}>{t(`live.tiles.${tile.id}`)}</div>
          <div className={styles.value}>{tile.value}</div>
          {real ? null : <span className={styles.tag}>{tile.tag}</span>}
        </div>
      ))}
    </section>
  );
}
