import RequireAuth from "@/components/auth/RequireAuth";
import { notFound } from "next/navigation";
import RoutePlaceholder from "@/components/RoutePlaceholder";
import { isBuilt } from "@/components/layout/nav-items";

// Not built yet: the page answers 404 until its flag in nav-items.ts is true.
export default function Page() {
  if (!isBuilt("/people")) notFound();
  return (
    <RequireAuth>
      <RoutePlaceholder route="People" />
    </RequireAuth>
  );
}
