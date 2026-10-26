import type { ButtonHTMLAttributes, ReactNode } from "react";
import styles from "./Chip.module.css";

export type ChipTone = "neutral" | "accent" | "ok" | "bad" | "warn" | "soon";

type StaticProps = { tone?: ChipTone; onClick?: undefined; children: ReactNode };
type ButtonProps = { tone?: ChipTone; children: ReactNode } & Omit<ButtonHTMLAttributes<HTMLButtonElement>, "className" | "children"> & {
    onClick: NonNullable<ButtonHTMLAttributes<HTMLButtonElement>["onClick"]>;
  };

function toneClass(tone: ChipTone) {
  return [styles.chip, tone === "neutral" ? "" : styles[tone]].filter(Boolean).join(" ");
}

// Without onClick it is a plain label (span); with onClick it is a real button.
export default function Chip(props: StaticProps | ButtonProps) {
  const tone = props.tone ?? "neutral";
  if (props.onClick === undefined) {
    return <span className={toneClass(tone)}>{props.children}</span>;
  }
  // eslint-disable-next-line @typescript-eslint/no-unused-vars -- tone is picked out so it doesn't reach the DOM
  const { tone: _tone, children, type = "button", ...rest } = props;
  return (
    <button type={type} className={toneClass(tone)} {...rest}>
      {children}
    </button>
  );
}
