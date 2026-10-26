"use client";

import { useCallback, useState } from "react";
import {
  checkFile,
  kindOf,
  MODE_SLOTS,
  type FileError,
  type SlotFile,
  type SlotId,
  type WorkspaceMode,
} from "@/lib/workspace/validate";

type Slots = Record<SlotId, SlotFile[]>;
type Errors = Record<SlotId, FileError[]>;

const emptySlots = (): Slots => ({ files: [], document: [], sources: [], fileA: [], fileB: [] });
const emptyErrors = (): Errors => ({ files: [], document: [], sources: [], fileA: [], fileB: [] });

let nextId = 0;

export type AddResult = { added: string[]; rejected: number };

// The files a user adds live only in this component's state: no upload, no network, no storage.
// Nothing here reads file contents, so there are no object URLs to revoke; state is dropped on unmount.
export function useWorkspaceFiles(mode: WorkspaceMode) {
  const [slots, setSlots] = useState<Slots>(emptySlots);
  const [errors, setErrors] = useState<Errors>(emptyErrors);

  const add = useCallback(
    (slot: SlotId, incoming: File[]): AddResult => {
      const modeSlots = MODE_SLOTS[mode];
      const taken = new Set<string>();
      for (const id of modeSlots) for (const item of slots[id]) taken.add(item.file.name.toLowerCase());
      const kindOfOther = (other: SlotId) => slots[other][0]?.kind ?? null;
      const partner: SlotId | null = slot === "fileA" ? "fileB" : slot === "fileB" ? "fileA" : null;
      const partnerKind = partner ? kindOfOther(partner) : null;

      const accepted: SlotFile[] = [];
      const found: FileError[] = [];
      for (const file of incoming) {
        const code = checkFile(file, { slot, takenNames: taken, count: slots[slot].length + accepted.length, partnerKind, csvOnly: mode === "ask" });
        if (code) {
          found.push({ code, name: file.name });
          continue;
        }
        const kind = kindOf(file);
        if (!kind) continue;
        taken.add(file.name.toLowerCase());
        accepted.push({ id: `f${nextId++}`, file, kind });
      }
      setSlots((value) => ({ ...value, [slot]: [...value[slot], ...accepted] }));
      setErrors((value) => ({ ...value, [slot]: found }));
      return { added: accepted.map((item) => item.file.name), rejected: found.length };
    },
    [mode, slots],
  );

  const remove = useCallback((slot: SlotId, id: string) => {
    setSlots((value) => ({ ...value, [slot]: value[slot].filter((item) => item.id !== id) }));
    setErrors((value) => ({ ...value, [slot]: [] }));
  }, []);

  const clearErrors = useCallback((slot: SlotId) => setErrors((value) => ({ ...value, [slot]: [] })), []);

  return { slots, errors, add, remove, clearErrors };
}
