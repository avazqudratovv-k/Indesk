import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import PlansView from "@/components/plans/PlansView";
import { getMockCustomPlanOffer, listMockPlanOffers } from "@/mocks";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("plans");
  return { title: `${t("title")} · Indesk` };
}

export default function Page() {
  return <PlansView offers={listMockPlanOffers()} custom={getMockCustomPlanOffer()} />;
}
