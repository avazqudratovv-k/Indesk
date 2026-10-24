import type { AgentId } from "./agents";

// Original geometric marks: 48 px grid, 2.5 stroke, a soft body fill, solid eyes. Color comes from currentColor.
const strokeProps = { stroke: "currentColor", strokeWidth: 2.5, strokeLinejoin: "round", strokeLinecap: "round" } as const;
const soft = { fill: "currentColor", fillOpacity: 0.16 } as const;

function Shapes({ agent }: { agent: AgentId }) {
  switch (agent) {
    case "owl":
      return (
        <>
          <polygon points="9,19 11,7 20,13" {...soft} {...strokeProps} />
          <polygon points="39,19 37,7 28,13" {...soft} {...strokeProps} />
          <rect x="9" y="12" width="30" height="30" rx="15" {...soft} {...strokeProps} />
          <circle cx="17.5" cy="25" r="5" fill="none" {...strokeProps} />
          <circle cx="30.5" cy="25" r="5" fill="none" {...strokeProps} />
          <circle cx="17.5" cy="25" r="1.8" fill="currentColor" />
          <circle cx="30.5" cy="25" r="1.8" fill="currentColor" />
          <polygon points="24,29 21,34 27,34" fill="currentColor" {...strokeProps} strokeWidth={1.5} />
        </>
      );
    case "chameleon":
      return (
        <>
          <polygon points="12,14 17,7 22,13" {...soft} {...strokeProps} />
          <ellipse cx="22" cy="27" rx="15" ry="12" {...soft} {...strokeProps} />
          <path d="M36 28c8 0 9 11 2 11-4 0-4-5-1-5" fill="none" {...strokeProps} />
          <circle cx="17" cy="23" r="5" fill="none" {...strokeProps} />
          <circle cx="17" cy="23" r="1.8" fill="currentColor" />
          <path d="M8 31h8" fill="none" {...strokeProps} />
          <path d="M16 39v4M28 39v4" fill="none" {...strokeProps} />
        </>
      );
    case "beaver":
      return (
        <>
          <circle cx="12.5" cy="13" r="5" {...soft} {...strokeProps} />
          <circle cx="35.5" cy="13" r="5" {...soft} {...strokeProps} />
          <circle cx="24" cy="26" r="15" {...soft} {...strokeProps} />
          <circle cx="18" cy="23" r="1.8" fill="currentColor" />
          <circle cx="30" cy="23" r="1.8" fill="currentColor" />
          <ellipse cx="24" cy="29" rx="4" ry="3" fill="currentColor" />
          <rect x="20.5" y="32" width="7" height="7" rx="1.5" fill="none" {...strokeProps} />
          <path d="M24 32v7" fill="none" {...strokeProps} strokeWidth={1.5} />
        </>
      );
    case "hound":
      return (
        <>
          <path d="M14 13C5 13 5 31 12 34c2-6 2-13 2-21z" {...soft} {...strokeProps} />
          <path d="M34 13c9 0 9 18 2 21-2-6-2-13-2-21z" {...soft} {...strokeProps} />
          <rect x="14" y="8" width="20" height="26" rx="10" {...soft} {...strokeProps} />
          <ellipse cx="24" cy="34" rx="8" ry="6.5" {...soft} {...strokeProps} />
          <circle cx="19" cy="21" r="1.8" fill="currentColor" />
          <circle cx="29" cy="21" r="1.8" fill="currentColor" />
          <ellipse cx="24" cy="30" rx="3.2" ry="2.2" fill="currentColor" />
          <path d="M24 32v4" fill="none" {...strokeProps} strokeWidth={1.5} />
        </>
      );
    case "cat":
      return (
        <>
          <polygon points="10,22 11,6 24,15" {...soft} {...strokeProps} />
          <polygon points="38,22 37,6 24,15" {...soft} {...strokeProps} />
          <ellipse cx="24" cy="28" rx="15" ry="13" {...soft} {...strokeProps} />
          <ellipse cx="18" cy="26" rx="1.8" ry="2.6" fill="currentColor" />
          <ellipse cx="30" cy="26" rx="1.8" ry="2.6" fill="currentColor" />
          <polygon points="24,31 21.5,28.8 26.5,28.8" fill="currentColor" {...strokeProps} strokeWidth={1.5} />
          <path d="M3 29h9M3 34l8-2M45 29h-9M45 34l-8-2" fill="none" {...strokeProps} strokeWidth={1.8} />
        </>
      );
  }
}

export default function AgentMark({ agent, size = 40 }: { agent: AgentId; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" fill="none" aria-hidden="true" focusable="false">
      <Shapes agent={agent} />
    </svg>
  );
}
