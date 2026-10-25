import { useTranslations } from "next-intl";
import Card from "@/components/ui/Card";
import HomeSection from "./HomeSection";
import PlateMark from "./PlateMark";
import { agentColor, agentIds, agentPlate, type AgentId } from "./agents";
import styles from "./HomeTeam.module.css";

export default function HomeTeam() {
  const t = useTranslations("home.team");
  return (
    <HomeSection id="team" title={t("title")} sub={t("sub")}>
      <ul className={styles.grid}>
        {agentIds.map((id: AgentId) => (
          <Card as="li" key={id} className={styles.card}>
            <PlateMark agent={id} color={agentColor[id]} label={t("plate", { n: agentPlate[id] })} />
            <h3 className={styles.name}>
              {t(`${id}.name`)} · {t(`${id}.role`)}
            </h3>
            <p className={styles.desc}>{t(`${id}.desc`)}</p>
            <span className={styles.tag}>{t(`${id}.tag`)}</span>
            <p className={styles.see}>
              <b>{t("seeLabel")}</b> {t(`${id}.see`)}
            </p>
          </Card>
        ))}
      </ul>
    </HomeSection>
  );
}
