import type { ReactNode } from "react";
import { useTranslations } from "next-intl";
import styles from "./ArtifactPane.module.css";

// One pane of an agent's work. Every pane carries the small "Example" stamp in its top corner: the content is the
// scripted demo, not a result from the user's files.
// `code` is the dark code pane (Beaver): it sets its own text colours, see the module.
export default function ArtifactPane({ children, className = "", code = false }: { children: ReactNode; className?: string; code?: boolean }) {
  const t = useTranslations("workspace");
  return (
    <div className={`${styles.pane} ${code ? styles.code : ""} ${className}`}>
      <span className={styles.stamp}>{t("live.tilesTag.example")}</span>
      {children}
    </div>
  );
}
