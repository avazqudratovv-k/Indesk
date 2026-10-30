import { renderToStaticMarkup } from "react-dom/server";
import { NextIntlClientProvider } from "next-intl";
import { describe, expect, it } from "vitest";
import en from "@/messages/en.json";
import ko from "@/messages/ko.json";
import { countAgentsDone, type AgentView, type RunAgent } from "@/lib/run/mock-run";
import { markUnused, RUN_WORKERS, runKind, tabStatus } from "./agent-status";
import RealAgentWork from "./RealAgentWork";
import RunTiles from "./RunTiles";

const view = (state: AgentView["state"]): AgentView => ({ state, flags: 0 });
const agents = (states: Partial<Record<RunAgent, AgentView["state"]>>): Record<RunAgent, AgentView> => ({
  owl: view(states.owl ?? "waiting"),
  chameleon: view(states.chameleon ?? "waiting"),
  beaver: view(states.beaver ?? "waiting"),
  hound: view(states.hound ?? "waiting"),
  cat: view(states.cat ?? "waiting"),
});

describe("the kind of a real run", () => {
  it("is a PDF run once Hound starts or Beaver is skipped, a CSV run once Beaver starts or Hound is skipped", () => {
    expect(runKind(agents({ owl: "working" }))).toBeNull();
    expect(runKind(agents({ owl: "done", hound: "working" }))).toBe("pdf");
    expect(runKind(agents({ owl: "done", beaver: "skipped" }))).toBe("pdf");
    expect(runKind(agents({ owl: "done", beaver: "working" }))).toBe("csv");
    expect(runKind(agents({ owl: "done", hound: "skipped" }))).toBe("csv");
  });

  it("marks Beaver Not used in a PDF run, and nothing else", () => {
    const pdf = markUnused(agents({ hound: "working" }), "pdf");
    expect(pdf.beaver.state).toBe("skipped");
    expect(tabStatus("beaver", pdf.beaver, false, true)).toBe("notUsed");
    expect(tabStatus("chameleon", pdf.chameleon, true, true)).toBe("comingLater");
    const csv = agents({ beaver: "working" });
    expect(markUnused(csv, "csv")).toBe(csv);
  });

  it("keeps Beaver as Did not run in a CSV run that ended before it started", () => {
    expect(tabStatus("beaver", view("waiting"), true, true)).toBe("didNotRun");
  });
});

describe("Agents done tile", () => {
  const tile = (done: number, count: number, locale: "en" | "ko" = "en") =>
    renderToStaticMarkup(
      <NextIntlClientProvider locale={locale} messages={locale === "en" ? en : ko}>
        <RunTiles toolCalls={0} tokens={0} agentsDone={done} agentCount={count} finished real={{ startMs: 0, endMs: 1000 }} />
      </NextIntlClientProvider>,
    );

  it("counts only the agents that can work in the run type", () => {
    expect(RUN_WORKERS.csv).toEqual(["owl", "beaver", "cat"]);
    expect(RUN_WORKERS.pdf).toEqual(["owl", "hound", "cat"]);
    const csvDone = agents({ owl: "done", beaver: "done", cat: "done", hound: "skipped" });
    const pdfDone = markUnused(agents({ owl: "done", hound: "done", cat: "done" }), "pdf");
    expect(countAgentsDone(csvDone, RUN_WORKERS.csv)).toBe(3);
    expect(countAgentsDone(pdfDone, RUN_WORKERS.pdf)).toBe(3);
    expect(countAgentsDone(pdfDone, RUN_WORKERS.csv)).toBe(2);
  });

  it("renders M of M for a finished run", () => {
    expect(tile(3, RUN_WORKERS.pdf.length)).toContain("3 / 3");
    expect(tile(3, RUN_WORKERS.csv.length)).toContain("3 / 3");
  });
});

describe("the run view of a PDF run", () => {
  const work = (locale: "en" | "ko") =>
    renderToStaticMarkup(
      <NextIntlClientProvider locale={locale} messages={locale === "en" ? en : ko}>
        <RealAgentWork agents={markUnused(agents({ owl: "done", hound: "done", cat: "done" }), "pdf")} events={[]} finished reportId={null} />
      </NextIntlClientProvider>,
    );

  it("shows Beaver's tab as Not used and Chameleon's as Coming later", () => {
    expect(work("en")).toContain("Not used");
    expect(work("ko")).toContain("사용 안 함");
    expect(en.workspace.artifacts.states.notUsed).toBe("Not used in this run");
  });
});
