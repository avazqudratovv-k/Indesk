import { renderToStaticMarkup } from "react-dom/server";
import { NextIntlClientProvider } from "next-intl";
import { describe, expect, it } from "vitest";
import en from "@/messages/en.json";
import ko from "@/messages/ko.json";
import type { AgentView, RunAgent } from "@/lib/run/mock-run";
import { endedKey, tabStatus } from "./agent-status";
import RealAgentWork from "./RealAgentWork";
import { runSeconds } from "./RunTiles";

const view = (state: AgentView["state"]): AgentView => ({ state, flags: 0 });
const failedPdfRun = (): Record<RunAgent, AgentView> => ({ owl: view("done"), chameleon: view("waiting"), beaver: view("skipped"), hound: view("waiting"), cat: view("waiting") });

describe("one word for unbuilt things", () => {
  it("never says Coming soon, Coming later, 곧 제공, 추후 제공 or 준비 중", () => {
    const text = JSON.stringify({ en, ko });
    for (const old of ["Coming soon", "Coming later", "곧 제공", "추후 제공", "준비 중"]) expect(text).not.toContain(old);
  });

  it("uses Not available yet / 아직 쓸 수 없음 for the modes, the Home cards, the agent and the upload panel", () => {
    const places = (m: typeof en) => [m.home.modes.comingSoon, m.home.team.comingLater, m.workspace.modes.soon, m.workspace.live.status.comingLater, m.workspace.artifacts.states.comingLater, m.workspace.info.later];
    for (const label of places(en)) expect(label).toMatch(/^(Not available yet|This agent is not available yet\.)$/);
    for (const label of places(ko as unknown as typeof en)) expect(label).toMatch(/^(아직 쓸 수 없음|이 에이전트는 아직 쓸 수 없습니다\.)$/);
  });
});

describe("Korean wording", () => {
  it("counts pages without text as pages, not as page n", () => {
    expect(ko.workspace.upload.pagesWithoutText).toBe("텍스트가 없는 페이지가 {n, number}개 있어 검색할 수 없습니다.");
  });

  it("says 주장 and never 진술, and keeps no invisible word-joiner", () => {
    const text = JSON.stringify(ko);
    expect(text).not.toContain("진술");
    expect(text).not.toContain("\\u2060");
    expect(text).not.toContain("⁠");
  });
});

describe("Did not start", () => {
  it("is Hound's state in a PDF run that ended before Hound started, and Beaver's in a CSV run that ended before Beaver", () => {
    expect(tabStatus("hound", view("waiting"), true, true)).toBe("didNotRun");
    expect(endedKey("hound", view("waiting"), true, true)).toBe("didNotRun");
    expect(tabStatus("beaver", view("waiting"), true, true)).toBe("didNotRun");
  });

  it("stays Not used for the agent that is not part of this kind of run", () => {
    expect(tabStatus("beaver", view("skipped"), true, true)).toBe("notUsed");
    expect(tabStatus("hound", view("skipped"), true, true)).toBe("notUsed");
  });

  it("is written on the tab body in English and Korean", () => {
    const body = (locale: "en" | "ko") =>
      renderToStaticMarkup(
        <NextIntlClientProvider locale={locale} messages={locale === "en" ? en : ko}>
          <RealAgentWork agents={failedPdfRun()} events={[]} finished reportId={null} />
        </NextIntlClientProvider>,
      );
    expect(en.workspace.live.status.didNotRun).toBe("Did not start");
    expect(ko.workspace.live.status.didNotRun).toBe("시작하지 않음");
    expect(body("en")).not.toContain("Not used in this run");
    expect(body("ko")).not.toContain("이 실행에서는 사용하지 않았습니다");
  });
});

describe("run time tile", () => {
  it("uses only the server's start and finish for a finished run, whatever the browser clock says", () => {
    const real = { startMs: 1_000_000, endMs: 1_012_500 };
    expect(runSeconds(real, 0)).toBe(12.5);
    expect(runSeconds(real, 9_999_999_999)).toBe(12.5);
  });

  it("counts a running run from its start to now, never below zero, and is empty without a start", () => {
    expect(runSeconds({ startMs: 1_000_000, endMs: null }, 1_004_000)).toBe(4);
    expect(runSeconds({ startMs: 1_000_000, endMs: null }, 990_000)).toBe(0);
    expect(runSeconds({ startMs: null, endMs: null }, 5)).toBeNull();
  });
});
