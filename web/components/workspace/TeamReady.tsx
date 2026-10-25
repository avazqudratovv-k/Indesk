import Image from "next/image";
import { useTranslations } from "next-intl";
import { agentIds } from "@/components/home/agents";
import styles from "./TeamReady.module.css";

export default function TeamReady() {
  const t = useTranslations("workspace");
  const home = useTranslations("home.team");
  return (
    <section className={styles.ready}>
      <div className={styles.title}>{t("ready")}</div>
      <ul className={styles.team}>
        {agentIds.map((id) => (
          <li key={id} className={styles.agent}>
            <Image src={`/workspace/agent-${id}.png`} alt="" width={48} height={48} />
            {home(`${id}.name`)}
          </li>
        ))}
      </ul>
    </section>
  );
}
