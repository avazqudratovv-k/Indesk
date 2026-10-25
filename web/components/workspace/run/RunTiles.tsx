"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { TOOL_CALL_LIMIT } from "@/lib/run/mock-run";
import styles from "./RunTiles.module.css";

// Seconds on the real clock since the tile mounted (a run mounts it fresh), frozen when the run finishes. This is the
// playback time of the demo, measured; the rest of the tiles come from the script.
function useElapsed(finished: boolean): number {
  const [start] = useState(() => performance.now());
  const [now, setNow] = useState(start);
  useEffect(() => {
    if (finished) {
      const id = setTimeout(() => setNow(performance.now()), 0);
      return () => clearTimeout(id);
    }
    const id = setInterval(() => setNow(performance.now()), 100);
    return () => clearInterval(id);
  }, [finished]);
  return (now - start) / 1000;
}

type Props = { toolCalls: number; tokens: number; agentsDone: number; agentCount: number; finished: boolean };

// Board summary tiles, in step with the events. Time is the real elapsed clock; Tokens and Tool calls are scripted
// ("Example"); Agents done replaces the board's Cost tile (no cost is shown to users, DECISIONS #74).
export default function RunTiles({ toolCalls, tokens, agentsDone, agentCount, finished }: Props) {
  const t = useTranslations("workspace");
  const elapsed = useElapsed(finished);
  const tiles = [
    { id: "time", value: `${elapsed.toFixed(1)}s`, tag: t("live.tilesTag.playback") },
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
          <span className={styles.tag}>{tile.tag}</span>
        </div>
      ))}
    </section>
  );
}
