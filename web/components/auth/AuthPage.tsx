import AuthForm from "./AuthForm";
import AuthSide from "./AuthSide";
import type { AuthMode } from "./validate";
import styles from "./AuthPage.module.css";

// Log in and Sign up share one board: form card, then the "included for free" panel (below it on phones).
export default function AuthPage({ mode }: { mode: AuthMode }) {
  return (
    <main className={styles.main}>
      <AuthForm mode={mode} />
      <AuthSide />
    </main>
  );
}
