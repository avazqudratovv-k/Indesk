import HomeClosing from "@/components/home/HomeClosing";
import HomeHero from "@/components/home/HomeHero";
import HomeModes from "@/components/home/HomeModes";
import HomeTeam from "@/components/home/HomeTeam";
import { getMockReport } from "@/mocks";

export default function Page() {
  // PLACEHOLDER numbers for the demo animation come from the mock Ask report (rep_01).
  const report = getMockReport("rep_01");
  if (!report) throw new Error("mock report rep_01 is missing");
  return (
    <main>
      <HomeHero verified={report.verified_count} total={report.total_claims} />
      <HomeModes />
      <HomeTeam />
      <HomeClosing />
    </main>
  );
}
