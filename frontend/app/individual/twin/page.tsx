"use client";
import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/dib/authContext";
import { twinApi, simulationApi, reasoningApi, ingestApi, interventionApi, individualApi } from "@/dib/api";
import { PageHeader } from "@/components/shared";
import { TimeSeriesPanel } from "@/components/TimeSeriesPanel";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Slider } from "@/components/ui/slider";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  GitBranch, Activity, Download, Play, TrendingUp, FileText,
  CheckCircle2, Loader2, Brain, ChevronDown, ChevronRight,
  Zap, RefreshCw, Shield, MessageSquare, Send, Clock3,
} from "lucide-react";
import { ProcessingWorkflow } from "@/components/ProcessingWorkflow";
import { ScoreStatus } from "@/hooks/useScore";
import {
  LineChart, Line, AreaChart, Area,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import { cn } from "@/dib/utils";

function fmtTs(ts: string) {
  try { return new Date(ts).toLocaleString("en-IN", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }); }
  catch { return ts; }
}
function riskColor(score: number) {
  if (score >= 75) return "#ef4444";
  if (score >= 50) return "#f59e0b";
  return "#22c55e";
}

function fmtINR(n: number) {
  if (n >= 10000000) return `₹${(n / 10000000).toFixed(1)}Cr`;
  if (n >= 100000) return `₹${(n / 100000).toFixed(1)}L`;
  return `₹${n.toLocaleString("en-IN")}`;
}

function fmtPctProb(v: number) {
  if (v > 0 && v < 0.001) return "<0.1%";
  return `${(v * 100).toFixed(2)}%`;
}

function normalizeCotSteps(cot: any): any[] {
  const direct = cot?.steps ?? cot?.chain_of_thought ?? cot?.cot_trace;
  if (Array.isArray(direct)) return direct;
  if (direct && typeof direct === "object") {
    return Object.entries(direct)
      .filter(([, val]) => val !== undefined && val !== null)
      .map(([key, val]) => {
        const title = String(key).replace(/_/g, " ").replace(/\b\w/g, (m) => m.toUpperCase());
        if (typeof val === "string" || typeof val === "number" || typeof val === "boolean") {
          return { title, content: String(val) };
        }
        if (Array.isArray(val)) {
          return { title, content: JSON.stringify(val, null, 2) };
        }
        return { title, ...(val as Record<string, unknown>), content: JSON.stringify(val, null, 2) };
      });
  }

  if (cot && typeof cot === "object") {
    const derived: any[] = [];
    if (cot.risk_narrative || cot.narrative) {
      derived.push({ title: "Narrative", content: String(cot.risk_narrative ?? cot.narrative) });
    }
    if (cot.situation) {
      derived.push({ title: "Situation", content: String(cot.situation) });
    }
    if (cot.confidence !== undefined) {
      derived.push({ title: "Confidence", content: `${Math.round(Number(cot.confidence) * 100)}%` });
    }
    if (Array.isArray(cot.active_flags) && cot.active_flags.length > 0) {
      derived.push({ title: "Concern Flags", content: JSON.stringify(cot.active_flags, null, 2) });
    }
    if (Array.isArray(cot.intent_signals) && cot.intent_signals.length > 0) {
      derived.push({ title: "Intent Signals", content: JSON.stringify(cot.intent_signals, null, 2) });
    }
    return derived;
  }

  return [];
}

const SEVERITY_COLOR: Record<string, string> = {
  critical: "bg-red-500/10 border-red-500/20 text-red-400",
  high: "bg-red-500/10 border-red-500/20 text-red-400",
  medium: "bg-orange-500/10 border-orange-500/20 text-orange-400",
  low: "bg-green-500/10 border-green-500/20 text-green-400",
};

