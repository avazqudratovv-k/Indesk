import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import AuthPage from "@/components/auth/AuthPage";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("auth");
  return { title: `${t("tabSignup")} · Indesk` };
}

export default function Page() {
  return <AuthPage mode="signup" />;
}
