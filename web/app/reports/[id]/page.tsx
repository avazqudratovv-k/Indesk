import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getLocale, getTranslations } from "next-intl/server";
import RoutePlaceholder from "@/components/RoutePlaceholder";
import RealReport from "@/components/report/RealReport";
import ReportView from "@/components/report/ReportView";
import { defaultLocale, isLocale } from "@/i18n/config";
import { getReport } from "@/lib/report/get-report";
import { isRealReportId } from "@/lib/report/real/id";

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

// A UUID is a real report (ROADMAP 4.4): the browser loads it from the API with the person's session. Any other id is
// looked up among the mock reports (2.7: the example). Check and Compare reports (2.10, 2.11) keep the placeholder.
export default async function Page({ params }: Props) {
  const { id } = await params;
  if (isRealReportId(id)) return <RealReport id={id} />;
  const bundle = await getReport(id, await currentLocale());
  if (!bundle) notFound();
  if (bundle.report.mode !== "ask") return <RoutePlaceholder route="Report" param={id} />;
  return <ReportView bundle={bundle} />;
}
