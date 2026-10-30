import { describe, expect, it } from "vitest";
import en from "@/messages/en.json";
import ko from "@/messages/ko.json";
import { SESSION_MAX_SECONDS } from "@/lib/limits";
import { parseLoginAt } from "./hint";
import {
  clearSessionEnded,
  consumeNotice,
  isAuthPath,
  NOTICE_KEY,
  noticeMessage,
  sessionEndedAfterLimit,
  sessionEndedNotice,
  shouldWriteSessionEnded,
  writeNotice,
  type NoticeStorage,
} from "./notice";

function memoryStorage(initial: Record<string, string> = {}): NoticeStorage & { data: Record<string, string> } {
  const data = { ...initial };
  return {
    data,
    getItem: (key) => data[key] ?? null,
    setItem: (key, value) => {
      data[key] = value;
    },
    removeItem: (key) => {
      delete data[key];
    },
  };
}

describe("the notice store", () => {
  it("writes one notice under one key and reads it back once", () => {
    const storage = memoryStorage();
    writeNotice(storage, { kind: "welcome", name: "Kim" });
    expect(Object.keys(storage.data)).toEqual([NOTICE_KEY]);
    expect(consumeNotice(storage)).toEqual({ kind: "welcome", name: "Kim" });
    expect(storage.data).toEqual({});
    expect(consumeNotice(storage)).toBeNull();
  });

  it("keeps only the latest notice", () => {
    const storage = memoryStorage();
    writeNotice(storage, { kind: "sessionEnded", sixHours: true });
    writeNotice(storage, { kind: "loggedOut" });
    expect(consumeNotice(storage)).toEqual({ kind: "loggedOut" });
  });

  it("reads each kind", () => {
    const storage = memoryStorage();
    writeNotice(storage, { kind: "sessionEnded", sixHours: false });
    expect(consumeNotice(storage)).toEqual({ kind: "sessionEnded", sixHours: false });
  });

  it("ignores unknown kinds and malformed storage, and still removes them", () => {
    for (const raw of ['{"kind":"promo"}', "not json", "null", "42", '"welcome"', "[]", "{}"]) {
      const storage = memoryStorage({ [NOTICE_KEY]: raw });
      expect(consumeNotice(storage), raw).toBeNull();
      expect(storage.data).toEqual({});
    }
  });

  it("reads a welcome with a bad name as the nameless welcome", () => {
    const storage = memoryStorage({ [NOTICE_KEY]: '{"kind":"welcome","name":7}' });
    expect(consumeNotice(storage)).toEqual({ kind: "welcome", name: "" });
  });

  it("does not throw when storage throws", () => {
    const broken: NoticeStorage = {
      getItem: () => {
        throw new Error("blocked");
      },
      setItem: () => {
        throw new Error("blocked");
      },
      removeItem: () => {
        throw new Error("blocked");
      },
    };
    expect(() => writeNotice(broken, { kind: "loggedOut" })).not.toThrow();
    expect(consumeNotice(broken)).toBeNull();
    expect(() => clearSessionEnded(broken)).not.toThrow();
  });

  it("drops a pending session-ended notice and leaves other kinds", () => {
    const ended = memoryStorage();
    writeNotice(ended, { kind: "sessionEnded", sixHours: true });
    clearSessionEnded(ended);
    expect(ended.data).toEqual({});
    const other = memoryStorage();
    writeNotice(other, { kind: "loggedOut" });
    clearSessionEnded(other);
    expect(consumeNotice(other)).toEqual({ kind: "loggedOut" });
  });
});

describe("the 6-hour wording", () => {
  const limitMs = SESSION_MAX_SECONDS * 1000;
  const now = 1_800_000_000_000;

  it("is 21600 seconds", () => {
    expect(SESSION_MAX_SECONDS).toBe(21600);
  });

  it("says 6 hours only when the login is at least 6 hours old", () => {
    expect(sessionEndedAfterLimit(now - limitMs + 1, now)).toBe(false); // just under
    expect(sessionEndedAfterLimit(now - limitMs, now)).toBe(true); // exactly
    expect(sessionEndedAfterLimit(now - limitMs - 1, now)).toBe(true); // over
    expect(sessionEndedAfterLimit(now - 60_000, now)).toBe(false);
  });

  it("uses the generic line when the login time is missing or in the future", () => {
    expect(sessionEndedAfterLimit(null, now)).toBe(false);
    expect(sessionEndedAfterLimit(now + 1, now)).toBe(false);
    expect(sessionEndedNotice(null, now)).toEqual({ kind: "sessionEnded", sixHours: false });
    expect(sessionEndedNotice(now - limitMs, now)).toEqual({ kind: "sessionEnded", sixHours: true });
  });

  it("reads the stored login time and treats the old '1' hint or junk as missing", () => {
    expect(parseLoginAt(String(now))).toBe(now);
    for (const raw of [null, "1", "", "abc", "NaN", "-5"]) expect(parseLoginAt(raw), String(raw)).toBeNull();
  });

  it("takes the hour count from the limit, not from the copy", () => {
    expect(noticeMessage({ kind: "sessionEnded", sixHours: true })).toEqual({ key: "sessionEndedHours", values: { hours: 6 } });
    expect(noticeMessage({ kind: "sessionEnded", sixHours: false })).toEqual({ key: "sessionEnded" });
  });
});

