import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getLocale, getTranslations } from "next-intl/server";
import RoutePlaceholder from "@/components/RoutePlaceholder";
import ReportView from "@/components/report/ReportView";
import { defaultLocale, isLocale } from "@/i18n/config";
import { getReport } from "@/lib/report/get-report";

type Props = { params: Promise<{ id: string }> };

async function currentLocale() {
  const locale = await getLocale();
  return isLocale(locale) ? locale : defaultLocale;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { id } = await params;
  const [t, bundle] = await Promise.all([getTranslations("report"), currentLocale().then((locale) => getReport(id, locale))]);
  return { title: `${bundle?.report.title ?? t("title")} · Indesk` };
}

// ROADMAP 2.7: Ask reports. Check and Compare reports (2.10, 2.11) keep the placeholder until they are built.
export default async function Page({ params }: Props) {
  const { id } = await params;
  const bundle = await getReport(id, await currentLocale());
  if (!bundle) notFound();
  if (bundle.report.mode !== "ask") return <RoutePlaceholder route="Report" param={id} />;
  return <ReportView bundle={bundle} />;
}
