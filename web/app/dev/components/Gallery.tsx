"use client";

import { useTranslations } from "next-intl";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import Chip from "@/components/ui/Chip";
import DemoNotice from "@/components/ui/DemoNotice";
import Eyebrow from "@/components/ui/Eyebrow";
import IconButton from "@/components/ui/IconButton";
import styles from "./page.module.css";

const stroke = { fill: "none", stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round", strokeLinejoin: "round" } as const;

function StarIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true" {...stroke}>
      <path d="M12 3l2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1L3.2 9.5l6.1-.9z" />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true" {...stroke}>
      <path d="M6 6l12 12M18 6L6 18" />
    </svg>
  );
}

function noop() {}

export default function Gallery({ title, theme }: { title: string; theme: "light" | "dark" }) {
  const t = useTranslations("ui");
  const d = useTranslations("dev.components");
  return (
    <section className={styles.panel} data-theme={theme} aria-label={title}>
      <h2 className={styles.h2}>{title}</h2>

      <div className={styles.section}>
        <h3 className={styles.h3}>{d("buttons")}</h3>
        <div className={styles.row}>
          <Button>{t("button.default")}</Button>
          <Button variant="ink">{t("button.ink")}</Button>
          <Button variant="primary">{t("button.primary")}</Button>
          <Button href="/workspace">{t("button.link")}</Button>
          <Button disabled>{t("button.disabled")}</Button>
        </div>
      </div>

      <div className={styles.section}>
        <h3 className={styles.h3}>{d("sizes")}</h3>
        <div className={styles.row}>
          <Button size="sm">{t("button.default")}</Button>
          <Button>{t("button.default")}</Button>
          <Button size="lg">{t("button.default")}</Button>
          <Button size="sm" variant="ink">{t("button.ink")}</Button>
          <Button size="lg" variant="primary">{t("button.primary")}</Button>
        </div>
      </div>

      <div className={styles.section}>
        <h3 className={styles.h3}>{d("iconButtons")}</h3>
        <div className={styles.row}>
          <IconButton aria-label={t("iconButton.star")}>
            <StarIcon />
          </IconButton>
          <IconButton aria-label={t("iconButton.close")}>
            <CloseIcon />
          </IconButton>
        </div>
      </div>

      <div className={styles.section}>
        <h3 className={styles.h3}>{d("eyebrow")}</h3>
        <Eyebrow>{t("eyebrow.example")}</Eyebrow>
      </div>

      <div className={styles.section}>
        <h3 className={styles.h3}>{d("card")}</h3>
        <Card>
          <h4 className={styles.cardTitle}>{t("card.title")}</h4>
          <p className={styles.cardBody}>{t("card.body")}</p>
        </Card>
      </div>

      <div className={styles.section}>
        <h3 className={styles.h3}>{d("chips")}</h3>
        <div className={styles.row}>
          <Chip>{t("chip.neutral")}</Chip>
          <Chip tone="accent">{t("chip.accent")}</Chip>
          <Chip tone="ok">{t("chip.ok")}</Chip>
          <Chip tone="bad">{t("chip.bad")}</Chip>
          <Chip tone="warn">{t("chip.warn")}</Chip>
          <Chip onClick={noop}>{t("chip.neutral")}</Chip>
        </div>
      </div>

      <div className={styles.section}>
        <h3 className={styles.h3}>{d("demoNotice")}</h3>
        <DemoNotice />
      </div>
    </section>
  );
}
