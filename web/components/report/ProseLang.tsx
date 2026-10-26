"use client";

import { createContext, useContext, type ReactNode } from "react";

// The language the report's own prose is written in, when it is known. Labels and buttons follow the site language; the
// prose (title, answer, claims, notes) carries its own `lang` so screen readers and fonts treat it right. A mock report
// follows the site language and sets nothing.
const ProseLangContext = createContext<string | undefined>(undefined);

export function ProseLangProvider({ lang, children }: { lang: string | undefined; children: ReactNode }) {
  return <ProseLangContext.Provider value={lang}>{children}</ProseLangContext.Provider>;
}

export function useProseLang(): string | undefined {
  return useContext(ProseLangContext);
}
