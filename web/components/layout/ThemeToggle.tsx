"use client";

import { useTranslations } from "next-intl";
import IconButton from "@/components/ui/IconButton";
import { useTheme } from "@/hooks/use-theme";
import { MoonIcon, SunIcon } from "./icons";

export default function ThemeToggle() {
  const t = useTranslations("theme");
  const { theme, setTheme } = useTheme();
  const dark = theme === "dark";
  return (
    <IconButton aria-label={t("dark")} aria-pressed={dark} onClick={() => setTheme(dark ? "light" : "dark")}>
      {dark ? <SunIcon /> : <MoonIcon />}
    </IconButton>
  );
}
