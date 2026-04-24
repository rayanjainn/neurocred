"use client";

import { useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  ChevronDown,
  ChevronRight,
  Loader2,
  RefreshCw,
  Shield,
  TrendingDown,
  TrendingUp,
  Zap,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { simulationApi } from "@/dib/api";

// ── Types ─────────────────────────────────────────────────────────────────────

interface SimulationStep {
  step: number;
  day: number;
  action: string;
  description: string;
  daily_cf_delta: number;
  success_probability: number;
}

interface SimulationResult {
  simulation_id: string;
  user_id: string;
  timestamp: string;
  ews: {
    ews_7d: number;
    ews_14d: number;
    ews_30d: number;
    severity: string;
  };
  fan_chart: {
    horizon_days: number;
    p10: number[];
    p25: number[];
    p50: number[];
    p75: number[];
    p90: number[];
  };
  recovery_plan: {
    plan_id: string;
    steps: SimulationStep[];
    projected_regime_at_45d: string;
    recovery_probability_full_compliance: number;
    recovery_probability_50pct_compliance: number;
    recovery_probability_no_action: number;
    alternative_step3: any;
  };
  tail_risk: {
    var_95: number;
    cvar_95: number;
  };
  regime_distribution_at_90d: {
    STABLE: number;
    STRESSED: number;
    CRISIS: number;
  };
  default_probability: number;
}

interface SimulationPanelProps {
  userId: string;
  score?: any;
  compact?: boolean;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

const EWS_COLORS: Record<string, string> = {
  GREEN:  "text-[#C8FF00]",
  AMBER:  "text-[#FFAA00]",
  ORANGE: "text-orange-400",
  RED:    "text-[#FF0040]",
};

const EWS_BG: Record<string, string> = {
  GREEN:  "bg-[rgba(200,255,0,0.12)] border-[rgba(200,255,0,0.3)]",
  AMBER:  "bg-[rgba(255,170,0,0.10)] border-[rgba(255,170,0,0.3)]",
  ORANGE: "bg-orange-400/10 border-orange-400/30",
  RED:    "bg-[rgba(255,0,64,0.10)] border-[rgba(255,0,64,0.3)]",
};

function pct(v: number) {
  return `${(v * 100).toFixed(0)}%`;
}

function formatINR(v: number) {
  if (Math.abs(v) >= 100000) return `₹${(v / 100000).toFixed(1)}L`;
  if (Math.abs(v) >= 1000) return `₹${(v / 1000).toFixed(1)}k`;
  return `₹${Math.round(v)}`;
}

// Mini sparkline — renders p10/p50/p90 band from fan chart
function FanSparkline({ fan }: { fan: SimulationResult["fan_chart"] }) {
  if (!fan?.p50?.length) return null;
  const days = Math.min(fan.p50.length, 30);
  const all = [...(fan.p10 ?? []), ...(fan.p90 ?? [])].slice(0, days);
  const min = Math.min(...all);
  const max = Math.max(...all);
  const range = max - min || 1;
  const W = 200;
  const H = 48;
  const toX = (i: number) => (i / (days - 1)) * W;
  const toY = (v: number) => H - ((v - min) / range) * H;

  const p50pts = fan.p50.slice(0, days).map((v, i) => `${toX(i)},${toY(v)}`).join(" ");
  const p10pts = fan.p10.slice(0, days).map((v, i) => `${toX(i)},${toY(v)}`).join(" ");
  const p90pts = fan.p90.slice(0, days).map((v, i) => `${toX(i)},${toY(v)}`).join(" ");

  const areaPath = [
    `M ${p90pts.split(" ")[0]}`,
    ...fan.p90.slice(0, days).map((v, i) => `L ${toX(i)} ${toY(v)}`),
    ...fan.p10
      .slice(0, days)
      .reverse()
      .map((v, i) => `L ${toX(days - 1 - i)} ${toY(v)}`),
    "Z",
  ].join(" ");

  return (
    <svg width={W} height={H} className="overflow-visible">
      <path d={areaPath} fill="rgba(200,255,0,0.08)" />
      <polyline
        points={p50pts}
        fill="none"
        stroke="#C8FF00"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      <polyline
        points={p10pts}
        fill="none"
        stroke="rgba(200,255,0,0.3)"
        strokeWidth="1"
        strokeDasharray="3,3"
      />
      <polyline
        points={p90pts}
        fill="none"
        stroke="rgba(200,255,0,0.3)"
        strokeWidth="1"
        strokeDasharray="3,3"
      />
    </svg>
  );
}

// ── Main Component ─────────────────────────────────────────────────────────────

export function SimulationPanel({ userId, score, compact = false }: SimulationPanelProps) {
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showPlan, setShowPlan] = useState(false);

  const runSimulation = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const payload = {
        user_id: userId,
        horizon_days: 90,
        num_simulations: 1000,
        scenario: score?.risk_band === "high_risk"
          ? { type: "compound", components: ["C_FULL_STRESS"], start_day: 0 }
          : null,
        variance_reduction: { sobol: true, antithetic: true },
        run_counterfactual: false,
        seed: null,
      };

      const data: any = await simulationApi.run(payload);
      setResult(data);
      setShowPlan(data?.recovery_plan?.steps?.length > 0);
    } catch (e: any) {
      setError(e.message ?? "Simulation failed");
    } finally {
      setLoading(false);
    }
  }, [userId, score]);

  const ews = result?.ews;
  const severity = ews?.severity ?? "GREEN";
  const ewsColor = EWS_COLORS[severity] ?? "text-gray-400";
  const ewsBg = EWS_BG[severity] ?? "bg-gray-800/40 border-gray-600/30";
  const plan = result?.recovery_plan;
  const regime = result?.regime_distribution_at_90d;

  if (compact) {
    return (
      <div className="flex items-center gap-2">
        <Button
          size="sm"
          variant="outline"
          onClick={runSimulation}
          disabled={loading}
          className="h-7 px-2 text-xs border-[rgba(0,240,255,0.2)] text-[#00C8D4] hover:bg-[rgba(0,240,255,0.08)] hover:text-[#00F0FF]"
        >
          {loading ? (
            <Loader2 className="w-3 h-3 animate-spin" />
          ) : (
            <Activity className="w-3 h-3 mr-1" />
          )}
          Run Simulation
        </Button>
        {ews && (
          <Badge className={`text-[10px] px-1.5 py-0 border ${ewsBg} ${ewsColor}`}>
            EWS {severity}
          </Badge>
        )}
      </div>
    );
  }

  return (
    <Card className="bg-[#0D0D0D] border-[rgba(255,255,255,0.06)] overflow-hidden">
      <CardHeader className="pb-3 border-b border-[rgba(255,255,255,0.04)]">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-semibold text-[#F0F0F0] flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-[#00F0FF]" />
            Risk Simulation Engine
            <span className="text-[10px] font-mono text-[#666666] ml-1">Monte Carlo</span>
          </CardTitle>
          <Button
            size="sm"
            onClick={runSimulation}
            disabled={loading}
            className="h-7 px-3 text-xs bg-[rgba(0,240,255,0.10)] border border-[rgba(0,240,255,0.25)] text-[#00C8D4] hover:bg-[rgba(0,240,255,0.18)] hover:text-[#00F0FF] transition-all"
          >
            {loading ? (
              <>
                <Loader2 className="w-3 h-3 mr-1.5 animate-spin" />
                Running…
              </>
            ) : (
              <>
                <RefreshCw className="w-3 h-3 mr-1.5" />
                {result ? "Re-run" : "Run Simulation"}
              </>
            )}
          </Button>
        </div>
      </CardHeader>

      <CardContent className="pt-4 space-y-4">
        {error && (
          <div className="flex items-start gap-2 p-3 rounded-md bg-[rgba(255,0,64,0.08)] border border-[rgba(255,0,64,0.2)]">
            <AlertTriangle className="w-4 h-4 text-[#FF0040] mt-0.5 shrink-0" />
            <p className="text-xs text-[#FF0040]">{error}</p>
          </div>
        )}

        {!result && !loading && (
          <div className="flex flex-col items-center justify-center py-8 gap-3 text-[#444444]">
            <Activity className="w-8 h-8 opacity-40" />
            <p className="text-xs">Run the simulation to see 90-day risk trajectory</p>
          </div>
        )}

        {loading && (
          <div className="flex flex-col items-center justify-center py-8 gap-3">
            <div className="relative">
              <div className="w-10 h-10 rounded-full border border-[rgba(0,240,255,0.2)] animate-ping absolute inset-0" />
              <Loader2 className="w-10 h-10 text-[#00F0FF] animate-spin relative" />
            </div>
            <p className="text-xs text-[#666666] font-mono">Running 1,000 Monte Carlo paths…</p>
          </div>
        )}

        <AnimatePresence>
          {result && !loading && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4 }}
              className="space-y-4"
            >
              {/* EWS Banner */}
              {ews && (
                <div className={`flex items-center justify-between px-3 py-2 rounded-md border ${ewsBg}`}>
                  <div className="flex items-center gap-2">
                    <Zap className={`w-4 h-4 ${ewsColor}`} />
                    <span className={`text-xs font-semibold font-mono ${ewsColor}`}>
                      EWS · {severity}
                    </span>
                    <span className="text-[10px] text-[#666666]">Early Warning System</span>
                  </div>
                  <div className="flex gap-3 text-[10px] font-mono text-[#999999]">
                    <span>7d: <span className={ewsColor}>{pct(ews.ews_7d)}</span></span>
                    <span>14d: <span className={ewsColor}>{pct(ews.ews_14d)}</span></span>
                    <span>30d: <span className={ewsColor}>{pct(ews.ews_30d)}</span></span>
                  </div>
                </div>
              )}

              {/* Fan Chart + Regime Distribution */}
              <div className="grid grid-cols-2 gap-3">
                {/* Fan Chart */}
                <div className="bg-[#111111] rounded-md p-3 border border-[rgba(255,255,255,0.04)]">
                  <p className="text-[10px] text-[#666666] mb-2 font-mono uppercase tracking-wide">
                    Cash Trajectory · 30d
                  </p>
                  {result.fan_chart && <FanSparkline fan={result.fan_chart} />}
                  <div className="flex gap-3 mt-2 text-[9px] font-mono text-[#666666]">
                    <span className="flex items-center gap-1">
                      <span className="w-2 h-0.5 bg-[#C8FF00] inline-block" /> P50
                    </span>
                    <span className="flex items-center gap-1">
                      <span className="w-2 h-0.5 bg-[rgba(200,255,0,0.3)] inline-block border-dashed" /> P10/P90
                    </span>
                  </div>
                </div>

                {/* Regime Distribution */}
                <div className="bg-[#111111] rounded-md p-3 border border-[rgba(255,255,255,0.04)]">
                  <p className="text-[10px] text-[#666666] mb-2 font-mono uppercase tracking-wide">
                    Regime @ 90d
                  </p>
                  {regime && (
                    <div className="space-y-1.5">
                      {(
                        [
                          { key: "STABLE", label: "STABLE", color: "#C8FF00", bg: "bg-[#C8FF00]" },
                          { key: "STRESSED", label: "STRESSED", color: "#FFAA00", bg: "bg-[#FFAA00]" },
                          { key: "CRISIS", label: "CRISIS", color: "#FF0040", bg: "bg-[#FF0040]" },
                        ] as const
                      ).map(({ key, label, color, bg }) => (
                        <div key={key} className="flex items-center gap-2">
                          <span className="text-[9px] font-mono w-14" style={{ color }}>
                            {label}
                          </span>
                          <div className="flex-1 h-1.5 bg-[#1C1C1C] rounded-full overflow-hidden">
                            <div
                              className={`h-full rounded-full ${bg}`}
                              style={{ width: `${((regime as any)[key] ?? 0) * 100}%`, opacity: 0.8 }}
                            />
                          </div>
                          <span className="text-[9px] font-mono text-[#666666] w-8 text-right">
                            {pct((regime as any)[key] ?? 0)}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {/* Tail Risk */}
              {result.tail_risk && (
                <div className="grid grid-cols-3 gap-2">
                  <div className="bg-[#111111] rounded-md p-2.5 border border-[rgba(255,255,255,0.04)] text-center">
                    <p className="text-[9px] text-[#666666] font-mono uppercase">VaR 95%</p>
                    <p className="text-sm font-mono text-[#FF0040] mt-0.5">
                      {formatINR(result.tail_risk.var_95)}
                    </p>
                  </div>
                  <div className="bg-[#111111] rounded-md p-2.5 border border-[rgba(255,255,255,0.04)] text-center">
                    <p className="text-[9px] text-[#666666] font-mono uppercase">CVaR 95%</p>
                    <p className="text-sm font-mono text-[#FF0040] mt-0.5">
                      {formatINR(result.tail_risk.cvar_95)}
                    </p>
                  </div>
                  <div className="bg-[#111111] rounded-md p-2.5 border border-[rgba(255,255,255,0.04)] text-center">
                    <p className="text-[9px] text-[#666666] font-mono uppercase">Default P</p>
                    <p className={`text-sm font-mono mt-0.5 ${
                      (result.default_probability ?? 0) > 0.3
                        ? "text-[#FF0040]"
                        : (result.default_probability ?? 0) > 0.1
                        ? "text-[#FFAA00]"
                        : "text-[#C8FF00]"
                    }`}>
                      {pct(result.default_probability ?? 0)}
                    </p>
                  </div>
                </div>
              )}

              {/* Recovery Plan */}
              {plan && plan.steps.length > 0 && (
                <div className="border border-[rgba(0,240,255,0.15)] rounded-md overflow-hidden">
                  <button
                    className="w-full flex items-center justify-between px-3 py-2 bg-[rgba(0,240,255,0.05)] hover:bg-[rgba(0,240,255,0.08)] transition-colors"
                    onClick={() => setShowPlan(!showPlan)}
                  >
                    <div className="flex items-center gap-2">
                      <Shield className="w-3.5 h-3.5 text-[#00F0FF]" />
                      <span className="text-xs font-semibold text-[#00C8D4]">Recovery Plan</span>
                      <span className="text-[10px] text-[#666666] font-mono">
                        {plan.steps.length} steps · {pct(plan.recovery_probability_full_compliance)} success
                      </span>
                    </div>
                    <ChevronDown
                      className={`w-3.5 h-3.5 text-[#666666] transition-transform ${showPlan ? "rotate-180" : ""}`}
                    />
                  </button>

                  <AnimatePresence>
                    {showPlan && (
                      <motion.div
                        initial={{ height: 0 }}
                        animate={{ height: "auto" }}
                        exit={{ height: 0 }}
                        className="overflow-hidden"
                      >
                        <div className="px-3 py-2 space-y-2">
                          {/* Prob row */}
                          <div className="flex gap-4 text-[10px] font-mono text-[#666666] pb-1 border-b border-[rgba(255,255,255,0.04)]">
                            <span>Full compliance: <span className="text-[#C8FF00]">{pct(plan.recovery_probability_full_compliance)}</span></span>
                            <span>50% compliance: <span className="text-[#FFAA00]">{pct(plan.recovery_probability_50pct_compliance)}</span></span>
                            <span>No action: <span className="text-[#FF0040]">{pct(plan.recovery_probability_no_action)}</span></span>
                          </div>
                          {/* Steps */}
                          {plan.steps.map((step) => (
                            <div key={step.step} className="flex items-start gap-2.5">
                              <div className="w-5 h-5 rounded-full bg-[rgba(0,240,255,0.1)] border border-[rgba(0,240,255,0.2)] flex items-center justify-center shrink-0 mt-0.5">
                                <span className="text-[9px] font-mono text-[#00C8D4]">{step.step}</span>
                              </div>
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2">
                                  <p className="text-xs text-[#F0F0F0] truncate">{step.description}</p>
                                  <span className="text-[9px] font-mono text-[#666666] shrink-0">Day {step.day}</span>
                                </div>
                                <div className="flex gap-3 mt-0.5 text-[9px] font-mono text-[#666666]">
                                  {step.daily_cf_delta > 0 && (
                                    <span className="text-[#C8FF00]">+{formatINR(step.daily_cf_delta)}/day</span>
                                  )}
                                  <span>{pct(step.success_probability)} success</span>
                                </div>
                              </div>
                            </div>
                          ))}
                          {/* Projected regime */}
                          <div className="pt-1 border-t border-[rgba(255,255,255,0.04)] flex items-center gap-2">
                            <TrendingUp className="w-3 h-3 text-[#C8FF00]" />
                            <span className="text-[10px] text-[#999999]">
                              Projected regime at 45d:{" "}
                              <span className={
                                plan.projected_regime_at_45d === "STABLE"
                                  ? "text-[#C8FF00]"
                                  : plan.projected_regime_at_45d === "STRESSED"
                                  ? "text-[#FFAA00]"
                                  : "text-[#FF0040]"
                              }>
                                {plan.projected_regime_at_45d}
                              </span>
                            </span>
                          </div>
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </CardContent>
    </Card>
  );
}
