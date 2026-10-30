import Image from "next/image";
import { useTranslations } from "next-intl";
import { agentBuilt, agentIds } from "@/components/home/agents";
import styles from "./TeamReady.module.css";

// Hound joins the strip only when a PDF is attached: it searches documents and has nothing to do on a CSV.
export default function TeamReady({ withHound = false }: { withHound?: boolean }) {
  const t = useTranslations("workspace");
  const home = useTranslations("home.team");
  return (
    <section className={styles.ready}>
      <div className={styles.title}>{t("ready")}</div>
      <ul className={styles.team}>
        {agentIds.filter((id) => agentBuilt[id] && (id !== "hound" || withHound)).map((id) => (
          <li key={id} className={styles.agent}>
            <Image src={`/workspace/agent-${id}.png`} alt="" width={48} height={48} />
            {home(`${id}.name`)}
          </li>
        ))}
      </ul>
    </section>
  );
}
