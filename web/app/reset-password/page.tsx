import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import ResetForm from "@/components/auth/ResetForm";
import RecoveryPage from "@/components/auth/RecoveryPage";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("recovery");
  return { title: `${t("reset.title")} · Indesk`, robots: { index: false } };
}

export default function Page() {
  return (
    <RecoveryPage>
      <ResetForm />
    </RecoveryPage>
  );
}