function ReasoningTab({ cotSteps, loading }: { cotSteps: any[]; loading: boolean }) {
  const [expanded, setExpanded] = useState<number[]>([]);
  const toggle = (i: number) =>
    setExpanded((prev) => prev.includes(i) ? prev.filter((x) => x !== i) : [...prev, i]);
  return (
    <Card className="border-border shadow-sm">
      <CardHeader className="py-3 px-4 border-b">
        <CardTitle className="text-sm font-semibold flex items-center gap-2">
          <Brain className="w-4 h-4 text-primary" /> How AI Assessed Your Profile
        </CardTitle>
      </CardHeader>
      <CardContent className="p-4">
        {loading ? (
          <div className="flex items-center justify-center h-32"><Loader2 className="w-6 h-6 animate-spin text-muted-foreground" /></div>
        ) : cotSteps.length === 0 ? (
          <p className="text-xs text-muted-foreground text-center py-8">No reasoning trace yet. The AI will explain your profile on next scoring run.</p>
        ) : (
          <div className="space-y-2">
            {cotSteps.map((s: any, i: number) => {
              const open = expanded.includes(i);
              return (
                <div key={i} className="border border-border rounded-lg overflow-hidden">
                  <button
                    className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-muted/30 transition-colors"
                    onClick={() => toggle(i)}
                  >
                    {open ? <ChevronDown className="w-3.5 h-3.5 shrink-0 text-muted-foreground" /> : <ChevronRight className="w-3.5 h-3.5 shrink-0 text-muted-foreground" />}
                    <span className="text-[10px] font-mono text-muted-foreground w-6 shrink-0">T{i + 1}</span>
                    <span className="text-xs font-medium truncate">{s.title ?? s.step ?? s.thought?.slice(0, 60) ?? "Step"}</span>
                    {s.confidence !== undefined && (
                      <span className="ml-auto text-[10px] text-muted-foreground shrink-0">{Math.round(s.confidence * 100)}% conf.</span>
                    )}
                  </button>
                  {open && (
                    <div className="px-4 pb-3 pt-1 border-t border-border bg-muted/20">
                      <pre className="text-[11px] text-foreground/80 whitespace-pre-wrap leading-relaxed font-mono">
                        {s.content ?? s.reasoning ?? s.thought ?? JSON.stringify(s, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default function IndividualTwinPage() {
  const { user } = useAuth();
  const router = useRouter();
  const [twin, setTwin] = useState<any>(null);
  const [history, setHistory] = useState<any[]>([]);
  const [triggers, setTriggers] = useState<any[]>([]);
  const [cot, setCot] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState("timeline");

  // What-If state
  const [incomeChg, setIncomeChg] = useState([0]);
  const [spendChg, setSpendChg] = useState([0]);
  const [scenario, setScenario] = useState("baseline");
  const [simResult, setSimResult] = useState<any>(null);
  const [simRunning, setSimRunning] = useState(false);
  const [simProgress, setSimProgress] = useState(0);
  const [autoSimEnabled, setAutoSimEnabled] = useState(true);
  const [autoSimEverySec, setAutoSimEverySec] = useState(120);
  const [lastSimAt, setLastSimAt] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [status, setStatus] = useState<ScoreStatus>("pending");
  const [initError, setInitError] = useState<string | null>(null);

  // Generic custom scenario planner
  const [plannerName, setPlannerName] = useState("Custom Scenario");
  const [plannerOneTimeOutflow, setPlannerOneTimeOutflow] = useState(500000);
  const [plannerMonthlyCommitment, setPlannerMonthlyCommitment] = useState(15000);
  const [plannerTenureMonths, setPlannerTenureMonths] = useState(24);
  const [plannerDiscountPct, setPlannerDiscountPct] = useState(0);
  const [plannerIncomeShockPct, setPlannerIncomeShockPct] = useState(0);
  const [plannerExpenseShockPct, setPlannerExpenseShockPct] = useState(0);
  const [plannerLoading, setPlannerLoading] = useState(false);
  const [plannerResult, setPlannerResult] = useState<any>(null);
  const [showPlannerAdvanced, setShowPlannerAdvanced] = useState(false);

  // Tier 8 intervention controls
  const [offer, setOffer] = useState<any>(null);
  const [negSession, setNegSession] = useState<any>(null);
  const [negInput, setNegInput] = useState("");
  const [negBusy, setNegBusy] = useState(false);
  const [liveFeed, setLiveFeed] = useState<any[]>([]);
  const triggerSignatureRef = useRef("");
  const triggerBootstrappedRef = useRef(false);

  const pushFeed = useCallback((event: { title: string; detail: string; severity?: string }) => {
    const ts = new Date().toISOString();
    setLiveFeed((prev) => [
      {
        id: `${ts}:${event.title}`,
        ts,
        title: event.title,
        detail: event.detail,
        severity: event.severity ?? "low",
      },
      ...prev,
    ].slice(0, 40));
  }, []);

  const loadTwinBundle = useCallback(async () => {
    if (!user) return null;
    const [tw, hist, trig, cotData] = await Promise.all([
      twinApi.get(user.id).catch(() => null),
      twinApi.getHistory(user.id).catch(() => []),
      twinApi.getTriggers(user.id).catch(() => []),
      reasoningApi.getCot(user.id).catch(() => null),
    ]);

    let resolvedCot = cotData;
    if (!resolvedCot) {
      resolvedCot = await reasoningApi.getResult(user.id).catch(() => null);
    }

    const triggerPayload = Array.isArray(trig) ? { triggers: trig } : ((trig as any) ?? {});
    const nextTriggers = Array.isArray(triggerPayload?.triggers) ? triggerPayload.triggers : [];
    setTwin(tw);
    setHistory(Array.isArray(hist) ? hist : (hist as any)?.history ?? []);
    setTriggers(nextTriggers);
    if (triggerPayload?.proactive_offer) {
      setOffer(triggerPayload.proactive_offer);
    }
    const signature = JSON.stringify({
      triggers: nextTriggers
        .map((t: any) => `${t.type ?? t.trigger_id ?? "trigger"}:${t.reason ?? t.message ?? ""}`)
        .sort(),
      offer: triggerPayload?.proactive_offer?.offer_id ?? "",
    });
    triggerSignatureRef.current = signature;
    triggerBootstrappedRef.current = true;
    setCot(resolvedCot);
    return tw;
  }, [user]);

  const initializeTwin = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    setInitError(null);
    setStatus("ingesting");

    let tw = await loadTwinBundle();
    if (tw) {
      setStatus("complete");
      setLoading(false);
      return;
    }

    // Determine likely active tier for UX while we actively bootstrap/update.
    try {
      const classify: any = await ingestApi.getClassifyStatus();
      const rawLen = Number(classify?.raw_stream_length ?? 0);
      const typedLen = Number(classify?.typed_stream_length ?? 0);
      if (rawLen <= 0) setStatus("ingesting");
      else if (typedLen < rawLen * 0.8) setStatus("classifying");
      else setStatus("extracting_features");
    } catch {
      setStatus("extracting_features");
    }

    // Deterministic init path: ensure twins exist, then update from latest features.
    await twinApi.bootstrap().catch(() => null);
    setStatus("benchmarking");
    await twinApi.update(user.id, {}).catch(() => null);

    setStatus("scoring");
    tw = await loadTwinBundle();

    if (!tw) {
      setStatus("failed");
      setInitError(
        "Twin could not be initialized yet. Please ensure Tier 1-3 pipeline has produced features for this user, then retry.",
      );
    } else {
      setStatus("complete");
    }
    setLoading(false);
  }, [user, loadTwinBundle]);

  useEffect(() => {
    if (!user) return;
    if (user.role !== "individual") { router.push("/login"); return; }
    initializeTwin();
  }, [user, router, initializeTwin]);

  const refreshAll = useCallback(() => {
    initializeTwin();
  }, [initializeTwin]);

  useEffect(() => {
    if (!user) return;

    const poll = async () => {
      try {
        const trig = await twinApi.getTriggers(user.id);
        const payload = Array.isArray(trig) ? { triggers: trig } : ((trig as any) ?? {});
        const nextTriggers = Array.isArray(payload?.triggers) ? payload.triggers : [];
        setTriggers(nextTriggers);
        if (payload?.proactive_offer) {
          setOffer(payload.proactive_offer);
        }

        const signature = JSON.stringify({
          triggers: nextTriggers
            .map((t: any) => `${t.type ?? t.trigger_id ?? "trigger"}:${t.reason ?? t.message ?? ""}`)
            .sort(),
          offer: payload?.proactive_offer?.offer_id ?? "",
        });

        if (!triggerBootstrappedRef.current) {
          triggerSignatureRef.current = signature;
          triggerBootstrappedRef.current = true;
          return;
        }

        if (signature !== triggerSignatureRef.current) {
          triggerSignatureRef.current = signature;
          const first = nextTriggers[0];
          const sev = String(first?.urgency ?? first?.priority ?? "low").toLowerCase();
          pushFeed({
            title: "Live trigger update",
            detail: first
              ? `${first.type ?? first.trigger_id ?? "Trigger"}: ${first.reason ?? first.message ?? "updated"}`
              : "No active triggers now.",
            severity: sev.includes("high") || sev.includes("critical") ? "high" : sev.includes("med") ? "medium" : "low",
          });
        }
      } catch {
        // Silent polling failure.
      }
    };

    const timer = setInterval(poll, 20000);
    poll();
    return () => clearInterval(timer);
  }, [user, pushFeed]);

  useEffect(() => {
    if (!user || !negSession?.session_id) return;
    const timer = setInterval(async () => {
      try {
        const latest = await interventionApi.getNegotiation(user.id, negSession.session_id);
        setNegSession(latest);
      } catch {
        // Silent polling failure.
      }
    }, 15000);
    return () => clearInterval(timer);
  }, [user, negSession?.session_id]);

  const applyScenario = (s: string) => {
    setScenario(s);
    if (s === "job_loss") { setIncomeChg([-100]); setSpendChg([20]); }
    else if (s === "income_drop") { setIncomeChg([-20]); setSpendChg([0]); }
    else if (s === "spending_shock") { setIncomeChg([0]); setSpendChg([30]); }
    else if (s === "recovery") { setIncomeChg([15]); setSpendChg([-10]); }
    else { setIncomeChg([0]); setSpendChg([0]); }
  };

  const runSimulation = useCallback(async (opts?: { silent?: boolean; source?: "manual" | "auto" }) => {
    if (!user) return;
    const silent = Boolean(opts?.silent);
    if (!silent) {
      setSimResult(null);
      setSimProgress(0);
    }

    setSimRunning(true);
    let interval: ReturnType<typeof setInterval> | null = null;
    if (!silent) {
      interval = setInterval(() => {
        setSimProgress((p) => {
          if (p >= 90) {
            if (interval) clearInterval(interval);
            return 90;
          }
          return p + Math.random() * 12;
        });
      }, 700);
    }

    try {
      const res = await simulationApi.run({
        user_id: user.id,
        run_counterfactual: true,
        num_simulations: 1000,
        scenario_overrides: {
          income_change_pct: incomeChg[0],
          expense_change_pct: spendChg[0],
          scenario_name: scenario,
          job_loss: scenario === "job_loss",
          medical_emergency: scenario === "spending_shock",
        },
      });

      if (interval) clearInterval(interval);
      if (!silent) {
        setSimProgress(100);
      }
      setSimResult(res);
      setLastSimAt(new Date().toISOString());

      const proactive = (res as any)?.proactive_offer;
      if (proactive) {
        setOffer(proactive);
        pushFeed({
          title: "Proactive offer refreshed",
          detail: `Pre-qualified amount ${fmtINR(Number(proactive.approved_amount ?? 0))} is available.`,
          severity: "medium",
        });
      }

      const dp = Number(
        (res as any)?.simulation_windows?.day_90?.default_probability
          ?? (res as any)?.temporal_projections?.day_90?.default_probability
          ?? 0,
      );
      pushFeed({
        title: opts?.source === "auto" ? "Auto simulation completed" : "Simulation completed",
        detail: `Scenario ${scenario.replace(/_/g, " ")}: 90d default probability ${(dp * 100).toFixed(1)}%.`,
        severity: dp > 0.3 ? "high" : dp > 0.15 ? "medium" : "low",
      });
    } catch {
      if (interval) clearInterval(interval);
      if (!silent) {
        setSimProgress(0);
      }
      pushFeed({
        title: opts?.source === "auto" ? "Auto simulation failed" : "Simulation failed",
        detail: "Could not compute the latest projection.",
        severity: "high",
      });
    } finally {
      setTimeout(() => setSimRunning(false), silent ? 0 : 500);
    }
  }, [user, incomeChg, spendChg, scenario, pushFeed]);

  const runCustomScenarioPlanner = useCallback(async () => {
    if (!user) return;
    setPlannerLoading(true);
    setPlannerResult(null);

    const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v));

    try {
      const discountFactor = clamp(1 - plannerDiscountPct / 100, 0, 1);
      const adjustedOneTime = Math.max(0, plannerOneTimeOutflow * discountFactor);
      const effectiveMonthlyCommitment = Math.max(0, plannerMonthlyCommitment);
      const baseEmi = Number(twin?.emi_monthly ?? 0);
      const scenarioName = plannerName.trim() || "custom_scenario";

      const scenarioComponents: string[] = [];
      if (plannerIncomeShockPct <= -45) scenarioComponents.push("S_INC_DROP_50");
      else if (plannerIncomeShockPct <= -15) scenarioComponents.push("S_INC_DROP_20");
      else if (plannerIncomeShockPct >= 15) scenarioComponents.push("S_INC_RISE_20");
      if (plannerExpenseShockPct >= 25) scenarioComponents.push("S_EXP_SURGE_30");
      if (adjustedOneTime > 0) scenarioComponents.push("S_MEDICAL");

      const scenarioPayload = scenarioComponents.length === 0
        ? { type: "baseline", components: [] }
        : {
            type: scenarioComponents.length === 1 ? "atomic" : "compound",
            components: scenarioComponents,
            custom_params: adjustedOneTime > 0 ? { medical_expense_amount: adjustedOneTime } : {},
          };

      const profile: any = await individualApi.getScore(user.id).catch(() => null);
      const profileIncome = Number(profile?.monthly_income_estimate ?? 0);
      const profileExpense = Number(profile?.monthly_expense_estimate ?? 0);

      const [baselineRes, stressedRes] = await Promise.all([
        simulationApi.run({
          user_id: user.id,
          num_simulations: 1000,
          run_counterfactual: true,
          scenario_overrides: {
            scenario_name: "baseline",
            income_change_pct: 0,
            expense_change_pct: 0,
          },
        }),
        simulationApi.run({
          user_id: user.id,
          num_simulations: 1000,
          run_counterfactual: true,
          twin_snapshot: {
            emi_monthly: Math.max(1, baseEmi + effectiveMonthlyCommitment),
            income_monthly: Math.max(
              1000,
              profileIncome * (1 + plannerIncomeShockPct / 100),
            ),
            essential_expense_monthly: Math.max(
              0,
              profileExpense * 0.65 * (1 + plannerExpenseShockPct / 100),
            ),
            discretionary_expense_monthly: Math.max(
              0,
              profileExpense * 0.35 * (1 + plannerExpenseShockPct / 100),
            ),
          },
          scenario: scenarioPayload,
        }),
      ]);

      const base90 = Number(
        (baselineRes as any)?.simulation_windows?.day_90?.default_probability
        ?? (baselineRes as any)?.temporal_projections?.day_90?.default_probability
        ?? 0,
      );
      const stress90 = Number(
        (stressedRes as any)?.simulation_windows?.day_90?.default_probability
        ?? (stressedRes as any)?.temporal_projections?.day_90?.default_probability
        ?? 0,
      );
      const delta90 = stress90 - base90;

      const baseEws14 = Number((baselineRes as any)?.ews?.ews_14d ?? (baselineRes as any)?.ews_snapshot?.ews_14d ?? 0);
      const stressEws14 = Number((stressedRes as any)?.ews?.ews_14d ?? (stressedRes as any)?.ews_snapshot?.ews_14d ?? 0);
      const deltaEws14 = stressEws14 - baseEws14;
      const baseVar95 = Math.abs(Number((baselineRes as any)?.tail_risk?.var_95 ?? (baselineRes as any)?.var_95 ?? 0));
      const stressVar95 = Math.abs(Number((stressedRes as any)?.tail_risk?.var_95 ?? (stressedRes as any)?.var_95 ?? 0));
      const deltaVar95 = stressVar95 - baseVar95;
      const basePaths = Number((baselineRes as any)?.num_paths ?? 1000);
      const stressPaths = Number((stressedRes as any)?.num_paths ?? 1000);
      const baseDefaultPaths = Math.max(0, Math.round(base90 * Math.max(basePaths, 1)));
      const stressDefaultPaths = Math.max(0, Math.round(stress90 * Math.max(stressPaths, 1)));

      const baselineRunId =
        (baselineRes as any)?.simulation_id
        ?? (baselineRes as any)?.sim_id
        ?? (baselineRes as any)?.id
        ?? null;
      const stressedRunId =
        (stressedRes as any)?.simulation_id
        ?? (stressedRes as any)?.sim_id
        ?? (stressedRes as any)?.id
        ?? null;

      const income = profileIncome;
      const expenses = profileExpense;
      const baseHealth = Number(profile?.financial_health_score ?? 0);

      const monthlySurplusAfterCommitment = income - expenses - effectiveMonthlyCommitment;
      const oneTimeCoverageMonths = monthlySurplusAfterCommitment > 0
        ? adjustedOneTime / monthlySurplusAfterCommitment
        : Number.POSITIVE_INFINITY;

      const projectedPenalty =
        Math.max(0, Math.round(delta90 * 120))
        + Math.max(0, Math.round(deltaEws14 * 60))
        + Math.max(0, Math.round((deltaVar95 / Math.max(income * 3, 1)) * 35))
        + (monthlySurplusAfterCommitment < 0 ? 10 : 0)
        + (oneTimeCoverageMonths > 8 ? 6 : oneTimeCoverageMonths > 4 ? 3 : 0);
      const projectedHealth = clamp(baseHealth - projectedPenalty, 0, 100);

      const impactScore = Math.round(clamp(
        100 * (
          0.40 * clamp(delta90 / 0.10, 0, 1)
          + 0.25 * clamp(deltaEws14 / 0.15, 0, 1)
          + 0.20 * clamp(deltaVar95 / Math.max(income * 2.0, 1), 0, 1)
          + 0.15 * clamp((-monthlySurplusAfterCommitment) / Math.max(income, 1), 0, 1)
        ),
        0,
        100,
      ));

      const verdict =
        impactScore < 25 && monthlySurplusAfterCommitment >= 0 && oneTimeCoverageMonths <= 4
          ? "comfortable"
          : impactScore < 55 && monthlySurplusAfterCommitment >= -0.1 * Math.max(income, 1)
            ? "cautious"
            : "risky";

      const guidance: string[] = [];
      if (verdict === "comfortable") {
        guidance.push("Scenario appears affordable under current trend and Monte Carlo stress windows.");
      }
      if (monthlySurplusAfterCommitment < 0) {
        guidance.push("Monthly surplus turns negative after this commitment; consider lowering EMI or extending tenure.");
      }
      if (oneTimeCoverageMonths > 6 && Number.isFinite(oneTimeCoverageMonths)) {
        guidance.push("One-time outflow consumes more than 6 months of surplus; split across installments if possible.");
      }
      if (delta90 > 0.08) {
        guidance.push("90-day default probability rises materially versus baseline; this should be treated as high stress.");
      }
      if (baseDefaultPaths === 0 && stressDefaultPaths === 0) {
        guidance.push("No defaulted paths were observed in this run window; sensitivity is reflected via EWS and tail-risk metrics.");
      }
      if (deltaEws14 > 0.05) {
        guidance.push("Early warning severity rises in 14-day horizon; maintain additional liquidity buffer.");
      }
      if (deltaVar95 > Math.max(income, 1) * 0.6) {
        guidance.push("Tail loss (VaR95) worsens sharply under this scenario; avoid concentrated one-time outflow.");
      }
      if (guidance.length === 0) {
        guidance.push("Stress impact is limited; maintain an emergency buffer and monitor monthly spend volatility.");
      }

      setPlannerResult({
        scenario_name: scenarioName,
        scenario_components: scenarioComponents,
        baseline_sim_id: baselineRunId,
        stressed_sim_id: stressedRunId,
        baseline_default_paths: baseDefaultPaths,
        stressed_default_paths: stressDefaultPaths,
        adjusted_one_time: adjustedOneTime,
        effective_monthly_commitment: effectiveMonthlyCommitment,
        baseline_default_90d: base90,
        stressed_default_90d: stress90,
        default_delta_90d: delta90,
        baseline_ews_14d: baseEws14,
        stressed_ews_14d: stressEws14,
        ews_delta_14d: deltaEws14,
        baseline_var_95: baseVar95,
        stressed_var_95: stressVar95,
        var95_delta: deltaVar95,
        monthly_surplus_after_commitment: monthlySurplusAfterCommitment,
        one_time_coverage_months: oneTimeCoverageMonths,
        base_health: baseHealth,
        projected_health: projectedHealth,
        impact_score: impactScore,
        verdict,
        guidance,
        computed_at: new Date().toISOString(),
      });

      pushFeed({
        title: "Scenario planner verdict ready",
        detail: `${scenarioName}: projected health ${projectedHealth}/100, 90d default ${fmtPctProb(stress90)} (${delta90 >= 0 ? "+" : ""}${(delta90 * 100).toFixed(2)}pp).`,
        severity: verdict === "risky" ? "high" : verdict === "cautious" ? "medium" : "low",
      });
    } catch {
      pushFeed({
        title: "Scenario planner failed",
        detail: "Could not compute custom scenario verdict. Try again in a few seconds.",
        severity: "high",
      });
    } finally {
      setPlannerLoading(false);
    }
  }, [
    user,
    twin?.emi_monthly,
    plannerName,
    plannerOneTimeOutflow,
    plannerMonthlyCommitment,
    plannerTenureMonths,
    plannerDiscountPct,
    plannerIncomeShockPct,
    plannerExpenseShockPct,
    pushFeed,
  ]);

  const fetchOffer = useCallback(async () => {
    if (!user) return;
    try {
      const payload = await interventionApi.getOffer(user.id);
      const nextOffer = (payload as any)?.offer ?? payload;
      if (nextOffer) {
        setOffer(nextOffer);
        pushFeed({
          title: "Pre-qualified offer generated",
          detail: `Approved amount ${fmtINR(Number((nextOffer as any)?.approved_amount ?? 0))}.`,
          severity: "medium",
        });
      }
    } catch {
      pushFeed({
        title: "Offer fetch failed",
        detail: "Could not generate an intervention offer right now.",
        severity: "high",
      });
    }
  }, [user, pushFeed]);

  const startNegotiation = useCallback(async () => {
    if (!user) return;
    setNegBusy(true);
    try {
      const session = await interventionApi.startNegotiation(
        user.id,
        offer ? { offer } : undefined,
      );
      setNegSession(session);
      pushFeed({
        title: "Negotiation started",
        detail: "Tier 8 intervention agent opened an EMI restructuring session.",
        severity: "medium",
      });
    } catch {
      pushFeed({
        title: "Negotiation start failed",
        detail: "Could not start restructuring negotiation.",
        severity: "high",
      });
    } finally {
      setNegBusy(false);
    }
  }, [user, offer, pushFeed]);

  const sendNegotiationTurn = useCallback(async () => {
    if (!user || !negSession?.session_id || !negInput.trim()) return;
    const msg = negInput.trim();
    setNegInput("");
    setNegBusy(true);
    try {
      const next = await interventionApi.negotiateTurn(user.id, negSession.session_id, msg);
      setNegSession(next);
      const nextStatus = (next as any)?.status;
      if (nextStatus === "confirmed") {
        pushFeed({
          title: "Restructure confirmed",
          detail: "Twin updated with negotiated EMI restructuring metrics.",
          severity: "low",
        });
        loadTwinBundle();
      } else if (nextStatus === "rejected") {
        pushFeed({
          title: "Restructure rejected",
          detail: "No restructuring impact has been committed to the twin.",
          severity: "medium",
        });
      }
    } catch {
      pushFeed({
        title: "Negotiation turn failed",
        detail: "The message could not be processed by the intervention engine.",
        severity: "high",
      });
    } finally {
      setNegBusy(false);
    }
  }, [user, negSession, negInput, loadTwinBundle, pushFeed]);

  useEffect(() => {
    if (!user || !autoSimEnabled) return;
    const timer = setInterval(() => {
      if (!simRunning) {
        runSimulation({ silent: true, source: "auto" });
      }
    }, autoSimEverySec * 1000);
    return () => clearInterval(timer);
  }, [user, autoSimEnabled, autoSimEverySec, simRunning, runSimulation]);

  const exportAudit = async (format: "json" | "csv") => {
    if (!user) return;
    setGenerating(true);
    try {
      const [currentTwin, twinHist, twinTriggers, cotTrace, ews] = await Promise.all([
        twinApi.get(user.id).catch(() => null),
        twinApi.getHistory(user.id).catch(() => []),
        twinApi.getTriggers(user.id).catch(() => []),
        reasoningApi.getCot(user.id).catch(() => null),
        simulationApi.getEws(user.id).catch(() => null),
      ]);
      const report = {
        generated_at: new Date().toISOString(),
        user_id: user.id,
        user_name: user.name,
        regulatory_note: "Personal data portability export under RBI Digital Lending Guidelines 2023",
        twin_current_state: currentTwin,
        twin_evolution_history: twinHist,
        intervention_triggers: twinTriggers,
        llm_chain_of_thought: cotTrace,
        ews_snapshot: ews,
        simulation_artifacts: simResult ?? { note: "Run a What-If simulation to include projections." },
      };
      const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a"); a.href = url;
      a.download = `my_financial_twin_${user.id}_${Date.now()}.json`; a.click();
      URL.revokeObjectURL(url);
    } finally { setGenerating(false); }
  };

  if (!user || user.role !== "individual") return null;

  const chartData = history.map((v: any) => ({
    ver: `v${v.version ?? "?"}`,
    risk: Math.round((v.risk_score ?? 0) * 100),
    cibil: v.cibil_like_score ?? v.cibil_score ?? 0,
    ts: v.last_updated ?? v.created_at ?? "",
    persona: v.persona ?? "unknown",
  }));

  const fanChart: any[] = Array.isArray(simResult?.fan_chart_series)
    ? simResult.fan_chart_series
    : Array.isArray(simResult?.fan_chart?.p50)
      ? (simResult.fan_chart.p50 as number[]).map((_: number, i: number) => ({
          day: i + 1,
          month: `D${i + 1}`,
          p10: simResult?.fan_chart?.p10?.[i] ?? 0,
          p50: simResult?.fan_chart?.p50?.[i] ?? 0,
          p90: simResult?.fan_chart?.p90?.[i] ?? 0,
        }))
      : [];
  const ews: any = simResult?.ews ?? simResult?.ews_snapshot ?? simResult?.risk_snapshot ?? {};
  const day90 = simResult?.simulation_windows?.day_90 ?? simResult?.temporal_projections?.day_90 ?? {};
  const activeOffer = useMemo(() => offer ?? simResult?.proactive_offer ?? null, [offer, simResult]);
  const newCreditLimit = activeOffer?.approved_amount ?? simResult?.recommended_credit_limit ?? simResult?.new_credit_limit;

  const twinTimeline = history
    .map((v: any) => ({
      date: v.last_updated ?? v.created_at ?? "",
      risk_score: Number(v.risk_score ?? 0),
      version: v.version,
    }))
    .filter((p: any) => p.date);

  const scoreHistory = (twin?.score_history ?? []).map((p: any) => ({
    date: p.date,
    score: Number(p.score ?? 0),
    delta: Number(p.delta ?? 0),
    risk_band: p.risk_band,
  }));

  const cotSteps: any[] = normalizeCotSteps(cot);

  const plannerNarrative = useMemo(() => {
    if (!plannerResult) return null;
    const verdict = String(plannerResult.verdict ?? "cautious");
    const scenarioProb = Number(plannerResult.stressed_default_90d ?? 0);
    const baseProb = Number(plannerResult.baseline_default_90d ?? 0);
    const surplus = Number(plannerResult.monthly_surplus_after_commitment ?? 0);
    const projectedHealth = Number(plannerResult.projected_health ?? 0);
    const impactScore = Number(plannerResult.impact_score ?? 0);
    const coverageMonths = Number(plannerResult.one_time_coverage_months ?? Number.POSITIVE_INFINITY);

    const riskBand = scenarioProb >= 0.3 ? "high" : scenarioProb >= 0.12 ? "moderate" : "low";
    const opener =
      verdict === "comfortable"
        ? "This scenario looks manageable with your current income and spending pattern."
        : verdict === "cautious"
          ? "This scenario is possible, but you should watch cash flow and keep a safety buffer."
          : "This scenario looks financially stressful under current trends and should be adjusted.";

    const recommendation =
      verdict === "comfortable"
        ? "Proceed only if you preserve at least 3 months of emergency cash."
        : verdict === "cautious"
          ? "Reduce one-time amount or monthly commitment by 15-25% before proceeding."
          : "Avoid this version. Rework it with lower upfront outflow, lower EMI, or higher discount.";

    return {
      opener,
      recommendation,
      points: [
        `After this plan, estimated monthly cash left is ${fmtINR(Math.round(surplus))}.`,
        `90-day stress default risk is ${fmtPctProb(scenarioProb)} (${riskBand}) vs baseline ${fmtPctProb(baseProb)}.`,
        `Projected financial health is ${projectedHealth}/100 with impact score ${impactScore}/100.`,
        Number.isFinite(coverageMonths)
          ? `Your one-time outflow equals about ${coverageMonths.toFixed(1)} months of post-plan surplus.`
          : "Your one-time outflow cannot be covered by current monthly surplus.",
      ],
    };
  }, [plannerResult]);

  if (loading) {
     return (
        <div className="p-6 w-full max-w-[1400px] mx-auto min-h-screen flex flex-col bg-background">
          <PageHeader
            title="Initializing Digital Twin Account..."
            description={`Reconstructing high-fidelity financial personality for ${user?.name}`}
          />
          <div className="flex-1 flex flex-col items-center justify-center">
              <div className="w-full max-w-xl p-8 rounded-3xl border bg-card/50 backdrop-blur-xl shadow-2xl relative overflow-hidden">
                  <div className="absolute top-0 left-0 w-full h-1 bg-muted">
                      <div className="h-full bg-primary transition-all duration-500" style={{ width: (
                          status === "ingesting" ? "20%" :
                          status === "classifying" ? "40%" :
                          status === "extracting_features" ? "60%" :
                          status === "benchmarking" ? "80%" :
                          status === "scoring" ? "95%" : "5%"
                      ) }} />
                  </div>
                  <h3 className="text-xl font-bold mb-8 flex items-center gap-3">
                      <Shield className="w-6 h-6 text-primary" />
                      Individual Behavioural Scoring
                  </h3>
                  <ProcessingWorkflow currentStatus={status} />
              </div>
              <p className="mt-8 text-sm text-muted-foreground animate-pulse tracking-wide uppercase">
                  Tier 3 Trend Engine Online
              </p>
          </div>
        </div>
      );
  }

  if (initError) {
    return (
      <div className="p-6 w-full max-w-[1200px] mx-auto space-y-4">
        <PageHeader
          title="Digital Twin Initialization Failed"
          description={initError}
          actions={
            <Button size="sm" onClick={initializeTwin} className="gap-2">
              <RefreshCw className="w-3.5 h-3.5" /> Retry Initialization
            </Button>
          }
        />
      </div>
    );
  }

  const liquidityPct = typeof twin?.liquidity_health_index === "number"
    ? Math.round(twin.liquidity_health_index * 100)
    : (twin?.liquidity_health === "HIGH" ? 90 : twin?.liquidity_health === "MEDIUM" ? 55 : 25);

  return (
    <div className="p-6 w-full max-w-[1200px] mx-auto space-y-6">
      <PageHeader
        title="My Digital Twin"
        description="Your personal financial digital twin — see how your profile has evolved, simulate life events, and download your data."
        actions={
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" className="gap-2 h-8 text-xs font-medium" onClick={refreshAll}>
              <RefreshCw className="w-3.5 h-3.5" /> Refresh
            </Button>
            <Button variant="outline" size="sm" className="gap-2 h-8 text-xs font-medium" onClick={() => exportAudit("json")} disabled={generating}>
              {generating ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />} JSON
            </Button>
            <Button size="sm" className="gap-2 h-8 text-xs font-medium" onClick={() => window.print()}>
              <FileText className="w-3.5 h-3.5" /> PDF
            </Button>
          </div>
        }
      />

      {/* Twin snapshot */}
      {twin && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            { label: "Risk Score", value: `${Math.round((twin.risk_score ?? 0) * 100)}%`, bad: twin.risk_score > 0.5 },
            { label: "Liquidity Health", value: `${liquidityPct}%`, bad: liquidityPct < 40 },
            { label: "CIBIL-Like Score", value: twin.cibil_like_score ?? "—", bad: (twin.cibil_like_score ?? 750) < 650 },
            { label: "Persona", value: twin.persona ?? "—", bad: false },
          ].map((m) => (
            <Card key={m.label} className="border-border shadow-sm">
              <CardContent className="p-4">
                <p className="text-xs text-muted-foreground">{m.label}</p>
                <p className={cn("text-lg font-bold mt-1 capitalize", m.bad ? "text-amber-400" : "text-foreground")}>{String(m.value)}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="mb-4">
          <TabsTrigger value="timeline" className="text-xs gap-1.5"><GitBranch className="w-3.5 h-3.5" />Timeline</TabsTrigger>
          <TabsTrigger value="transactions" className="text-xs gap-1.5"><Activity className="w-3.5 h-3.5" />Transactions</TabsTrigger>
          <TabsTrigger value="simulation" className="text-xs gap-1.5"><Activity className="w-3.5 h-3.5" />What-If</TabsTrigger>
          <TabsTrigger value="reasoning" className="text-xs gap-1.5"><Brain className="w-3.5 h-3.5" />AI Reasoning</TabsTrigger>
          <TabsTrigger value="export" className="text-xs gap-1.5"><Download className="w-3.5 h-3.5" />My Data Export</TabsTrigger>
        </TabsList>

        {/* Timeline */}
        <TabsContent value="timeline" className="space-y-4">
          <Card className="border-border shadow-sm">
            <CardHeader className="py-3 px-4 border-b">
              <CardTitle className="text-sm font-semibold flex items-center gap-2">
                <GitBranch className="w-4 h-4 text-primary" /> Financial Twin Evolution
              </CardTitle>
            </CardHeader>
            <CardContent className="p-4">
              {loading ? (
                <div className="flex items-center justify-center h-48"><Loader2 className="w-8 h-8 animate-spin text-muted-foreground" /></div>
              ) : chartData.length === 0 ? (
                <p className="text-xs text-muted-foreground text-center py-12">No twin history found. Run the twin bootstrap or wait for data.</p>
              ) : (
                <>
                  <ResponsiveContainer width="100%" height={200}>
                    <LineChart data={chartData} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                      <XAxis dataKey="ver" tick={{ fontSize: 10 }} />
                      <YAxis tick={{ fontSize: 10 }} domain={[0, 100]} />
                      <Tooltip contentStyle={{ fontSize: 11 }} formatter={(v: any, n: string) => [`${v}${n==="cibil"?"":"%"}`, n]} />
                      <Line type="monotone" dataKey="risk" stroke="#ef4444" strokeWidth={2} dot={{ r: 3 }} name="Risk %" />
                      <Line type="monotone" dataKey="cibil" stroke="#c8ff00" strokeWidth={2} dot={{ r: 3 }} name="CIBIL-Like" />
                    </LineChart>
                  </ResponsiveContainer>
                  <div className="mt-3 space-y-1.5 max-h-40 overflow-y-auto pr-1">
                    {[...chartData].reverse().map((v, i) => (
                      <div key={i} className="flex items-center justify-between text-xs bg-muted/40 rounded px-3 py-1.5">
                        <span className="font-mono text-muted-foreground">{v.ver}</span>
                        <span className="capitalize text-foreground/80">{v.persona}</span>
                        <span style={{ color: riskColor(v.risk) }}>Risk {v.risk}%</span>
                        <span className="text-muted-foreground">{fmtTs(v.ts)}</span>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </CardContent>
          </Card>

          {/* Intervention triggers */}
          {triggers.length > 0 && (
            <Card className="border-border shadow-sm">
              <CardHeader className="py-3 px-4 border-b">
                <CardTitle className="text-sm font-semibold flex items-center gap-2">
                  <Zap className="w-4 h-4 text-primary" /> Active Intervention Signals
                  <Badge variant="outline" className="text-xs ml-auto">{triggers.length}</Badge>
                </CardTitle>
              </CardHeader>
              <CardContent className="p-4 space-y-2">
                {triggers.map((t: any, i: number) => (
                  <div key={i} className={cn("border rounded-lg px-3 py-2 text-xs", SEVERITY_COLOR[t.severity ?? "low"])}>
                    <div className="flex items-center justify-between mb-0.5">
                      <span className="font-semibold">{t.trigger_id ?? t.name ?? "Alert"}</span>
                      <Badge variant="outline" className="text-[10px] h-4">{t.severity ?? "low"}</Badge>
                    </div>
                    <p className="text-foreground/70">{t.message ?? t.description ?? ""}</p>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}
        </TabsContent>
        {/* Transactions tab */}
        <TabsContent value="transactions">
           {twin && (
             <TimeSeriesPanel
               upiTimeline={twin.upi_timeline ?? []}
               ewbTimeline={twin.ewb_timeline ?? []}
               twinTimeline={twinTimeline}
               windows={twin.windows}
               scoreHistory={scoreHistory}
               title="Financial Activity — 12 Month Timeline"
               entityType="individual"
               account={user?.account}
             />
           )}
        </TabsContent>

        {/* What-If Simulation */}
        <TabsContent value="simulation">
          <Card className="border-border shadow-sm">
            <CardHeader className="py-3 px-4 border-b">
              <CardTitle className="text-sm font-semibold flex items-center gap-2">
                <Activity className="w-4 h-4 text-primary" /> What-If Life Event Simulator
                <Badge variant="outline" className="text-[10px] ml-auto">≤10s SLA</Badge>
              </CardTitle>
            </CardHeader>
            <CardContent className="p-5">
              <Card className="border-border/70 shadow-sm mb-5">
                <CardHeader className="py-3 px-4 border-b">
                  <CardTitle className="text-sm font-semibold flex items-center gap-2">
                    <Activity className="w-4 h-4 text-primary" /> Custom Scenario Planner
                    <Badge variant="outline" className="text-[10px] ml-auto">Baseline vs Scenario</Badge>
                  </CardTitle>
                </CardHeader>
                <CardContent className="p-4 space-y-4">
                  <p className="text-xs text-muted-foreground leading-relaxed">
                    Define any scenario in financial terms (one-time outflow, recurring commitment, discounts, income/expense shocks).
                    The planner runs Monte Carlo baseline vs your scenario and returns a stability verdict.
                  </p>

                  <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-2.5">
                    <input
                      value={plannerName}
                      onChange={(e) => setPlannerName(e.target.value)}
                      placeholder="Scenario name"
                      className="h-8 rounded-md border border-border bg-background px-2 text-xs outline-none focus:ring-1 focus:ring-primary/40"
                    />
                    <input
                      type="number"
                      min={0}
                      step={1000}
                      value={plannerOneTimeOutflow}
                      onChange={(e) => setPlannerOneTimeOutflow(Number(e.target.value || 0))}
                      placeholder="One-time outflow (INR)"
                      className="h-8 rounded-md border border-border bg-background px-2 text-xs outline-none focus:ring-1 focus:ring-primary/40"
                    />
                    <input
                      type="number"
                      min={0}
                      step={500}
                      value={plannerMonthlyCommitment}
                      onChange={(e) => setPlannerMonthlyCommitment(Number(e.target.value || 0))}
                      placeholder="Monthly commitment (INR)"
                      className="h-8 rounded-md border border-border bg-background px-2 text-xs outline-none focus:ring-1 focus:ring-primary/40"
                    />
                    <input
                      type="number"
                      min={1}
                      max={120}
                      value={plannerTenureMonths}
                      onChange={(e) => setPlannerTenureMonths(Number(e.target.value || 1))}
                      placeholder="Tenure (months)"
                      className="h-8 rounded-md border border-border bg-background px-2 text-xs outline-none focus:ring-1 focus:ring-primary/40"
                    />
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <div className="space-y-1">
                      <div className="flex items-center justify-between">
                        <label className="text-[11px] font-medium text-muted-foreground">Discount %</label>
                        <span className="text-[11px] font-mono text-foreground">{plannerDiscountPct}%</span>
                      </div>
                      <Slider value={[plannerDiscountPct]} onValueChange={(v) => setPlannerDiscountPct(Number(v[0] ?? 0))} min={0} max={50} step={1} />
                    </div>
                    <div className="space-y-1">
                      <div className="flex items-center justify-between">
                        <label className="text-[11px] font-medium text-muted-foreground">Income Shock %</label>
                        <span className="text-[11px] font-mono text-foreground">{plannerIncomeShockPct}%</span>
                      </div>
                      <Slider value={[plannerIncomeShockPct]} onValueChange={(v) => setPlannerIncomeShockPct(Number(v[0] ?? 0))} min={-100} max={50} step={5} />
                    </div>
                    <div className="space-y-1">
                      <div className="flex items-center justify-between">
                        <label className="text-[11px] font-medium text-muted-foreground">Expense Shock %</label>
                        <span className="text-[11px] font-mono text-foreground">{plannerExpenseShockPct}%</span>
                      </div>
                      <Slider value={[plannerExpenseShockPct]} onValueChange={(v) => setPlannerExpenseShockPct(Number(v[0] ?? 0))} min={-30} max={100} step={5} />
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <Button className="h-8 text-xs gap-2" onClick={runCustomScenarioPlanner} disabled={plannerLoading}>
                      {plannerLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
                      {plannerLoading ? "Running planner..." : "Run Scenario Verdict"}
                    </Button>
                    <span className="text-[10px] text-muted-foreground">Uses your real monthly trend + twin stress engine.</span>
                  </div>

                  {plannerResult && plannerNarrative && (
                    <div className="space-y-3 pt-1">
                      <div className="border border-border/60 rounded-lg p-3 bg-muted/20 space-y-2">
                        <div className="flex items-center justify-between gap-2">
                          <p className="text-[11px] font-semibold text-foreground/90">In simple words</p>
                          <Badge
                            variant="outline"
                            className={cn(
                              "text-[10px] capitalize",
                              plannerResult.verdict === "comfortable"
                                ? "text-emerald-300 border-emerald-400/60"
                                : plannerResult.verdict === "cautious"
                                  ? "text-amber-300 border-amber-400/60"
                                  : "text-red-300 border-red-400/60",
                            )}
                          >
                            {plannerResult.verdict}
                          </Badge>
                        </div>
                        <p className="text-sm text-foreground/85 leading-relaxed">{plannerNarrative.opener}</p>
                        <div className="space-y-1">
                          {plannerNarrative.points.map((line: string, idx: number) => (
                            <p key={`${line}:${idx}`} className="text-[12px] text-muted-foreground leading-relaxed">- {line}</p>
                          ))}
                        </div>
                        <p className="text-[12px] text-foreground/85">
                          Recommendation: <span className="text-muted-foreground">{plannerNarrative.recommendation}</span>
                        </p>
                      </div>

                      <div className="flex items-center justify-between gap-2 border border-border/50 rounded-lg px-3 py-2 bg-muted/15">
                        <div className="text-[11px] text-muted-foreground">
                          Scenario: {plannerResult.scenario_name} · Computed: {fmtTs(String(plannerResult.computed_at ?? new Date().toISOString()))}
                        </div>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-7 text-[11px]"
                          onClick={() => setShowPlannerAdvanced((v) => !v)}
                        >
                          {showPlannerAdvanced ? "Hide technical details" : "Show technical details"}
                        </Button>
                      </div>

                      {showPlannerAdvanced && (
                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                          <div className="bg-muted/35 rounded-lg px-2 py-2">
                            <p className="text-[10px] text-muted-foreground">Baseline 90d Default</p>
                            <p className="text-xs font-semibold">{fmtPctProb(Number(plannerResult.baseline_default_90d ?? 0))}</p>
                          </div>
                          <div className="bg-muted/35 rounded-lg px-2 py-2">
                            <p className="text-[10px] text-muted-foreground">Scenario 90d Default</p>
                            <p className="text-xs font-semibold">{fmtPctProb(Number(plannerResult.stressed_default_90d ?? 0))}</p>
                          </div>
                          <div className="bg-muted/35 rounded-lg px-2 py-2">
                            <p className="text-[10px] text-muted-foreground">Projected Health</p>
                            <p className="text-xs font-semibold">{Number(plannerResult.projected_health ?? 0)}/100</p>
                          </div>
                          <div className="bg-muted/35 rounded-lg px-2 py-2">
                            <p className="text-[10px] text-muted-foreground">Monthly Surplus (post)</p>
                            <p className={cn("text-xs font-semibold", Number(plannerResult.monthly_surplus_after_commitment ?? 0) < 0 ? "text-red-300" : "text-emerald-300")}>{fmtINR(Math.round(Number(plannerResult.monthly_surplus_after_commitment ?? 0)))}</p>
                          </div>
                          <div className="bg-muted/35 rounded-lg px-2 py-2">
                            <p className="text-[10px] text-muted-foreground">Impact Score</p>
                            <p className={cn("text-xs font-semibold", Number(plannerResult.impact_score ?? 0) >= 55 ? "text-red-300" : Number(plannerResult.impact_score ?? 0) >= 25 ? "text-amber-300" : "text-emerald-300")}>{Number(plannerResult.impact_score ?? 0)}/100</p>
                          </div>
                          <div className="bg-muted/35 rounded-lg px-2 py-2">
                            <p className="text-[10px] text-muted-foreground">Coverage Months</p>
                            <p className="text-xs font-semibold">{Number.isFinite(Number(plannerResult.one_time_coverage_months)) ? Number(plannerResult.one_time_coverage_months).toFixed(1) : "inf"}</p>
                          </div>
                          <div className="bg-muted/35 rounded-lg px-2 py-2">
                            <p className="text-[10px] text-muted-foreground">Components</p>
                            <p className="text-xs font-semibold">{(plannerResult.scenario_components ?? []).length > 0 ? (plannerResult.scenario_components as string[]).join(", ") : "baseline"}</p>
                          </div>
                          <div className="bg-muted/35 rounded-lg px-2 py-2">
                            <p className="text-[10px] text-muted-foreground">Sim IDs</p>
                            <p className="text-[10px] font-mono text-muted-foreground truncate">{String(plannerResult.baseline_sim_id ?? "n/a")} -&gt; {String(plannerResult.stressed_sim_id ?? "n/a")}</p>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </CardContent>
              </Card>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-5">
                  <div>
                    <p className="text-xs font-semibold text-muted-foreground mb-2">Quick Life Events</p>
                    <div className="flex flex-wrap gap-2">
                      {[
                        { id: "baseline", label: "Baseline" },
                        { id: "job_loss", label: "Job Loss" },
                        { id: "income_drop", label: "Income -20%" },
                        { id: "spending_shock", label: "Spending +30%" },
                        { id: "recovery", label: "Recovery" },
                      ].map((s) => (
                        <Button key={s.id} size="sm" variant={scenario === s.id ? "default" : "outline"} className="text-xs h-7" onClick={() => applyScenario(s.id)}>
                          {s.label}
                        </Button>
                      ))}
                    </div>
                  </div>

                  <div className="space-y-4">
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <label className="text-xs font-medium">Income Change</label>
                        <span className={cn("text-xs font-bold font-mono", incomeChg[0] < 0 ? "text-red-400" : "text-emerald-400")}>
                          {incomeChg[0] > 0 ? "+" : ""}{incomeChg[0]}%
                        </span>
                      </div>
                      <Slider value={incomeChg} onValueChange={setIncomeChg} min={-100} max={50} step={5} />
                    </div>
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <label className="text-xs font-medium">Spending Change</label>
                        <span className={cn("text-xs font-bold font-mono", spendChg[0] > 0 ? "text-red-400" : "text-emerald-400")}>
                          {spendChg[0] > 0 ? "+" : ""}{spendChg[0]}%
                        </span>
                      </div>
                      <Slider value={spendChg} onValueChange={setSpendChg} min={-50} max={100} step={5} />
                    </div>
                  </div>

                  <Button className="w-full gap-2" onClick={() => runSimulation({ source: "manual" })} disabled={simRunning}>
                    {simRunning ? <><Loader2 className="w-4 h-4 animate-spin" /> Running simulation…</> : <><Play className="w-4 h-4" /> Simulate</>}
                  </Button>

                  {simRunning && (
                    <div className="space-y-1">
                      <Progress value={Math.min(simProgress, 100)} indicatorClassName="bg-primary" />
                      <p className="text-[10px] text-muted-foreground text-center">{Math.min(Math.round(simProgress), 100)}% complete</p>
                    </div>
                  )}
                </div>

                <div>
                  {!simResult && !simRunning && (
                    <div className="flex flex-col items-center justify-center h-full gap-3 text-muted-foreground">
                      <TrendingUp className="w-10 h-10 opacity-20" />
                      <p className="text-xs text-center">Pick a life event or adjust sliders and simulate to see projected impact</p>
                    </div>
                  )}

                  {simResult && (
                    <div className="space-y-4 animate-in fade-in slide-in-from-bottom-2 duration-400">
                      <div className="grid grid-cols-2 gap-3">
                        {[
                          { label: "Default P (90d)", value: day90?.default_probability !== undefined ? `${((day90.default_probability ?? 0) * 100).toFixed(1)}%` : "—", bad: (day90?.default_probability ?? 0) > 0.3 },
                          { label: "Pre-Qual Offer", value: newCreditLimit ? fmtINR(Number(newCreditLimit)) : "—", bad: false },
                          { label: "EWS Signal", value: ews.severity ?? ews.level ?? ews.status ?? "—", bad: ["RED", "ORANGE"].includes(String(ews.severity ?? ews.level ?? "").toUpperCase()) },
                          { label: "Scenario", value: scenario.replace(/_/g, " "), bad: false },
                        ].map((m) => (
                          <div key={m.label} className="bg-muted/40 rounded-lg p-3">
                            <p className="text-[10px] text-muted-foreground">{m.label}</p>
                            <p className={cn("text-sm font-bold mt-0.5 capitalize", m.bad ? "text-red-400" : "text-foreground")}>{m.value}</p>
                          </div>
                        ))}
                      </div>

                      {fanChart.length > 0 && (
                        <ResponsiveContainer width="100%" height={130}>
                          <AreaChart data={fanChart.slice(0, 60)} margin={{ top: 5, right: 5, left: -25, bottom: 0 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                            <XAxis dataKey="day" tick={{ fontSize: 9 }} />
                            <YAxis tick={{ fontSize: 9 }} />
                            <Tooltip contentStyle={{ fontSize: 10 }} />
                            <Area type="monotone" dataKey="p90" stroke="#22c55e" fill="#22c55e" fillOpacity={0.1} strokeWidth={1} />
                            <Area type="monotone" dataKey="p50" stroke="#c8ff00" fill="none" strokeWidth={2} />
                            <Area type="monotone" dataKey="p10" stroke="#ef4444" fill="#ef4444" fillOpacity={0.1} strokeWidth={1} />
                          </AreaChart>
                        </ResponsiveContainer>
                      )}

                      {(simResult?.simulation_windows || simResult?.temporal_projections) && (
                        <div className="space-y-1">
                          <p className="text-[10px] font-semibold text-muted-foreground">30 / 60 / 90 Day Default Trajectory</p>
                          {[30, 60, 90].map((d) => {
                            const point = simResult?.simulation_windows?.[`day_${d}`] ?? simResult?.temporal_projections?.[`day_${d}`] ?? {};
                            const dp = Number(point?.default_probability ?? 0);
                            return (
                              <div key={d} className="flex items-center justify-between text-xs bg-muted/30 border border-border/40 rounded px-2 py-1">
                                <span>D{d}</span>
                                <span className={cn(dp > 0.3 ? "text-red-300" : dp > 0.15 ? "text-amber-300" : "text-emerald-300")}>{(dp * 100).toFixed(1)}%</span>
                              </div>
                            );
                          })}
                        </div>
                      )}

                      <Button variant="outline" className="w-full gap-2 text-xs h-8" onClick={() => exportAudit("json")} disabled={generating}>
                        {generating ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />}
                        Save Simulation to My Report
                      </Button>
                    </div>
                  )}
                </div>
              </div>

              <div className="mt-6 grid grid-cols-1 xl:grid-cols-2 gap-4">
                <Card className="border-border shadow-sm">
                  <CardHeader className="py-3 px-4 border-b">
                    <CardTitle className="text-sm font-semibold flex items-center gap-2">
                      <MessageSquare className="w-4 h-4 text-primary" /> Tier 8 Negotiation Console
                      {negSession?.status && (
                        <Badge variant="outline" className="text-[10px] ml-auto capitalize">
                          {String(negSession.status).replace(/_/g, " ")}
                        </Badge>
                      )}
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="p-4 space-y-4">
                    <div className="grid grid-cols-3 gap-2">
                      <div className="bg-muted/40 rounded-lg p-2">
                        <p className="text-[10px] text-muted-foreground">Approved Amount</p>
                        <p className="text-xs font-semibold">{activeOffer?.approved_amount ? fmtINR(Number(activeOffer.approved_amount)) : "—"}</p>
                      </div>
                      <div className="bg-muted/40 rounded-lg p-2">
                        <p className="text-[10px] text-muted-foreground">APR</p>
                        <p className="text-xs font-semibold">{activeOffer?.apr ? `${activeOffer.apr}%` : "—"}</p>
                      </div>
                      <div className="bg-muted/40 rounded-lg p-2">
                        <p className="text-[10px] text-muted-foreground">Risk Band</p>
                        <p className="text-xs font-semibold capitalize">{activeOffer?.risk_band?.replace(/_/g, " ") ?? "—"}</p>
                      </div>
                    </div>

                    <div className="flex flex-wrap gap-2">
                      <Button size="sm" variant="outline" className="h-7 text-xs" onClick={fetchOffer} disabled={negBusy}>
                        {negBusy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : null}
                        Generate Offer
                      </Button>
                      <Button
                        size="sm"
                        className="h-7 text-xs"
                        onClick={startNegotiation}
                        disabled={negBusy}
                      >
                        Start Negotiation
                      </Button>
                    </div>

                    {negSession?.selected && (
                      <div className="grid grid-cols-3 gap-2 text-xs">
                        <div className="bg-muted/30 rounded px-2 py-1 border border-border/50">
                          EMI: <span className="font-semibold">{fmtINR(Number(negSession.selected.monthly_emi ?? 0))}</span>
                        </div>
                        <div className="bg-muted/30 rounded px-2 py-1 border border-border/50">
                          Tenure: <span className="font-semibold">{Number(negSession.selected.tenure_months ?? 0)} mo</span>
                        </div>
                        <div className="bg-muted/30 rounded px-2 py-1 border border-border/50">
                          Moratorium: <span className="font-semibold">{Number(negSession.selected.moratorium_days ?? 0)} d</span>
                        </div>
                      </div>
                    )}

                    <div className="border border-border/60 rounded-lg p-2 space-y-2 bg-muted/15">
                      <div className="max-h-44 overflow-y-auto space-y-1 pr-1">
                        {(negSession?.conversation ?? []).length === 0 ? (
                          <p className="text-xs text-muted-foreground">Start a negotiation session to see the multi-turn dialogue.</p>
                        ) : (
                          (negSession.conversation as any[]).map((turn: any, idx: number) => (
                            <div
                              key={`${turn.ts ?? idx}:${idx}`}
                              className={cn(
                                "text-xs rounded px-2 py-1 border",
                                turn.role === "agent"
                                  ? "bg-primary/10 border-primary/20"
                                  : "bg-muted/40 border-border/60",
                              )}
                            >
                              <p className="font-semibold capitalize mb-0.5">{turn.role ?? "agent"}</p>
                              <p className="text-foreground/80 leading-relaxed">{turn.message ?? ""}</p>
                            </div>
                          ))
                        )}
                      </div>

                      <div className="flex items-center gap-2">
                        <input
                          value={negInput}
                          onChange={(e) => setNegInput(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") {
                              e.preventDefault();
                              sendNegotiationTurn();
                            }
                          }}
                          placeholder="Try: lower emi, extend tenure, defer, confirm"
                          className="flex-1 h-8 rounded-md border border-border bg-background px-2 text-xs outline-none focus:ring-1 focus:ring-primary/40"
                          disabled={negBusy || !negSession?.session_id || negSession?.status !== "active"}
                        />
                        <Button
                          size="sm"
                          className="h-8 text-xs px-2"
                          onClick={sendNegotiationTurn}
                          disabled={negBusy || !negSession?.session_id || !negInput.trim() || negSession?.status !== "active"}
                        >
                          {negBusy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                <Card className="border-border shadow-sm">
                  <CardHeader className="py-3 px-4 border-b">
                    <CardTitle className="text-sm font-semibold flex items-center gap-2">
                      <Clock3 className="w-4 h-4 text-primary" /> Continuous Tier 8 Monitoring
                      <Badge variant="outline" className="text-[10px] ml-auto">Live Feed</Badge>
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="p-4 space-y-4">
                    <div className="flex flex-wrap items-center gap-2">
                      <Button
                        size="sm"
                        variant={autoSimEnabled ? "default" : "outline"}
                        className="h-7 text-xs"
                        onClick={() => setAutoSimEnabled((v) => !v)}
                      >
                        {autoSimEnabled ? "Auto Sim ON" : "Auto Sim OFF"}
                      </Button>
                      {[60, 120, 300].map((secs) => (
                        <Button
                          key={secs}
                          size="sm"
                          variant={autoSimEverySec === secs ? "default" : "outline"}
                          className="h-7 text-xs"
                          onClick={() => setAutoSimEverySec(secs)}
                        >
                          {secs}s
                        </Button>
                      ))}
                      <span className="text-[10px] text-muted-foreground ml-auto">
                        Last simulation: {lastSimAt ? fmtTs(lastSimAt) : "never"}
                      </span>
                    </div>

                    <div className="max-h-80 overflow-y-auto space-y-2 pr-1">
                      {liveFeed.length === 0 ? (
                        <p className="text-xs text-muted-foreground">No interventions yet. Feed updates from trigger polling and simulation runs.</p>
                      ) : (
                        liveFeed.map((evt: any) => {
                          const sev = ["critical", "high", "medium", "low"].includes(evt.severity) ? evt.severity : "low";
                          return (
                            <div key={evt.id} className={cn("border rounded-lg px-3 py-2 text-xs", SEVERITY_COLOR[sev])}>
                              <div className="flex items-center justify-between mb-0.5">
                                <span className="font-semibold">{evt.title}</span>
                                <span className="text-[10px] text-muted-foreground">{fmtTs(evt.ts)}</span>
                              </div>
                              <p className="text-foreground/75 leading-relaxed">{evt.detail}</p>
                            </div>
                          );
                        })
                      )}
                    </div>
                  </CardContent>
                </Card>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* AI Reasoning */}
        <TabsContent value="reasoning">
          <ReasoningTab cotSteps={cotSteps} loading={loading} />
        </TabsContent>

        {/* Data Export */}
        <TabsContent value="export">
          <Card className="border-border shadow-sm">
            <CardHeader className="py-3 px-4 border-b">
              <CardTitle className="text-sm font-semibold flex items-center gap-2">
                <Download className="w-4 h-4 text-primary" /> Export My Financial Data
                <Badge className="text-[10px] bg-primary/10 text-primary border-primary/20 ml-auto">Data Portability</Badge>
              </CardTitle>
            </CardHeader>
            <CardContent className="p-5">
              <p className="text-xs text-muted-foreground mb-4 leading-relaxed">
                Download your complete personal financial intelligence record — your twin state history, AI reasoning, intervention alerts, and any simulations you've run.
                Your data, your right.
              </p>
              <Button className="gap-2" onClick={() => exportAudit("json")} disabled={generating}>
                {generating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
                {generating ? "Preparing report…" : "Download My Complete Report (JSON)"}
              </Button>

              <div className="mt-4 text-[10px] text-muted-foreground border border-border/50 rounded-lg p-3 bg-muted/20 space-y-0.5">
                <p className="font-semibold text-foreground/70">Your report includes:</p>
                {[
                  "Current & historical Digital Twin state",
                  "AI reasoning chain explaining your score",
                  "Intervention alerts that fired on your profile",
                  "Any What-If simulation results from this session",
                  "Early Warning System (EWS) snapshot",
                ].map((item) => (
                  <p key={item} className="flex items-center gap-1.5">
                    <CheckCircle2 className="w-2.5 h-2.5 text-emerald-400 shrink-0" /> {item}
                  </p>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
