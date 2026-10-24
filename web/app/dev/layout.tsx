import { notFound } from "next/navigation";

// Dev-only pages (token swatches, component gallery, mock data) are not available in production builds.
export default function DevLayout({ children }: { children: React.ReactNode }) {
  if (process.env.NODE_ENV === "production") notFound();
  return children;
}
