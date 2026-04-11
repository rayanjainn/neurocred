"use client";

import { motion } from "framer-motion";
import { cn } from "@/dib/utils";

type TwinEnergyAuraProps = {
  avatarLabel?: string;
  className?: string;
};

export function TwinEnergyAura({ avatarLabel = "P", className }: TwinEnergyAuraProps) {
  return (
    <motion.div
      className={cn("relative w-40 h-40 flex items-center justify-center", className)}
      animate={{ y: [0, -6, 0] }}
      transition={{ duration: 4.2, repeat: Infinity, ease: "easeInOut" }}
    >
      <motion.div
        className="absolute inset-[-14%] rounded-full opacity-80 mix-blend-screen"
        style={{
          background:
            "radial-gradient(circle, rgba(96,165,250,0.25), rgba(167,139,250,0.2), rgba(34,211,238,0.2), transparent 70%)",
          filter: "blur(40px)",
          willChange: "transform, opacity",
        }}
        animate={{ scale: [1, 1.08, 1], opacity: [0.7, 1, 0.7] }}
        transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
      />

      <motion.div
        className="absolute inset-0 rounded-full opacity-95 mix-blend-screen"
        style={{
          background:
            "conic-gradient(from 0deg, #60a5fa, #a78bfa, #22d3ee, #4ade80, #60a5fa)",
          filter: "blur(1.5px)",
          WebkitMask:
            "radial-gradient(farthest-side, transparent calc(100% - 12px), #000 calc(100% - 9px))",
          mask: "radial-gradient(farthest-side, transparent calc(100% - 12px), #000 calc(100% - 9px))",
          willChange: "transform",
        }}
        animate={{
          rotate: 360,
          scaleX: [1, 1.04, 0.98, 1],
          scaleY: [1, 0.97, 1.03, 1],
          borderRadius: ["50%", "52% 48% 49% 51%", "49% 51% 52% 48%", "50%"],
        }}
        transition={{ rotate: { duration: 10, repeat: Infinity, ease: "linear" }, borderRadius: { duration: 6, repeat: Infinity, ease: "easeInOut" } }}
      />

      <motion.div
        className="absolute inset-[-1.5%] rounded-full opacity-85 mix-blend-screen"
        style={{
          background:
            "conic-gradient(from 220deg, #4ade80, #22d3ee, #a78bfa, #60a5fa, #4ade80)",
          filter: "blur(7px)",
          WebkitMask:
            "radial-gradient(farthest-side, transparent calc(100% - 16px), #000 calc(100% - 11px))",
          mask: "radial-gradient(farthest-side, transparent calc(100% - 16px), #000 calc(100% - 11px))",
          willChange: "transform",
        }}
        animate={{
          rotate: -360,
          scale: [1.03, 1.07, 1.03],
          borderRadius: ["50%", "47% 53% 50% 50%", "53% 47% 49% 51%", "50%"],
        }}
        transition={{
          rotate: { duration: 12, repeat: Infinity, ease: "linear" },
          scale: { duration: 4.8, repeat: Infinity, ease: "easeInOut" },
          borderRadius: { duration: 8, repeat: Infinity, ease: "easeInOut" },
        }}
      />

      <motion.div
        className="absolute inset-[24%] rounded-full opacity-80 mix-blend-screen"
        style={{
          background:
            "radial-gradient(circle, rgba(167,139,250,0.4), rgba(96,165,250,0.3), transparent 70%)",
          filter: "blur(20px)",
          willChange: "transform",
        }}
        animate={{ scale: [1, 1.05, 1], borderRadius: ["50%", "49% 51% 50% 50%", "50%"] }}
        transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
      />

      <div className="relative z-10 h-14 w-14 rounded-full border border-white/30 bg-black/35 backdrop-blur-md text-cyan-200 font-semibold flex items-center justify-center shadow-[0_0_18px_rgba(34,211,238,0.35)]">
        {avatarLabel}
      </div>
    </motion.div>
  );
}
