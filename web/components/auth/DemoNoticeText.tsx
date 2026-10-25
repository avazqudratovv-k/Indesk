import { useTranslations } from "next-intl";

// The demo notice as plain small text, the way the board shows it under the side cards.
export function DemoNoticeText({ className }: { className?: string }) {
  const t = useTranslations("demoNotice");
  return <p className={className}>{t("text")}</p>;
}
