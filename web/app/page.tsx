import HomeClosing from "@/components/home/HomeClosing";
import HomeHero from "@/components/home/HomeHero";
import HomeMarquee from "@/components/home/HomeMarquee";
import HomeModes from "@/components/home/HomeModes";
import HomeTeam from "@/components/home/HomeTeam";
import HomeTrust from "@/components/home/HomeTrust";
import HomeWho from "@/components/home/HomeWho";

export default function Page() {
  return (
    <main>
      <HomeHero />
      <HomeMarquee />
      <HomeModes />
      <HomeTeam />
      <HomeWho />
      <HomeTrust />
      <HomeClosing />
    </main>
  );
}
