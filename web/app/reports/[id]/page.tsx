import RoutePlaceholder from "@/components/RoutePlaceholder";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <RoutePlaceholder route="Report" param={id} />;
}
