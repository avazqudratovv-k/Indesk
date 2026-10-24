import Link from "next/link";
import type { ButtonHTMLAttributes, ReactNode } from "react";
import styles from "./Button.module.css";

export type ButtonVariant = "default" | "ink" | "primary";
export type ButtonSize = "sm" | "default" | "lg";

type CommonProps = {
  variant?: ButtonVariant;
  size?: ButtonSize;
  className?: string;
  children: ReactNode;
};

type ButtonAsButton = CommonProps & { href?: undefined } & Omit<ButtonHTMLAttributes<HTMLButtonElement>, "className" | "children">;
type ButtonAsLink = CommonProps & { href: string; disabled?: boolean; onClick?: () => void };

export type ButtonProps = ButtonAsButton | ButtonAsLink;

function classNames({ variant = "default", size = "default", className }: CommonProps) {
  return [
    styles.btn,
    variant === "default" ? "" : styles[variant],
    size === "default" ? "" : styles[size],
    className ?? "",
  ]
    .filter(Boolean)
    .join(" ");
}

export default function Button(props: ButtonProps) {
  if (props.href !== undefined) {
    const { href, disabled, onClick, children } = props;
    return (
      <Link
        href={href}
        className={classNames(props)}
        aria-disabled={disabled ? true : undefined}
        tabIndex={disabled ? -1 : undefined}
        onClick={onClick}
      >
        {children}
      </Link>
    );
  }
  // eslint-disable-next-line @typescript-eslint/no-unused-vars -- picked out so they don't reach the DOM
  const { variant, size, className, children, type = "button", ...rest } = props;
  return (
    <button type={type} className={classNames(props)} {...rest}>
      {children}
    </button>
  );
}
