import type { CSSProperties } from "react";
import type { RunAgent } from "@/lib/run/mock-run";
import styles from "./AgentSprite.module.css";

type Vars = CSSProperties & Record<`--${string}`, string>;

// The board's animated mascot (".lvs"): the Home sprite sheet (24 frames of 176 px) shown one frame at a time and
// stepped by CSS. `live` runs it; `dim` shows it faded and still. A plain img (not next/image) because CSS steps it.
export default function AgentSprite({ agent, live, size, phase, className = "" }: { agent: RunAgent; live: "on" | "dim" | ""; size: number; phase: number; className?: string }) {
  const style = { width: size, height: size, "--phase": `${(-0.45 * phase).toFixed(2)}s` } as Vars;
  return (
    <span className={`${styles.lvs} ${live ? styles[live] : ""} ${className}`} style={style} aria-hidden="true">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={`/home/sprite-${agent}.webp`} alt="" width={4224} height={176} decoding="async" />
    </span>
  );
}
