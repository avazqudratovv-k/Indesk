import { getTranslations } from "next-intl/server";
import Card from "@/components/ui/Card";
import Chip, { type ChipTone } from "@/components/ui/Chip";
import { getSession } from "@/lib/session-server";
import type { ClaimStatus } from "@/lib/types";
import { getMockClaims, getMockReport, getMockShareLink, getShareLinkState, listMockDiscoverablePeople, listMockUploads } from "@/mocks";
import styles from "./page.module.css";

const statusTone: Record<ClaimStatus, ChipTone> = { verified: "ok", flagged: "warn", unverified: "warn", mismatch: "bad" };

// Dev-only page for ROADMAP 1.7. Hidden in production by app/dev/layout.tsx.
export default async function MockPage() {
  const t = await getTranslations("dev.mock");
  const session = await getSession();
  const report = getMockReport("rep_01");
  const check = getMockReport("rep_02");
  const checkClaims = getMockClaims("rep_02");
  const uploads = listMockUploads("u_01");
  const people = listMockDiscoverablePeople();
  const links = ["rep_01", "rep_02"].map((id) => getMockShareLink(id)).filter((link) => link !== undefined);

  return (
    <main className={styles.page}>
      <h1 className={styles.h1}>{t("title")}</h1>
      <p className={styles.lede}>{t("lede")}</p>

      <h2 className={styles.h2}>{t("session")}</h2>
      <p className={styles.mono}>{session.signedIn ? `${t("signedIn")}: ${session.user.display_name} (${session.user.id})` : t("signedOut")}</p>

      <h2 className={styles.h2}>{t("report")}</h2>
      {report ? <pre className={styles.pre}>{JSON.stringify(report, null, 2)}</pre> : <p>{t("notFound")}</p>}

      <h2 className={styles.h2}>{t("check")}</h2>
      {check ? (
        <Card>
          <p>{check.title}</p>
          <ul className={styles.list}>
            {checkClaims.map((claim) => (
              <li key={claim.id} className={styles.claim}>
                <Chip tone={statusTone[claim.status]}>{claim.status}</Chip>
                <span>{claim.text}</span>
                <span className={styles.mono}>
                  {claim.id}
                  {claim.doc_value !== null ? ` · doc ${claim.doc_value} vs computed ${claim.computed_value}` : ""}
                </span>
              </li>
            ))}
          </ul>
        </Card>
      ) : (
        <p>{t("notFound")}</p>
      )}

      <h2 className={styles.h2}>{t("uploads")}</h2>
      <ul className={styles.list}>
        {uploads.map((upload) => (
          <li key={upload.id} className={styles.mono}>
            {upload.id} · {upload.filename} · {upload.status}
          </li>
        ))}
      </ul>

      <h2 className={styles.h2}>{t("shareLinks")}</h2>
      <ul className={styles.list}>
        {links.map((link) => (
          <li key={link.id} className={styles.mono}>
            {link.id} · {link.report_id} · {getShareLinkState(link)}
          </li>
        ))}
      </ul>

      <h2 className={styles.h2}>{t("people")}</h2>
      <ul className={styles.list}>
        {people.map((person) => (
          <li key={person.id} className={styles.mono}>
            {person.display_name} @{person.handle}
          </li>
        ))}
      </ul>
    </main>
  );
}
