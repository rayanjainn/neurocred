"use client";

import { useContext } from "react";
import { VoiceControlContext } from "@/src/voice/VoiceControlProvider";

export function useVoiceControl() {
  const ctx = useContext(VoiceControlContext);

  if (!ctx) {
    throw new Error("useVoiceControl must be used within VoiceControlProvider");
  }

  return ctx;
}
