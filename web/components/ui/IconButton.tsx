import type { ButtonHTMLAttributes, ReactNode } from "react";
import styles from "./IconButton.module.css";

type IconButtonProps = Omit<ButtonHTMLAttributes<HTMLButtonElement>, "aria-label" | "children"> & {
  "aria-label": string;
  children: ReactNode;
};

export default function IconButton({ className, type = "button", children, ...rest }: IconButtonProps) {
  return (
    <button type={type} className={[styles.iconBtn, className ?? ""].filter(Boolean).join(" ")} {...rest}>
      {children}
    </button>
  );
}
