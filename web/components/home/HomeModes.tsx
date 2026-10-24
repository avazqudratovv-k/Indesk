import Link from "next/link";
import { useTranslations } from "next-intl";
import Card from "@/components/ui/Card";
import HomeSection from "./HomeSection";
import { workspaceHref } from "./agents";
import styles from "./HomeModes.module.css";

const modes = ["ask", "check", "compare"] as const;

function ModeIcon({ mode }: { mode: (typeof modes)[number] }) {
  const common = { fill: "none", stroke: "currentColor", strokeWidth: 2, strokeLinecap: "round", strokeLinejoin: "round" } as const;
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" aria-hidden="true" focusable="false" {...common}>
      {mode === "ask" ? (
        <>
          <rect x="3" y="4" width="18" height="16" rx="2" />
          <path d="M3 10h18M9 4v16" />
        </>
      ) : mode === "check" ? (
        <>
          <path d="M6 3h9l4 4v14H6z" />
          <path d="M9 14l2.2 2.2L15.5 12" />
        </>
      ) : (
        <>
          <rect x="3" y="5" width="7" height="14" rx="1.5" />
          <rect x="14" y="5" width="7" height="14" rx="1.5" />
          <path d="M10 12h4" />
        </>
      )}
    </svg>
  );
}

export default function HomeModes() {
  const t = useTranslations("home.modes");
  return (
    <HomeSection id="modes" title={t("title")} sub={t("sub")}>
      <ul className={styles.grid}>
        {modes.map((mode) => (
          <Card as="li" key={mode} className={styles.card}>
            <span className={styles.icon}>
              <ModeIcon mode={mode} />
            </span>
            <h3 className={styles.name}>{t(`${mode}.title`)}</h3>
            <p className={styles.body}>{t(`${mode}.body`)}</p>
            <p className={styles.example}>{t(`${mode}.example`)}</p>
            {/* The Workspace may read ?mode later; nothing reads it yet. */}
            <Link className={styles.link} href={`${workspaceHref}?mode=${mode}`}>
              {t("open")} <span aria-hidden="true">→</span>
            </Link>
          </Card>
        ))}
      </ul>
    </HomeSection>
  );
}
