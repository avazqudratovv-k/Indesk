import { describe, expect, it } from "vitest";
import en from "@/messages/en.json";
import ko from "@/messages/ko.json";

const sets = [
  ["en", en],
  ["ko", ko],
] as const;

describe("outcome and plans copy tells the truth", () => {
  it.each(sets)("%s: every changed key exists", (_lang, m) => {
    const o = m.workspace.live.outcomes;
    for (const text of [o.answered.body, o.failed.body, o.counted, o.notCounted, m.plans.paidMsg, m.plans.limitBody, m.plans.bannerDemo, m.plans.limitsLine, m.plans.features.pdfPages, m.workspace.live.guard.budgetValue, m.home.closing.title]) {
      expect(text).toBeTruthy();
    }
  });

  it("en uses the exact agreed sentences", () => {
    expect(en.workspace.live.outcomes.answered.body).toBe("Every number shows the row or page it came from.");
    expect(en.workspace.live.outcomes.failed.body).toBe("Please try again. This didn't use one of your free runs.");
    expect(en.plans.paidMsg).toBe("Demo only: nothing changed on your account.");
    expect(en.workspace.live.guard.budgetValue).toBe("Each run has a size cap.");
    expect(en.home.closing.title).toBe("Start free. Paid plans are simulated in this demo.");
    expect(en.plans.bannerDemo).toBe("Demo only: paid plans are simulated");
  });

  it.each(sets)("%s: no claim of links, raised limits, a server block, spending or old plan promises", (_lang, m) => {
    const text = JSON.stringify([m.plans, m.workspace.live.outcomes, m.workspace.live.guard, m.home.closing]);
    for (const old of ["links to", "Your limits were raised", "한도가 늘어났습니다", "The server blocks", "서버가 새 실행을 막습니다", "spending", "지출", "was not used up", "차감되지", "Pay only"]) {
      expect(text).not.toContain(old);
    }
  });

  it.each(sets)("%s: the limits line carries the four real numbers as parameters", (_lang, m) => {
    for (const p of ["{mb, number}", "{rows, number}", "{pages, number}", "{runs, number}"]) expect(m.plans.limitsLine).toContain(p);
  });

  it("the removed calculator keys are gone in both languages", () => {
    for (const [, m] of sets) {
      for (const key of ["fileSize", "dataSize", "parallel", "optionsNote", "lineFileSize", "lineParallel", "included"]) expect(m.plans.custom).not.toHaveProperty(key);
    }
  });

  it.each(sets)("%s: checkout success and card limit keys exist", (_lang, m) => {
    for (const text of [m.plans.checkout.successTitle, m.plans.checkout.successLine, m.plans.features.fileSize, m.plans.features.csvRows, m.plans.features.pdfPages]) {
      expect(text).toBeTruthy();
    }
  });

  it("en success screen says demo checkout, no money moved and the account stays on Free", () => {
    expect(en.plans.checkout.successTitle).toBe("Demo checkout complete");
    expect(en.plans.checkout.successLine).toContain("No real money moved.");
    expect(en.plans.checkout.successLine).toContain("Your account stays on the Free plan.");
  });

  it.each(sets)("%s: success copy never claims a payment or a plan change", (_lang, m) => {
    const text = `${m.plans.checkout.successTitle} ${m.plans.checkout.successLine}`;
    // "데모 결제가 완료되었습니다" (Demo checkout complete) is the allowed wording; a plain "결제가 완료" is not.
    for (const old of ["Payment successful", "went through", "결제가 처리"]) expect(text).not.toContain(old);
    expect(text.replaceAll("데모 결제가 완료", "")).not.toContain("결제가 완료");
  });
});
