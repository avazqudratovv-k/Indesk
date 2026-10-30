import { useTranslations } from "next-intl";
import Card from "@/components/ui/Card";
import Chip from "@/components/ui/Chip";
import HomeSection from "./HomeSection";
import PlateMark from "./PlateMark";
import { agentBuilt, agentColor, agentIds, agentPlate, type AgentId } from "./agents";

// Only the built agents have a tag (the others show the "Not available yet" chip).
type BuiltAgentId = Exclude<AgentId, "chameleon">;
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
            {agentBuilt[id] ? (
              <span className={styles.tag}>{t(`${id as BuiltAgentId}.tag`)}</span>
            ) : (
              <span className={styles.later}>
                <Chip tone="soon">{t("comingLater")}</Chip>
              </span>
            )}
            <p className={styles.see}>
              <b>{t(agentBuilt[id] ? "seeLabel" : "seeLabelLater")}</b> {t(`${id}.see`)}
            </p>
          </Card>
        ))}
      </ul>
    </HomeSection>
  );
}
