import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import WorkspaceView from "@/components/workspace/WorkspaceView";
import { isRunScenario } from "@/lib/run/mock-run";
import { listMockPlanOffers } from "@/mocks";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("nav");
  return { title: `${t("workspace")} · Indesk` };
}

// ?mockOutcome=answered|failed|partial switches the run tab to the scripted demo. It is read in development only and ignored in production.
export default async function Page({ searchParams }: { searchParams: Promise<{ mockOutcome?: string | string[] }> }) {
  const { mockOutcome } = await searchParams;
  const scenario = process.env.NODE_ENV === "development" && isRunScenario(mockOutcome) ? mockOutcome : undefined;
  return <WorkspaceView offers={listMockPlanOffers()} mockOutcome={scenario} />;
}
