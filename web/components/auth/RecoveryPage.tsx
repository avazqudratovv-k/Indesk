import type { ReactNode } from "react";
import AuthSide from "./AuthSide";
import styles from "./AuthPage.module.css";

// Forgot and reset share the log in board: form card, then the side panel.
export default function RecoveryPage({ children }: { children: ReactNode }) {
  return (
    <main className={styles.main}>
      {children}
      <AuthSide />
    </main>
  );
}
