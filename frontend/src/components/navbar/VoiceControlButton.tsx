"use client";

import { Mic } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/dib/utils";
import { useVoiceControl } from "@/src/voice/useVoiceControl";

export function VoiceControlButton() {
  const { isListening, feedback, transcript, isSupported, toggleListening } =
    useVoiceControl();

  if (!isSupported) {
    return null;
  }

  const helperText = isListening
    ? "Listening..."
    : feedback || (transcript ? `Heard: ${transcript}` : "Click to speak");

  return (
    <div className="relative">
      <Button
        type="button"
        variant="ghost"
        size="icon"
        aria-label={isListening ? "Stop voice control" : "Start voice control"}
        title={isListening ? "Listening..." : "Click to speak"}
        onClick={toggleListening}
        className={cn(
          "rounded-full transition-all",
          isListening &&
            "bg-emerald-500/15 text-emerald-400 ring-1 ring-emerald-400/50 shadow-[0_0_20px_rgba(16,185,129,0.45)] animate-pulse",
        )}
      >
        <Mic className={cn("h-4.5 w-4.5", isListening && "scale-105")} />
      </Button>

      {(isListening || feedback || transcript) && (
        <div className="absolute right-0 top-11 z-[120] whitespace-nowrap rounded-md border border-border/80 bg-background/95 px-2 py-1 text-[11px] text-foreground shadow-lg backdrop-blur-sm">
          {helperText}
        </div>
      )}
    </div>
  );
}
