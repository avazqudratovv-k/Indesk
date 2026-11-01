import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import RecoveryPage from "@/components/auth/RecoveryPage";
import VerifyEmail from "@/components/auth/VerifyEmail";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("verify.page");
  return { title: `${t("title")} · Indesk`, robots: { index: false } };
}

export default function Page() {
  return (
    <RecoveryPage>
      <VerifyEmail />
    </RecoveryPage>
  );
}
