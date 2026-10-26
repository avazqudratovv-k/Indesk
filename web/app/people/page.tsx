import RequireAuth from "@/components/auth/RequireAuth";
import RoutePlaceholder from "@/components/RoutePlaceholder";

export default function Page() {
  return (
    <RequireAuth>
      <RoutePlaceholder route="People" />
    </RequireAuth>
  );
}
