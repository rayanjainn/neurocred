"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Loader2, Mic, PhoneCall } from "lucide-react";
import { cn } from "@/dib/utils";
import { TwinEnergyAura } from "@/components/TwinEnergyAura";
import { VoiceModal } from "@/components/voice/VoiceModal";
import { useToast } from "@/hooks/use-toast";
import { useAuth } from "@/dib/authContext";

import { voiceApi } from "@/dib/api";

const VOICE_PENDING_ACTION_KEY = "voice.pendingAction";

interface DigitalTwinCardProps {
  score?: any;
}

export function DigitalTwinCard({ score }: DigitalTwinCardProps) {
  const { user } = useAuth();
  const twin = {
    name: user?.name?.split(" ")[0] || "User",
    riskLevel: (score?.risk_band?.toLowerCase() as "low" | "medium" | "high") || "medium",
    liquidity: score?.liquidity_status || "MEDIUM",
    stability: score?.data_maturity_months ? Math.min(100, score.data_maturity_months * 8) : 82,
    suggestion: score?.top_reasons?.[0] || "You're doing great! Maintain current spending habits.",
    lastUpdated: "Just now",
  };

const RISK_STYLES = {
  low: {
    badge: "bg-lime-400/20 text-lime-300 border-lime-400/60",
    ring: "ring-lime-400/50",
    text: "LOW RISK",
  },
  medium: {
    badge: "bg-amber-400/20 text-amber-300 border-amber-400/60",
    ring: "ring-amber-400/50",
    text: "WARNING",
  },
  high: {
    badge: "bg-red-400/20 text-red-300 border-red-400/60",
    ring: "ring-red-400/50",
    text: "HIGH RISK",
  },
};

  const risk = RISK_STYLES[twin.riskLevel] || RISK_STYLES.medium;
  const [isVoiceModalOpen, setIsVoiceModalOpen] = useState(false);
  const [isCalling, setIsCalling] = useState(false);
  const { toast } = useToast();

  const handleStartCall = async () => {
    const callNumber = window.prompt("Enter number in E.164 format (example: +919876543210)", "+91");
    if (!callNumber?.trim()) return;
    const normalized = callNumber.trim();
    if (!/^\+[1-9]\d{7,14}$/.test(normalized)) {
      toast({
        title: "Invalid phone number",
        description: "Use E.164 format, for example +919876543210.",
        variant: "destructive",
      });
      return;
    }

    setIsCalling(true);
    try {
      const payload: any = await voiceApi.startCall({
        to: normalized,
        userId: score?.user_id || "",
      });

      toast({
        title: "Calling now",
        description: `Call started (${payload?.callSid || "pending"}). Pick up to talk to the assistant.`,
      });
    } catch (error) {
      toast({
        title: "Call failed",
        description: error instanceof Error ? error.message : "Could not start outbound call",
        variant: "destructive",
      });
    } finally {
      setIsCalling(false);
    }
  };

  useEffect(() => {
    const openTwin = () => setIsVoiceModalOpen(true);
    const consumePending = () => {
      const pending = window.sessionStorage.getItem(VOICE_PENDING_ACTION_KEY);
      if (pending === "open_twin" || pending === "open_twin_chat") {
        setIsVoiceModalOpen(true);
        window.sessionStorage.removeItem(VOICE_PENDING_ACTION_KEY);
      }
    };

    const handleUiAction = (event: Event) => {
      const action = (event as CustomEvent<{ action?: string }>).detail?.action;
      if (action === "open_twin" || action === "open_twin_chat") {
        setIsVoiceModalOpen(true);
        window.sessionStorage.removeItem(VOICE_PENDING_ACTION_KEY);
      }
    };

    consumePending();

    window.addEventListener("voice:open-digital-twin", openTwin);
    window.addEventListener("voice:open-twin-chat", openTwin);
    window.addEventListener("voice:ui-action", handleUiAction);

    return () => {
      window.removeEventListener("voice:open-digital-twin", openTwin);
      window.removeEventListener("voice:open-twin-chat", openTwin);
      window.removeEventListener("voice:ui-action", handleUiAction);
    };
  }, []);

  return (
    <motion.div
      className={cn(
        "relative overflow-hidden rounded-xl border border-lime-400/70 bg-white/5 backdrop-blur-xl p-4",
        "before:pointer-events-none before:absolute before:inset-0 before:bg-gradient-to-br before:from-white/10 before:to-transparent",
      )}
      style={{ transformStyle: "preserve-3d" }}
      whileHover={{ rotateX: -2, rotateY: 2, y: -3 }}
      transition={{ type: "spring", stiffness: 240, damping: 18 }}
    >
      <div className="relative z-10 space-y-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-xs uppercase tracking-[0.12em] text-muted-foreground">Your Digital Twin</p>
            <p className="text-sm font-semibold text-foreground">{twin.name}</p>
          </div>
          <span
            className={cn(
              "rounded-full border px-2.5 py-1 text-[11px] font-semibold tracking-wide",
              risk.badge,
            )}
          >
            {risk.text}
          </span>
        </div>

        <div className="flex justify-center">
          <TwinEnergyAura avatarLabel={twin.name.charAt(0).toUpperCase()} className={risk.ring} />
        </div>

        <div className="rounded-lg border border-white/15 bg-black/20 p-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <p className="text-[11px] uppercase tracking-wide text-muted-foreground">Liquidity Health</p>
              <p className="text-lg font-bold text-lime-300">{twin.liquidity}</p>
            </div>
            <div>
              <p className="text-[11px] uppercase tracking-wide text-muted-foreground">Stability</p>
              <p className="text-lg font-bold text-foreground">{twin.stability}%</p>
            </div>
          </div>
          <p className="mt-3 text-xs text-foreground/85 leading-relaxed">{twin.suggestion}</p>
        </div>

        <div className="flex items-center justify-between gap-2">
          <p className="text-xs text-muted-foreground">Updated {twin.lastUpdated}</p>
          <div className="flex items-center gap-2">
            <motion.button
              type="button"
              whileHover={{ scale: 1.04 }}
              whileTap={{ scale: 0.98 }}
              onClick={handleStartCall}
              disabled={isCalling}
              className="inline-flex items-center gap-1.5 rounded-lg border border-cyan-400/70 bg-cyan-400/15 px-3 py-1.5 text-xs font-semibold text-cyan-300 hover:bg-cyan-400/20 disabled:opacity-60"
            >
              {isCalling ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <PhoneCall className="h-3.5 w-3.5" />}
              {isCalling ? "Calling..." : "Call Assistant"}
            </motion.button>

            <motion.button
              type="button"
              whileHover={{ scale: 1.04 }}
              whileTap={{ scale: 0.98 }}
              onClick={() => setIsVoiceModalOpen(true)}
              className="inline-flex items-center gap-1.5 rounded-lg border border-lime-400/70 bg-lime-400/15 px-3 py-1.5 text-xs font-semibold text-lime-300 hover:bg-lime-400/20"
            >
              <Mic className="h-3.5 w-3.5" />
              Talk to your Twin
            </motion.button>
          </div>
        </div>
      </div>

      <VoiceModal 
        isOpen={isVoiceModalOpen} 
        onClose={() => setIsVoiceModalOpen(false)} 
        twinName={twin.name} 
        dataContext={score}
      />
    </motion.div>
  );
}
