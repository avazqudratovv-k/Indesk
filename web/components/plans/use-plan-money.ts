"use client";

import { useLocale } from "next-intl";
import { formatMoney } from "@/lib/plans/format";

// Every price on the Plans screen goes through this, so all of it is shown in won.
export function usePlanMoney() {
  const locale = useLocale();
  return { money: (amount: number) => formatMoney(amount, locale) };
}