describe("which message a notice shows", () => {
  it("welcomes by name, or without a name when it is empty", () => {
    expect(noticeMessage({ kind: "welcome", name: " Kim " })).toEqual({ key: "welcome", values: { name: "Kim" } });
    expect(noticeMessage({ kind: "welcome", name: "   " })).toEqual({ key: "welcomeNoName" });
    expect(noticeMessage({ kind: "loggedOut" })).toEqual({ key: "loggedOut" });
  });
});

describe("no redirect loop", () => {
  it("never writes on /login or /signup", () => {
    for (const path of ["/login", "/signup", "/login/", "/signup/x"]) {
      expect(isAuthPath(path), path).toBe(true);
      for (const before of ["signedIn", "unknownWithHint"] as const) expect(shouldWriteSessionEnded(before, path)).toBe(false);
    }
    expect(isAuthPath("/loginx")).toBe(false);
    expect(isAuthPath(null)).toBe(false);
  });

  it("writes only on a signed-in to signed-out change (or a cold load with a hint)", () => {
    expect(shouldWriteSessionEnded("signedIn", "/my")).toBe(true);
    expect(shouldWriteSessionEnded("unknownWithHint", "/")).toBe(true);
    expect(shouldWriteSessionEnded("unknown", "/my")).toBe(false);
    expect(shouldWriteSessionEnded("signedOut", "/my")).toBe(false);
  });

  it("settles after one notice: auth-lost, redirect to /login, repeated auth-lost", () => {
    const storage = memoryStorage();
    let status: "signedIn" | "signedOut" = "signedIn";
    let path = "/my";
    let writes = 0;
    // The provider's auth-lost handler: decide first, then sign out. A notice changes neither status nor route.
    const authLost = () => {
      if (shouldWriteSessionEnded(status, path)) {
        writeNotice(storage, sessionEndedNotice(null, 0));
        writes += 1;
      }
      status = "signedOut";
    };
    authLost();
    path = "/login?next=%2Fmy"; // the existing redirect for a signed-out visitor on a private page
    path = "/login";
    authLost();
    authLost();
    expect(writes).toBe(1);
    expect(consumeNotice(storage)).toEqual({ kind: "sessionEnded", sixHours: false });
    expect(consumeNotice(storage)).toBeNull();
  });
});

describe("notice copy", () => {
  const keys = Object.keys(en.notice).sort();

  it("has the same keys in English and Korean", () => {
    expect(Object.keys(ko.notice).sort()).toEqual(keys);
  });

  it("covers every message key the code can ask for", () => {
    const asked = [
      noticeMessage({ kind: "welcome", name: "A" }).key,
      noticeMessage({ kind: "welcome", name: "" }).key,
      noticeMessage({ kind: "loggedOut" }).key,
      noticeMessage({ kind: "sessionEnded", sixHours: true }).key,
      noticeMessage({ kind: "sessionEnded", sixHours: false }).key,
    ];
    for (const key of asked) expect(keys).toContain(key);
    expect(keys).toContain("close");
  });

  it("has no particle markers in Korean, and the exact approved lines", () => {
    for (const text of Object.values(ko.notice)) expect(text).not.toMatch(/[가-힣]\([가-힣]\)/);
    expect(ko.notice.welcome).toBe("{name}님, 다시 오신 것을 환영합니다.");
    expect(ko.notice.loggedOut).toBe("로그아웃되었습니다.");
    expect(ko.notice.sessionEnded).toBe("세션이 끝났습니다. 다시 로그인해 주세요.");
    expect(en.notice.welcome).toBe("Welcome back, {name}.");
    expect(en.notice.sessionEnded).toBe("Your session ended. Please log in again.");
  });

  it("has the same placeholders in both languages", () => {
    const names = (text: string) => [...text.matchAll(/\{(\w+)/g)].map((match) => match[1]).sort();
    for (const key of keys) expect(names(ko.notice[key as keyof typeof ko.notice]), key).toEqual(names(en.notice[key as keyof typeof en.notice]));
  });
});
