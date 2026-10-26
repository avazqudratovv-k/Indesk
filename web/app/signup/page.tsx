import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import AuthPage from "@/components/auth/AuthPage";
import { safeNext } from "@/lib/auth/safe-next";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("auth");
  return { title: `${t("tabSignup")} · Indesk` };
}

export default async function Page({ searchParams }: { searchParams: Promise<{ next?: string | string[] }> }) {
  const { next } = await searchParams;
  return <AuthPage mode="signup" next={safeNext(next)} />;
}
