import type { ReactNode } from "react";
import styles from "./Card.module.css";

type CardProps = {
  as?: "div" | "section" | "article" | "li";
  flat?: boolean;
  className?: string;
  children: ReactNode;
};

export default function Card({ as: Tag = "div", flat = false, className, children }: CardProps) {
  return <Tag className={[styles.card, flat ? styles.flat : "", className ?? ""].filter(Boolean).join(" ")}>{children}</Tag>;
}
