import { notFound } from "next/navigation";
import RoutePlaceholder from "@/components/RoutePlaceholder";
import { isBuilt } from "@/components/layout/nav-items";

// Not built yet: the page answers 404 until "/s" leaves hiddenPages in nav-items.ts.
export default function Page() {
  if (!isBuilt("/s")) notFound();
  return <RoutePlaceholder route="Shared report" />;
}
