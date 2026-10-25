import { useTranslations } from "next-intl";
import styles from "./StepList.module.css";

export type StepState = "done" | "todo" | "notReached";
export type StepItem = { id: string; text: string; state: StepState };

// A numbered checklist: a step shows a check once it is done, its number until then. A step still open when the run
// has ended can never run, so it reads "Not reached" (text and a dashed dash mark, not colour alone). Owl's plan and
// Hound's retrieval steps use it. The state is also written for assistive tech, not only drawn.
export default function StepList({ items }: { items: StepItem[] }) {
  const t = useTranslations("workspace");
  return (
    <ol className={styles.list}>
      {items.map((item, index) => (
        <li key={item.id} className={`${styles.item} ${styles[item.state]}`}>
          <span className={styles.mark} aria-hidden="true">
            {item.state === "done" ? "✓" : item.state === "notReached" ? "–" : index + 1}
          </span>
          <span>
            {item.text}
            {item.state === "notReached" ? (
              <span className={styles.tag}>{t("artifacts.owl.notReached")}</span>
            ) : (
              <span className={styles.srOnly}> ({item.state === "done" ? t("artifacts.owl.done") : t("artifacts.owl.todo")})</span>
            )}
          </span>
        </li>
      ))}
    </ol>
  );
}
