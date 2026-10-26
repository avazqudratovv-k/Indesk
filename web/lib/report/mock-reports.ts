import { EXAMPLE_ID, isRealReportId } from "./real/id";

// The mock reports (rep_01 ...) are dev data, not product: a production build never serves them.
// Same rule as app/dev/layout.tsx. "example" and real UUID reports do not go through this check.
export const mockReportsEnabled = (nodeEnv: string | undefined = process.env.NODE_ENV): boolean => nodeEnv !== "production";

// Whether /reports/{id} may be served at all. The reports layout asks this before anything streams: the page sits
// behind loading.tsx, so a notFound() thrown inside it would already have sent status 200.
export function reportIdServed(id: string, nodeEnv: string | undefined = process.env.NODE_ENV): boolean {
  return id === EXAMPLE_ID || isRealReportId(id) || mockReportsEnabled(nodeEnv);
}
