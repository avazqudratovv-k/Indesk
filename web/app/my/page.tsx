import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import RequireAuth from "@/components/auth/RequireAuth";
import MyView from "@/components/my/MyView";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("my");
  return { title: `${t("title")} · Indesk` };
}

export default function Page() {
  return (
    <RequireAuth>
      <MyView />
    </RequireAuth>
  );
}
