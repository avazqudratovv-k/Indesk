"use client";

import { useEffect, useMemo, useState } from "react";
import { useReducedMotion } from "@/hooks/use-reduced-motion";
import { countToolCalls, deriveAgents, getRunScript, type RunScenario } from "@/lib/run/mock-run";

// Time between scripted events (the board uses 800 ms). It paces the demo; it is not a measured duration.
const STEP_MS = 800;

// Plays the scripted demo run. With reduced motion it shows every event at once (the final state).
// Retry (a failed agent) replays the script as the plain "answered" case: it is a demo, no model is called.
export function useMockRun(initial: RunScenario) {
  const reduced = useReducedMotion();
  const [scenario, setScenario] = useState<RunScenario>(initial);
  const [played, setPlayed] = useState(0);
  const [round, setRound] = useState(0);

  const events = useMemo(() => getRunScript(scenario), [scenario]);
  const step = reduced ? events.length : Math.min(played, events.length);
  const finished = step >= events.length;

  useEffect(() => {
    if (reduced || finished) return;
    const timer = setTimeout(() => setPlayed((value) => value + 1), STEP_MS);
    return () => clearTimeout(timer);
  }, [reduced, finished, played, round]);

  function restart(next: RunScenario) {
    setScenario(next);
    setPlayed(0);
    setRound((value) => value + 1);
  }

  return {
    scenario,
    events,
    step,
    finished,
    round,
    agents: deriveAgents(events, step),
    toolCalls: countToolCalls(events, step),
    replay: () => restart(scenario),
    retry: () => restart("answered"),
  };
}
