import type { CSSProperties } from "react";
import { useTranslations } from "next-intl";
import Card from "@/components/ui/Card";
import Chip from "@/components/ui/Chip";
import AgentMark from "./AgentMark";
import HomeSection from "./HomeSection";
import { agentColor, agentIds, agentPlate, type AgentId } from "./agents";
import styles from "./HomeTeam.module.css";

type AgentStyle = CSSProperties & { "--agent": string };

export default function HomeTeam() {
  const t = useTranslations("home.team");
  return (
    <HomeSection id="team" title={t("title")} sub={t("sub")}>
      <ul className={styles.grid}>
        {agentIds.map((id: AgentId) => (
          <Card as="li" key={id} className={styles.card}>
            <div className={styles.plate} style={{ "--agent": agentColor[id] } as AgentStyle}>
              <AgentMark agent={id} size={64} />
              <span className={styles.plateLabel}>
                <i className={styles.plateDot} aria-hidden="true" />
                {t("plate", { n: agentPlate[id] })}
              </span>
            </div>
            <h3 className={styles.name}>
              {t(`${id}.name`)} <span className={styles.role}>· {t(`${id}.role`)}</span>
            </h3>
            <p className={styles.desc}>{t(`${id}.desc`)}</p>
            <div>
              <Chip>{t(`${id}.tag`)}</Chip>
            </div>
            <p className={styles.see}>
              <strong>{t("seeLabel")}</strong> {t(`${id}.see`)}
            </p>
          </Card>
        ))}
      </ul>
    </HomeSection>
  );
}
