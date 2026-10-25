import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import WorkspaceView from "@/components/workspace/WorkspaceView";
import { listMockPlanOffers } from "@/mocks";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("nav");
  return { title: `${t("workspace")} · Indesk` };
}

export default function Page() {
  return <WorkspaceView offers={listMockPlanOffers()} />;
}
