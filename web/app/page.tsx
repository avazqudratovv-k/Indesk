import HomeClosing from "@/components/home/HomeClosing";
import HomeHero from "@/components/home/HomeHero";
import HomeMarquee from "@/components/home/HomeMarquee";
import HomeModes from "@/components/home/HomeModes";
import HomeTeam from "@/components/home/HomeTeam";
import HomeTrust from "@/components/home/HomeTrust";
import HomeWho from "@/components/home/HomeWho";
import { getSession } from "@/lib/session-server";
import { getMockReport } from "@/mocks";

export default async function Page() {
  // PLACEHOLDER numbers for the demo film (verified / total on the stamp) come from the mock Ask report (rep_01).
  const report = getMockReport("rep_01");
  if (!report) throw new Error("mock report rep_01 is missing");
  const session = await getSession();
  return (
    <main>
      <HomeHero verified={report.verified_count} total={report.total_claims} signedIn={session.signedIn} />
      <HomeMarquee />
      <HomeModes />
      <HomeTeam />
      <HomeWho />
      <HomeTrust />
      <HomeClosing />
    </main>
  );
}
