import { notFound } from "next/navigation";
import { reportIdServed } from "@/lib/report/mock-reports";

// A layout runs before loading.tsx streams the page, so a mock id (rep_01 ...) gets a real 404 status in a production
// build. The public example and real (UUID) reports are never affected. See lib/report/mock-reports.ts.
export default async function ReportLayout({ children, params }: { children: React.ReactNode; params: Promise<{ id: string }> }) {
  const { id } = await params;
  if (!reportIdServed(id)) notFound();
  return children;
}
