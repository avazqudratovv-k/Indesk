import Image from "next/image";
import { useTranslations } from "next-intl";
import { agentBuilt, agentIds } from "@/components/home/agents";
import styles from "./TeamReady.module.css";

// The strip shows the agents that will work on the attached file: Owl, Beaver and Cat for a CSV (also with nothing
// attached), Owl, Hound and Cat for a PDF. Chameleon is not built yet.
export default function TeamReady({ withHound = false }: { withHound?: boolean }) {
  const t = useTranslations("workspace");
  const home = useTranslations("home.team");
  return (
    <section className={styles.ready}>
      <div className={styles.title}>{t("ready")}</div>
      <ul className={styles.team}>
        {agentIds.filter((id) => agentBuilt[id] && (id === "hound" ? withHound : id !== "beaver" || !withHound)).map((id) => (
          <li key={id} className={styles.agent}>
            <Image src={`/workspace/agent-${id}.png`} alt="" width={48} height={48} />
            {home(`${id}.name`)}
          </li>
        ))}
      </ul>
    </section>
  );
}
