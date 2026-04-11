"use client";

import { motion } from "framer-motion";
import { cn } from "@/dib/utils";

type TwinGlowAuraProps = {
  size?: number;
  avatarLabel?: string;
  className?: string;
};

const PARTICLES = [
  { x: "12%", y: "26%", size: 3, delay: 0.1, duration: 2.8 },
  { x: "24%", y: "78%", size: 2, delay: 1.2, duration: 3.4 },
  { x: "36%", y: "16%", size: 2, delay: 0.7, duration: 3.0 },
  { x: "68%", y: "24%", size: 3, delay: 1.8, duration: 2.6 },
  { x: "82%", y: "68%", size: 2, delay: 0.3, duration: 3.6 },
  { x: "54%", y: "84%", size: 2, delay: 2.1, duration: 2.7 },
  { x: "74%", y: "44%", size: 3, delay: 0.5, duration: 3.2 },
  { x: "16%", y: "56%", size: 2, delay: 1.5, duration: 2.9 },
];

export function TwinGlowAura({
  size = 164,
  avatarLabel = "P",
  className,
}: TwinGlowAuraProps) {
  return (
    <motion.div
      className={cn("relative mx-auto rounded-full ring-1 ring-inset", className)}
      style={{ width: size, height: size, willChange: "transform" }}
      animate={{ scale: [1, 1.05, 1] }}
      transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
    >
      <motion.div
        className="absolute inset-0 rounded-full opacity-80 mix-blend-screen"
        style={{
          background:
            "conic-gradient(from 0deg, #84cc16, #22c55e, #a3e635, #84cc16)",
          filter: "blur(20px)",
          willChange: "transform",
        }}
        animate={{ rotate: 360 }}
        transition={{ duration: 10, repeat: Infinity, ease: "linear" }}
      />

      <motion.div
        className="absolute inset-0 rounded-full opacity-75 mix-blend-screen"
        style={{
          background:
            "conic-gradient(from 180deg, #a3e635, #84cc16, #22c55e, #a3e635)",
          filter: "blur(22px)",
          transform: "scale(1.1)",
          willChange: "transform",
        }}
        animate={{ rotate: -360 }}
        transition={{ duration: 12, repeat: Infinity, ease: "linear" }}
      />

      <div
        className="absolute inset-[12%] rounded-full"
        style={{
          background:
            "radial-gradient(circle, rgba(132,204,22,0.4), transparent 70%)",
          backdropFilter: "blur(8px)",
        }}
      />

      {PARTICLES.map((particle, index) => (
        <motion.span
          key={index}
          className="absolute rounded-full bg-lime-300/90"
          style={{
            left: particle.x,
            top: particle.y,
            width: particle.size,
            height: particle.size,
            boxShadow: "0 0 10px rgba(163,230,53,0.8)",
          }}
          animate={{ opacity: [0.2, 1, 0.25], y: [0, -4, 0] }}
          transition={{
            repeat: Infinity,
            duration: particle.duration,
            delay: particle.delay,
            ease: "easeInOut",
          }}
        />
      ))}

      <div className="absolute inset-0 z-20 flex items-center justify-center">
        <div className="h-14 w-14 rounded-full border border-white/30 bg-black/35 backdrop-blur-md text-lime-300 font-semibold flex items-center justify-center">
          {avatarLabel}
        </div>
      </div>
    </motion.div>
  );
}
