"use client";

import { useEffect, useMemo, useRef } from "react";

type FanPoint = {
  day: number;
  p10: number;
  p50: number;
  p90: number;
};

type DefaultPoint = {
  day: number;
  default_probability: number;
};

interface Simulation3DViewProps {
  fanSeries: FanPoint[];
  defaultTrajectory?: DefaultPoint[];
  height?: number;
}

function clamp(v: number, lo: number, hi: number) {
  return Math.max(lo, Math.min(hi, v));
}

export function Simulation3DView({
  fanSeries,
  defaultTrajectory = [],
  height = 240,
}: Simulation3DViewProps) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const normalized = useMemo(() => {
    if (!fanSeries.length) return [] as FanPoint[];
    return [...fanSeries]
      .filter((p) => Number.isFinite(p.day) && Number.isFinite(p.p10) && Number.isFinite(p.p50) && Number.isFinite(p.p90))
      .sort((a, b) => a.day - b.day)
      .slice(0, 90);
  }, [fanSeries]);

  useEffect(() => {
    const wrap = wrapRef.current;
    const canvas = canvasRef.current;
    if (!wrap || !canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let rafId = 0;
    let w = 0;
    let h = height;
    let dpr = 1;

    const setSize = () => {
      dpr = Math.max(1, window.devicePixelRatio || 1);
      w = Math.max(240, Math.floor(wrap.clientWidth));
      h = height;
      canvas.width = Math.floor(w * dpr);
      canvas.height = Math.floor(h * dpr);
      canvas.style.width = `${w}px`;
      canvas.style.height = `${h}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    const ro = new ResizeObserver(setSize);
    ro.observe(wrap);
    setSize();

    const values = normalized.flatMap((p) => [p.p10, p.p50, p.p90]);
    const minV = values.length ? Math.min(...values) : 0;
    const maxV = values.length ? Math.max(...values) : 1;
    const rangeV = Math.max(1e-6, maxV - minV);
    const maxDay = Math.max(1, ...normalized.map((p) => p.day));

    const project = (x: number, y: number, z: number, t: number) => {
      const yaw = 0.55 + Math.sin(t * 0.00025) * 0.16;
      const pitch = 0.55;
      const cy = Math.cos(yaw);
      const sy = Math.sin(yaw);
      const cp = Math.cos(pitch);
      const sp = Math.sin(pitch);

      const x1 = x * cy - z * sy;
      const z1 = x * sy + z * cy;
      const y2 = y * cp - z1 * sp;
      const z2 = y * sp + z1 * cp;

      const dist = 3.0;
      const persp = 1 / (z2 + dist);
      const sx = w * 0.5 + x1 * persp * w * 0.9;
      const sy2 = h * 0.63 - y2 * persp * h * 1.25;
      return { x: sx, y: sy2, p: persp };
    };

    const drawGrid = (t: number) => {
      ctx.save();
      ctx.lineWidth = 1;
      for (let i = 0; i <= 7; i += 1) {
        const z = (i / 7) * 1.8;
        const a = project(-1.2, -0.45, z, t);
        const b = project(1.2, -0.45, z, t);
        ctx.strokeStyle = "rgba(180, 255, 240, 0.10)";
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.stroke();
      }
      for (let j = 0; j <= 6; j += 1) {
        const x = -1.2 + (j / 6) * 2.4;
        const a = project(x, -0.45, 0, t);
        const b = project(x, -0.45, 1.8, t);
        ctx.strokeStyle = "rgba(180, 255, 240, 0.08)";
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.stroke();
      }
      ctx.restore();
    };

    const drawBandLines = (t: number) => {
      if (!normalized.length) return;
      const toY = (v: number) => -0.35 + ((v - minV) / rangeV) * 1.25;
      const toZ = (day: number) => (day / maxDay) * 1.8;

      const drawPath = (laneX: number, key: "p10" | "p50" | "p90", color: string, width: number) => {
        ctx.strokeStyle = color;
        ctx.lineWidth = width;
        ctx.beginPath();
        normalized.forEach((p, idx) => {
          const q = project(laneX, toY(p[key]), toZ(p.day), t);
          if (idx === 0) ctx.moveTo(q.x, q.y);
          else ctx.lineTo(q.x, q.y);
        });
        ctx.stroke();
      };

      for (let i = 0; i < normalized.length; i += 6) {
        const p = normalized[i];
        const q1 = project(-0.55, toY(p.p10), toZ(p.day), t);
        const q2 = project(0.55, toY(p.p90), toZ(p.day), t);
        ctx.strokeStyle = "rgba(120, 255, 220, 0.18)";
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(q1.x, q1.y);
        ctx.lineTo(q2.x, q2.y);
        ctx.stroke();
      }

      drawPath(-0.55, "p10", "rgba(239, 68, 68, 0.85)", 2);
      drawPath(0.0, "p50", "rgba(200, 255, 0, 0.95)", 2.6);
      drawPath(0.55, "p90", "rgba(34, 197, 94, 0.85)", 2);
    };

    const drawDefaultTowers = (t: number) => {
      if (!defaultTrajectory.length) return;
      const maxDayLocal = Math.max(1, ...defaultTrajectory.map((p) => p.day));
      const toZ = (day: number) => (day / maxDayLocal) * 1.8;
      defaultTrajectory.forEach((p) => {
        const prob = clamp(p.default_probability, 0, 1);
        const y0 = -0.45;
        const y1 = y0 + prob * 1.25;
        const x = 0.95;
        const b = project(x, y0, toZ(p.day), t);
        const top = project(x, y1, toZ(p.day), t);
        ctx.strokeStyle = prob > 0.3 ? "rgba(239,68,68,0.95)" : prob > 0.12 ? "rgba(245,158,11,0.95)" : "rgba(34,197,94,0.95)";
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.moveTo(b.x, b.y);
        ctx.lineTo(top.x, top.y);
        ctx.stroke();

        ctx.fillStyle = "rgba(230, 235, 240, 0.9)";
        ctx.font = "10px monospace";
        ctx.fillText(`D${p.day}`, top.x + 4, top.y - 2);
      });
    };

    const drawLegend = () => {
      ctx.fillStyle = "rgba(220, 225, 230, 0.85)";
      ctx.font = "11px monospace";
      ctx.fillText("3D Monte Carlo Flight View", 10, 18);
      ctx.fillStyle = "rgba(239,68,68,0.9)";
      ctx.fillText("P10", 10, 34);
      ctx.fillStyle = "rgba(200,255,0,0.95)";
      ctx.fillText("P50", 44, 34);
      ctx.fillStyle = "rgba(34,197,94,0.9)";
      ctx.fillText("P90", 78, 34);
      ctx.fillStyle = "rgba(200,205,210,0.75)";
      ctx.fillText("Right towers: default probability", 120, 34);
    };

    const draw = (t: number) => {
      const bg = ctx.createLinearGradient(0, 0, 0, h);
      bg.addColorStop(0, "#071016");
      bg.addColorStop(1, "#03060a");
      ctx.fillStyle = bg;
      ctx.fillRect(0, 0, w, h);

      drawGrid(t);
      drawBandLines(t);
      drawDefaultTowers(t);
      drawLegend();

      if (!normalized.length) {
        ctx.fillStyle = "rgba(170, 180, 190, 0.8)";
        ctx.font = "12px monospace";
        ctx.fillText("Run a simulation to render 3D trajectories.", 12, h - 16);
      }

      rafId = window.requestAnimationFrame(draw);
    };

    rafId = window.requestAnimationFrame(draw);

    return () => {
      window.cancelAnimationFrame(rafId);
      ro.disconnect();
    };
  }, [defaultTrajectory, height, normalized]);

  return (
    <div ref={wrapRef} className="w-full rounded-lg border border-white/10 overflow-hidden bg-[#02070b]">
      <canvas ref={canvasRef} />
    </div>
  );
}
