import { isKnownReason } from "./reasons";
import type { TraceArgs } from "./types";

// The closed set of trace keys (api/app/runs/trace.py TraceKey) and the arguments each may use. A key we do not know,
// or an argument of the wrong kind, never reaches the screen as text: it becomes a generic line.
export const TRACE_KEYS = ["plan", "dispatch", "readCsv", "runPython", "top3", "merge", "ready", "stepStarted", "stepFailed", "stopped"] as const;
export type TraceKey = (typeof TRACE_KEYS)[number];

// Message ids under workspace.trace.* (one per wording; a variant exists where an argument can be missing).
export const TRACE_MESSAGE_IDS = [
  "plan", "planFiles", "dispatch", "dispatchAgents", "readCsv", "readCsvSized", "runPython", "runPythonAttempt",
  "top3", "top3Rows", "merge", "ready", "stepStarted", "stepStartedAttempt", "stepFailed", "stepFailedReason",
  "stopped", "stoppedReason", "unknown",
] as const;
export type TraceMessageId = (typeof TRACE_MESSAGE_IDS)[number];

export type TraceText = { id: TraceMessageId; values: Record<string, number | string>; simulated: boolean };

function count(args: TraceArgs, name: string, min: number): number | null {
  const value = args[name];
  return typeof value === "number" && Number.isInteger(value) && value >= min && value <= 1_000_000_000 ? value : null;
}

function isTraceKey(key: string): key is TraceKey {
  return (TRACE_KEYS as readonly string[]).includes(key);
}

export function describeTrace(key: string, args: TraceArgs): TraceText {
  const simulated = args.stub === true;
  const say = (id: TraceMessageId, values: Record<string, number | string> = {}): TraceText => ({ id, values, simulated });
  if (!isTraceKey(key)) return say("unknown");
  const attempt = count(args, "attempt", 2);
  switch (key) {
    case "plan": {
      const files = count(args, "files", 1);
      return files === null ? say("plan") : say("planFiles", { files });
    }
    case "dispatch": {
      const agents = count(args, "agents", 1);
      return agents === null ? say("dispatch") : say("dispatchAgents", { agents });
    }
    case "readCsv": {
      const rows = count(args, "rows", 0);
      const cols = count(args, "cols", 0);
      return rows === null || cols === null ? say("readCsv") : say("readCsvSized", { rows, cols });
    }
    case "runPython":
      return attempt === null ? say("runPython") : say("runPythonAttempt", { attempt });
    case "top3": {
      const rows = count(args, "rows", 0);
      return rows === null ? say("top3") : say("top3Rows", { rows });
    }
    case "merge":
      return say("merge");
    case "ready":
      return say("ready");
    case "stepStarted":
      return attempt === null ? say("stepStarted") : say("stepStartedAttempt", { attempt });
    case "stepFailed": {
      const reason = args.reason;
      return typeof reason === "string" && isKnownReason(reason) ? say("stepFailedReason", { reason }) : say("stepFailed");
    }
    case "stopped": {
      const reason = args.reason;
      return typeof reason === "string" && isKnownReason(reason) ? say("stoppedReason", { reason }) : say("stopped");
    }
  }
}
