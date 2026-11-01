"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";
import { ApiError, apiErrorKey, retryMinutes } from "@/lib/api/errors";
import { resendVerification } from "@/lib/auth/api";
import styles from "./ResendLink.module.css";

type State = { kind: "idle" } | { kind: "sending" } | { kind: "sent" } | { kind: "error"; error: ApiError };

// "Resend link" for the verification email, with its answer beside it. A 204 says only that a new link is on its way
// (it is also the answer for an already verified user and when the site's daily email cap is used up).
export default function ResendLink() {
  const t = useTranslations("verify.banner");
  const tApi = useTranslations("apiErrors");
  const [state, setState] = useState<State>({ kind: "idle" });

  async function onClick() {
    if (state.kind === "sending") return;
    setState({ kind: "sending" });
    try {
      await resendVerification();
      setState({ kind: "sent" });
    } catch (caught) {
      setState({ kind: "error", error: caught instanceof ApiError ? caught : new ApiError(0, "UNKNOWN") });
    }
  }

  const busy = state.kind === "sending";
  return (
    <span className={styles.wrap}>
      <button type="button" className={styles.button} onClick={() => void onClick()} disabled={busy} aria-busy={busy}>
        {busy ? t("resending") : t("resend")}
      </button>
      <span className={styles.answer} role="status">
        {state.kind === "sent" ? t("sent") : state.kind === "error" ? tApi(apiErrorKey(state.error), { minutes: retryMinutes(state.error) }) : null}
      </span>
    </span>
  );
}
