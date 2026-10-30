"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import type { ApiErrorCode } from "@/lib/api/errors";
import { confirmDelete } from "@/lib/my/delete-flow";
import Button from "@/components/ui/Button";
import styles from "./my.module.css";

type Labels = { delete: string; confirm: string; cancel: string; confirmDelete: string; deleting: string };

// A Delete button that asks first, inline: "Delete this ...? Cancel / Delete". `run` does the delete; a failure shows the
// translated reason under the row and leaves the button usable. `onDone` runs only after the server said yes.
export default function ConfirmDelete({ labels, run, onDone }: { labels: Labels; run: () => Promise<void>; onDone: () => void }) {
  const tApi = useTranslations("apiErrors");
  const [step, setStep] = useState<"idle" | "confirm" | "busy">("idle");
  const [error, setError] = useState<ApiErrorCode | null>(null);

  async function confirm() {
    setStep("busy");
    setError(null);
    const result = await confirmDelete(run);
    if (result.ok) {
      onDone();
      return;
    }
    setError(result.key);
    setStep("idle");
  }

  return (
    <div className={styles.confirmBox}>
      {step === "idle" ? (
        <Button size="sm" className={styles.danger} onClick={() => setStep("confirm")}>
          {labels.delete}
        </Button>
      ) : (
        <div className={styles.confirm} role="group" aria-label={labels.confirm}>
          <span className={styles.confirmText}>{labels.confirm}</span>
          <Button size="sm" onClick={() => setStep("idle")} disabled={step === "busy"}>
            {labels.cancel}
          </Button>
          <Button size="sm" className={styles.dangerSolid} onClick={confirm} disabled={step === "busy"}>
            {step === "busy" ? labels.deleting : labels.confirmDelete}
          </Button>
        </div>
      )}
      {error ? (
        <p className={styles.rowError} role="alert">
          {tApi(error)}
        </p>
      ) : null}
    </div>
  );
}
