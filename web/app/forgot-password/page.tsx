import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import ForgotForm from "@/components/auth/ForgotForm";
import RecoveryPage from "@/components/auth/RecoveryPage";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("recovery");
  return { title: `${t("forgot.title")} · Indesk`, robots: { index: false } };
}

export default function Page() {
  return (
    <RecoveryPage>
      <ForgotForm />
    </RecoveryPage>
  );
}
