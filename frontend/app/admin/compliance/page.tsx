"use client";
import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/dib/authContext";
import { twinApi, simulationApi, reasoningApi, adminApi, vigilanceApi } from "@/dib/api";
import { PageHeader } from "@/components/shared";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Slider } from "@/components/ui/slider";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Progress } from "@/components/ui/progress";
import {
  AlertTriangle, RefreshCw, Download, Play, Activity,
  BarChart3, Shield, Brain, Clock, TrendingUp, TrendingDown,
  FileText, Zap, Eye, GitBranch, CheckCircle2, XCircle,
  ChevronDown, ChevronRight, Loader2, Settings,
} from "lucide-react";
import {
  AreaChart, Area, LineChart, Line, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  RadarChart, Radar, PolarGrid, PolarAngleAxis, ReferenceLine,
} from "recharts";
import { cn } from "@/dib/utils";

// ─── helpers ───────────────────────────────────────────────────────────────
function riskColor(score: number) {
  if (score >= 75) return "#ef4444";
  if (score >= 50) return "#f59e0b";
  return "#22c55e";
}

function fmtTs(ts: string) {
  try {
    return new Date(ts).toLocaleString("en-IN", {
      day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit",
    });
  } catch {
    return ts;
  }
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

// ─── Twin Timeline Card ──────────────────────────────────────────────────────
function TwinTimeline({ userId }: { userId: string }) {
  const [history, setHistory] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    twinApi.getHistory(userId)
      .then((d: any) => setHistory(Array.isArray(d) ? d : (d?.history ?? [])))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [userId]);

  const chartData = history.map((v: any) => ({
    ver: `v${v.version ?? "?"}`,
    risk: Math.round((v.risk_score ?? 0) * 100),
    liquidity: Math.round((v.liquidity_health ?? 0) * 100),
    credit: v.credit_score ?? v.cibil_like_score ?? v.cibil_score ?? 0,
    ts: v.last_updated ?? v.created_at ?? "",
    persona: v.persona ?? "unknown",
  }));

  return (
    <Card className="border-border shadow-sm h-full">
      <CardHeader className="py-3 px-4 border-b flex-row items-center justify-between">
        <CardTitle className="text-sm font-semibold flex items-center gap-2">
          <GitBranch className="w-4 h-4 text-primary" /> Digital Twin Evolution
        </CardTitle>
        {loading && <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />}
      </CardHeader>
      <CardContent className="p-4">
        {history.length === 0 && !loading ? (
          <p className="text-xs text-muted-foreground text-center py-8">No twin history found for this user.</p>
        ) : (
          <>
            <ResponsiveContainer width="100%" height={180}>
              <LineChart data={chartData} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="ver" tick={{ fontSize: 10 }} />
                <YAxis tick={{ fontSize: 10 }} domain={[0, 100]} />
                <Tooltip contentStyle={{ fontSize: 11 }} formatter={(v: any, n: string) => [`${v}${n === "credit" ? "" : "%"}`, n]} />
                <Line type="monotone" dataKey="risk" stroke="#ef4444" strokeWidth={2} dot={{ r: 3 }} name="Risk" />
                <Line type="monotone" dataKey="liquidity" stroke="#22c55e" strokeWidth={2} dot={{ r: 3 }} name="Liquidity" />
                <Line type="monotone" dataKey="credit" stroke="#c8ff00" strokeWidth={2} dot={{ r: 3 }} name="Credit Score" />
              </LineChart>
            </ResponsiveContainer>

            <div className="mt-3 space-y-1.5 max-h-44 overflow-y-auto pr-1">
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
  );
}

// ─── Risk Projection Graph ───────────────────────────────────────────────────
function RiskProjectionGraph({ userId }: { userId: string }) {
  const [fanData, setFanData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    simulationApi.getFanChart(userId)
      .then(setFanData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [userId]);

  const formatted = (() => {
    if (Array.isArray(fanData?.fan_chart_series)) {
      return fanData.fan_chart_series.map((p: any, idx: number) => ({
        month: p.month ?? `D${idx + 1}`,
        p10: Number(p.p10 ?? 0),
        p50: Number(p.p50 ?? 0),
        p90: Number(p.p90 ?? 0),
      }));
    }

    if (fanData?.fan_chart && !Array.isArray(fanData.fan_chart)) {
      const fan = fanData.fan_chart;
      const p10: number[] = Array.isArray(fan?.p10) ? fan.p10 : [];
      const p50: number[] = Array.isArray(fan?.p50) ? fan.p50 : [];
      const p90: number[] = Array.isArray(fan?.p90) ? fan.p90 : [];
      const n = Math.min(p10.length, p50.length, p90.length);
      return Array.from({ length: n }).map((_, idx) => ({
        month: `D${idx + 1}`,
        p10: Number(p10[idx] ?? 0),
        p50: Number(p50[idx] ?? 0),
        p90: Number(p90[idx] ?? 0),
      }));
    }

    const chartData: any[] = Array.isArray(fanData?.fan_chart)
      ? fanData.fan_chart
      : (Array.isArray(fanData?.projections) ? fanData.projections : []);
    return chartData.map((p: any, idx: number) => ({
      month: p.month ?? p.t ?? p.period ?? `D${idx + 1}`,
      p10: Number(p.p10 ?? p.pessimistic ?? 0),
      p50: Number(p.p50 ?? p.base ?? 0),
      p90: Number(p.p90 ?? p.optimistic ?? 0),
    }));
  })();

  return (
    <Card className="border-border shadow-sm h-full">
      <CardHeader className="py-3 px-4 border-b flex-row items-center justify-between">
        <CardTitle className="text-sm font-semibold flex items-center gap-2">
          <TrendingUp className="w-4 h-4 text-primary" /> Risk Projection (Monte Carlo Fan)
        </CardTitle>
        {loading && <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />}
      </CardHeader>
      <CardContent className="p-4">
        {formatted.length === 0 && !loading ? (
          <p className="text-xs text-muted-foreground text-center py-8">No projection data available.</p>
        ) : (
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={formatted} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="p90" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#22c55e" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#22c55e" stopOpacity={0.0} />
                </linearGradient>
                <linearGradient id="p10" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#ef4444" stopOpacity={0.0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
              <XAxis dataKey="month" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} />
              <Tooltip contentStyle={{ fontSize: 11 }} />
              <Area type="monotone" dataKey="p90" stroke="#22c55e" fill="url(#p90)" strokeWidth={1.5} name="Optimistic (P90)" />
              <Area type="monotone" dataKey="p50" stroke="#c8ff00" fill="none" strokeWidth={2.5} name="Base (P50)" />
              <Area type="monotone" dataKey="p10" stroke="#ef4444" fill="url(#p10)" strokeWidth={1.5} name="Pessimistic (P10)" />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  );
}

// ─── Intervention History ────────────────────────────────────────────────────
function InterventionHistory({ userId }: { userId: string }) {
  const [triggers, setTriggers] = useState<any[]>([]);
  const [twinAudit, setTwinAudit] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      twinApi.getTriggers(userId).catch(() => []),
      twinApi.getAudit(userId).catch(() => []),
    ]).then(([t, a]) => {
      setTriggers(Array.isArray(t) ? t : (t as any)?.triggers ?? []);
      const records = Array.isArray(a)
        ? a
        : (Array.isArray((a as any)?.records)
          ? (a as any).records
          : (Array.isArray((a as any)?.history) ? (a as any).history : []));
      setTwinAudit(records);
    }).finally(() => setLoading(false));
  }, [userId]);

  const SEVERITY_COLOR: Record<string, string> = {
    critical: "text-red-400 bg-red-500/10 border-red-500/20",
    high: "text-orange-400 bg-orange-500/10 border-orange-500/20",
    medium: "text-amber-400 bg-amber-500/10 border-amber-500/20",
    low: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
  };

  return (
    <Card className="border-border shadow-sm h-full">
      <CardHeader className="py-3 px-4 border-b flex-row items-center justify-between">
        <CardTitle className="text-sm font-semibold flex items-center gap-2">
          <Zap className="w-4 h-4 text-primary" /> Intervention History
        </CardTitle>
        <Badge variant="outline" className="text-xs">{triggers.length} triggers</Badge>
      </CardHeader>
      <CardContent className="p-4">
        {loading ? (
          <div className="flex items-center justify-center h-32"><Loader2 className="w-6 h-6 animate-spin text-muted-foreground" /></div>
        ) : triggers.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-32 text-muted-foreground gap-2">
            <CheckCircle2 className="w-8 h-8 text-emerald-500" />
            <p className="text-xs">No intervention triggers fired</p>
          </div>
        ) : (
          <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
            {triggers.map((t: any, i: number) => (
              <div key={i} className={cn("border rounded-lg px-3 py-2 text-xs", SEVERITY_COLOR[t.severity ?? "low"])}>
                <div className="flex items-center justify-between mb-1">
                  <span className="font-semibold">{t.trigger_id ?? t.name ?? "Trigger"}</span>
                  <Badge variant="outline" className="text-[10px] h-4">{t.severity ?? "low"}</Badge>
                </div>
                <p className="text-foreground/70 leading-relaxed">{t.message ?? t.description ?? "No description."}</p>
                {t.action_taken && (
                  <p className="mt-1 opacity-70">→ {t.action_taken}</p>
                )}
              </div>
            ))}
          </div>
        )}
        {twinAudit.length > 0 && (
          <>
            <p className="text-xs font-semibold text-muted-foreground mt-4 mb-2">Twin State Changes</p>
            <div className="space-y-1.5 max-h-32 overflow-y-auto pr-1">
              {twinAudit.slice(0, 8).map((a: any, i: number) => (
                <div key={i} className="flex items-center justify-between text-xs bg-muted/40 rounded px-2 py-1">
                  <span className="font-mono text-muted-foreground">{a.event_type ?? a.action ?? "update"}</span>
                  <span className="text-foreground/70 truncate max-w-[60%]">{a.summary ?? a.description ?? a.payload?.detail ?? ""}</span>
                  <span className="text-muted-foreground shrink-0">{fmtTs(a.timestamp ?? a.ts ?? "")}</span>
                </div>
              ))}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}

// ─── Credit Decision Log ─────────────────────────────────────────────────────
function CreditDecisionLog({ auditLog }: { auditLog: any[] }) {
  const creditEvents = auditLog.filter((e: any) =>
    ["loan_approved", "loan_denied", "score_submitted", "threshold_updated"].includes(e.action)
  );

  const ICON: Record<string, React.ReactNode> = {
    loan_approved: <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />,
    loan_denied: <XCircle className="w-3.5 h-3.5 text-red-400 shrink-0" />,
    score_submitted: <BarChart3 className="w-3.5 h-3.5 text-blue-400 shrink-0" />,
    threshold_updated: <Settings className="w-3.5 h-3.5 text-amber-400 shrink-0" />,
  };

  return (
    <Card className="border-border shadow-sm h-full">
      <CardHeader className="py-3 px-4 border-b flex-row items-center justify-between">
        <CardTitle className="text-sm font-semibold flex items-center gap-2">
          <FileText className="w-4 h-4 text-primary" /> Credit Decision Log
        </CardTitle>
        <Badge variant="outline" className="text-xs">{creditEvents.length} decisions</Badge>
      </CardHeader>
      <CardContent className="p-0 overflow-hidden">
        {creditEvents.length === 0 ? (
          <p className="text-xs text-center text-muted-foreground py-8">No credit decisions found.</p>
        ) : (
          <div className="divide-y divide-border max-h-72 overflow-y-auto">
            {creditEvents.map((e: any) => (
              <div key={e.id} className="flex items-start gap-3 px-4 py-2.5 hover:bg-muted/30">
                {ICON[e.action] ?? <Activity className="w-3.5 h-3.5 shrink-0" />}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-xs font-medium capitalize">{e.action.replace(/_/g, " ")}</span>
                    <span className="text-[10px] text-muted-foreground font-mono truncate">{e.target_id}</span>
                  </div>
                  <p className="text-[11px] text-muted-foreground mt-0.5">by {e.user_name} · {fmtTs(e.timestamp ?? e.ts ?? "")}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ─── Anomaly Heatmap ─────────────────────────────────────────────────────────
function AnomalyHeatmap({ userId }: { userId: string }) {
  const [cotData, setCotData] = useState<any>(null);
  const [reasoningResult, setReasoningResult] = useState<any>(null);
  const [vigilanceSummary, setVigilanceSummary] = useState<any>(null);
  const [twinState, setTwinState] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      reasoningApi.getCot(userId).catch(() => null),
      reasoningApi.getResult(userId).catch(() => null),
      vigilanceApi.getSummary(userId).catch(() => null),
      twinApi.get(userId).catch(() => null),
    ]).then(([cot, result, vig, twin]) => {
      setCotData(cot);
      setReasoningResult(result);
      setVigilanceSummary(vig);
      setTwinState(twin);
    })
      .finally(() => setLoading(false));
  }, [userId]);

  const base = cotData ?? reasoningResult ?? {};
  const anomalies: any[] = base?.anomalies ?? base?.flags ?? base?.active_flags ?? [];
  const riskScore = Math.max(0, Math.min(1, Number(twinState?.risk_score ?? 0.5)));
  const incomeStability = Math.max(0, Math.min(1, Number(twinState?.income_stability ?? 0.5)));
  const spendingVol = Math.max(0, Math.min(1, Number(twinState?.spending_volatility ?? 0.5)));
  const compliance = Math.max(0, Math.min(1, Number(base?.cot_trace?.confidence ?? base?.confidence ?? 0.7)));
  const deception = Math.max(0, Math.min(1, Number(vigilanceSummary?.deception_score ?? 0.12)));
  const networkSafety = 1 - deception;
  const drift = Math.max(0, Math.min(1, Number(base?.contradiction?.contradiction_score ?? riskScore * 0.6)));

  const radarData = [
    { subject: "Income Pattern", A: Math.round(incomeStability * 100) },
    { subject: "Spend Velocity", A: Math.round((1 - spendingVol) * 100) },
    { subject: "Identity Integrity", A: Math.round((1 - deception * 0.8) * 100) },
    { subject: "Network Safety", A: Math.round(networkSafety * 100) },
    { subject: "Compliance", A: Math.round(compliance * 100) },
    { subject: "Behavioral Drift", A: Math.round((1 - drift) * 100) },
  ];

  return (
    <Card className="border-border shadow-sm h-full">
      <CardHeader className="py-3 px-4 border-b flex-row items-center justify-between">
        <CardTitle className="text-sm font-semibold flex items-center gap-2">
          <Eye className="w-4 h-4 text-primary" /> Anomaly Intelligence Heatmap
        </CardTitle>
        {loading && <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />}
      </CardHeader>
      <CardContent className="p-4">
        <ResponsiveContainer width="100%" height={200}>
          <RadarChart data={radarData}>
            <PolarGrid stroke="rgba(255,255,255,0.1)" />
            <PolarAngleAxis dataKey="subject" tick={{ fontSize: 9, fill: "rgba(255,255,255,0.5)" }} />
            <Radar name="Risk Signal" dataKey="A" stroke="#c8ff00" fill="#c8ff00" fillOpacity={0.15} strokeWidth={2} />
          </RadarChart>
        </ResponsiveContainer>

        {anomalies.length > 0 && (
          <div className="mt-2 space-y-1.5">
            {anomalies.slice(0, 4).map((a: any, i: number) => (
              <div key={i} className="flex items-center gap-2 text-xs bg-red-500/10 border border-red-500/20 rounded px-2.5 py-1.5">
                <AlertTriangle className="w-3 h-3 text-red-400 shrink-0" />
                <span className="text-red-300">{a.description ?? a.flag ?? a}</span>
              </div>
            ))}
          </div>
        )}
        {anomalies.length === 0 && !loading && (
          <p className="text-xs text-center text-muted-foreground mt-2">No anomalies detected in latest CoT trace.</p>
        )}
      </CardContent>
    </Card>
  );
}

// ─── Live What-If Simulation Panel ───────────────────────────────────────────
function LiveWhatIfPanel({ userId }: { userId: string }) {
  const [incomeChg, setIncomeChg] = useState([0]);
  const [spendChg, setSpendChg] = useState([0]);
  const [scenario, setScenario] = useState("baseline");
  const [result, setResult] = useState<any>(null);
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState(0);

  const applyScenario = (s: string) => {
    setScenario(s);
    if (s === "job_loss") { setIncomeChg([-100]); setSpendChg([20]); }
    else if (s === "income_drop") { setIncomeChg([-20]); setSpendChg([0]); }
    else if (s === "spending_shock") { setIncomeChg([0]); setSpendChg([30]); }
    else if (s === "recovery") { setIncomeChg([15]); setSpendChg([-10]); }
    else { setIncomeChg([0]); setSpendChg([0]); }
  };

  const runSimulation = useCallback(async () => {
    setRunning(true);
    setResult(null);
    setProgress(0);

    // Animate progress bar over ~8s to reflect <10s SLA
    const interval = setInterval(() => {
      setProgress((prev) => {
        if (prev >= 90) { clearInterval(interval); return 90; }
        return prev + Math.random() * 12;
      });
    }, 700);

    try {
      const res = await adminApi.runTier10LiveWhatIf({
        user_id: userId,
        scenario_name: scenario,
        income_change_pct: incomeChg[0],
        expense_change_pct: spendChg[0],
        num_simulations: 1000,
        run_counterfactual: true,
      });
      clearInterval(interval);
      setProgress(100);
      setResult(res);
    } catch {
      clearInterval(interval);
      setProgress(0);
    } finally {
      setTimeout(() => setRunning(false), 500);
    }
  }, [userId, incomeChg, spendChg, scenario]);

  const simulation = result?.simulation ?? result ?? {};
  const fanChart: any[] = Array.isArray(simulation?.fan_chart_series)
    ? simulation.fan_chart_series
    : Array.isArray(simulation?.fan_chart?.p50)
      ? (simulation.fan_chart.p50 as number[]).map((_: number, i: number) => ({
          day: i + 1,
          p10: Number(simulation?.fan_chart?.p10?.[i] ?? 0),
          p50: Number(simulation?.fan_chart?.p50?.[i] ?? 0),
          p90: Number(simulation?.fan_chart?.p90?.[i] ?? 0),
        }))
      : [];
  const ews: any = simulation?.ews ?? simulation?.ews_snapshot ?? simulation?.risk_snapshot ?? {};
  const day90 = simulation?.simulation_windows?.day_90 ?? simulation?.temporal_projections?.day_90 ?? {};
  const newCreditLimit =
    result?.updated_credit_limit
    ?? simulation?.proactive_offer?.approved_amount
    ?? simulation?.recommended_credit_limit
    ?? simulation?.new_credit_limit;
  const updatedRiskScore = Number(result?.updated_risk_score ?? result?.updated_twin_state?.risk_score ?? NaN);
  const latencyMs = Number(result?.latency_ms ?? 0);
  const slaMet = Boolean(result?.sla_met);

  return (
    <Card className="border-border shadow-sm">
      <CardHeader className="py-3 px-4 border-b">
        <CardTitle className="text-sm font-semibold flex items-center gap-2">
          <Activity className="w-4 h-4 text-primary" /> Live What-If Simulation
          <Badge variant="outline" className="text-[10px] ml-auto">≤10s SLA</Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="p-5">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Controls */}
          <div className="space-y-5">
            <div>
              <p className="text-xs font-semibold text-muted-foreground mb-2">Quick Scenarios</p>
              <div className="flex flex-wrap gap-2">
                {[
                  { id: "baseline", label: "Baseline" },
                  { id: "job_loss", label: "Job Loss" },
                  { id: "income_drop", label: "Income −20%" },
                  { id: "spending_shock", label: "Spending +30%" },
                  { id: "recovery", label: "Recovery Mode" },
                ].map((s) => (
                  <Button
                    key={s.id}
                    size="sm"
                    variant={scenario === s.id ? "default" : "outline"}
                    className="text-xs h-7"
                    onClick={() => applyScenario(s.id)}
                  >
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
                <Slider
                  value={incomeChg}
                  onValueChange={setIncomeChg}
                  min={-100} max={50} step={5}
                  className="w-full"
                />
              </div>

              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="text-xs font-medium">Spending Change</label>
                  <span className={cn("text-xs font-bold font-mono", spendChg[0] > 0 ? "text-red-400" : "text-emerald-400")}>
                    {spendChg[0] > 0 ? "+" : ""}{spendChg[0]}%
                  </span>
                </div>
                <Slider
                  value={spendChg}
                  onValueChange={setSpendChg}
                  min={-50} max={100} step={5}
                  className="w-full"
                />
              </div>
            </div>

            <Button
              className="w-full gap-2"
              onClick={runSimulation}
              disabled={running}
            >
              {running ? (
                <><Loader2 className="w-4 h-4 animate-spin" /> Running Monte Carlo…</>
              ) : (
                <><Play className="w-4 h-4" /> Run Simulation</>
              )}
            </Button>

            {running && (
              <div className="space-y-1">
                <Progress value={Math.min(progress, 100)} indicatorClassName="bg-primary" />
                <p className="text-[10px] text-muted-foreground text-center">Running {Math.min(Math.round(progress), 100)}% complete</p>
              </div>
            )}
          </div>

          {/* Results */}
          <div>
            {!result && !running && (
              <div className="flex flex-col items-center justify-center h-full gap-3 text-muted-foreground">
                <Activity className="w-10 h-10 opacity-20" />
                <p className="text-xs text-center">Configure parameters and run a simulation to see projected outcomes</p>
              </div>
            )}

            {result && (
              <div className="space-y-4 animate-in fade-in slide-in-from-bottom-2 duration-400">
                <div className="grid grid-cols-2 gap-3">
                  {[
                    {
                      label: "Default P(90d)",
                      value: day90?.default_probability !== undefined
                        ? `${(Number(day90.default_probability) * 100).toFixed(1)}%`
                        : "—",
                      bad: Number(day90?.default_probability ?? 0) > 0.3,
                    },
                    {
                      label: "Updated Credit Limit",
                      value: newCreditLimit
                        ? `₹${(newCreditLimit / 100000).toFixed(1)}L`
                        : "—",
                      bad: false,
                    },
                    {
                      label: "Updated Twin Risk",
                      value: Number.isFinite(updatedRiskScore)
                        ? `${(updatedRiskScore * 100).toFixed(1)}%`
                        : "—",
                      bad: Number.isFinite(updatedRiskScore) ? updatedRiskScore > 0.6 : false,
                    },
                    {
                      label: "EWS Severity",
                      value: ews.severity ?? ews.level ?? ews.status ?? "—",
                      bad: ["RED", "ORANGE"].includes(String(ews.severity ?? ews.level ?? "").toUpperCase()),
                    },
                  ].map((m) => (
                    <div key={m.label} className="bg-muted/40 rounded-lg p-3">
                      <p className="text-[10px] text-muted-foreground">{m.label}</p>
                      <p className={cn("text-sm font-bold mt-0.5", m.bad ? "text-red-400" : "text-emerald-400")}>
                        {m.value}
                      </p>
                    </div>
                  ))}
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div className="bg-muted/40 rounded-lg p-3">
                    <p className="text-[10px] text-muted-foreground">Execution Latency</p>
                    <p className={cn("text-sm font-bold mt-0.5", slaMet ? "text-emerald-400" : "text-red-400")}>
                      {latencyMs > 0 ? `${latencyMs} ms` : "—"}
                    </p>
                  </div>
                  <div className="bg-muted/40 rounded-lg p-3">
                    <p className="text-[10px] text-muted-foreground">SLA (≤10s)</p>
                    <p className={cn("text-sm font-bold mt-0.5", slaMet ? "text-emerald-400" : "text-red-400")}>
                      {latencyMs > 0 ? (slaMet ? "Met" : "Breached") : "—"}
                    </p>
                  </div>
                </div>

                {fanChart.length > 0 && (
                  <ResponsiveContainer width="100%" height={140}>
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

                {result?.updated_twin_state && (
                  <div className="grid grid-cols-3 gap-2 text-xs">
                    <div className="bg-muted/30 rounded px-2 py-1 border border-border/50">
                      Liquidity: <span className="font-semibold">{String(result.updated_twin_state.liquidity_health ?? "—")}</span>
                    </div>
                    <div className="bg-muted/30 rounded px-2 py-1 border border-border/50">
                      Persona: <span className="font-semibold">{String(result.updated_twin_state.persona ?? "—")}</span>
                    </div>
                    <div className="bg-muted/30 rounded px-2 py-1 border border-border/50">
                      Credit Score: <span className="font-semibold">{String(result.updated_twin_state.credit_score ?? result.updated_twin_state.cibil_like_score ?? "—")}</span>
                    </div>
                  </div>
                )}

                {ews.top_risk_factors?.length > 0 && (
                  <div className="space-y-1">
                    <p className="text-[10px] font-semibold text-muted-foreground">Top Risk Drivers</p>
                    {ews.top_risk_factors.slice(0, 3).map((f: string, i: number) => (
                      <div key={i} className="flex items-center gap-2 text-xs text-red-300 bg-red-500/10 border border-red-500/20 rounded px-2 py-1">
                        <AlertTriangle className="w-3 h-3 shrink-0" /> {f}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// ─── LLM Reasoning Trace ─────────────────────────────────────────────────────
function ReasoningTracePanel({ userId }: { userId: string }) {
  const [cot, setCot] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<number[]>([]);

  useEffect(() => {
    reasoningApi.getCot(userId)
      .then(async (data) => {
        if (!data) {
          const fallback = await reasoningApi.getResult(userId).catch(() => null);
          setCot(fallback);
          return;
        }
        setCot(data);
      })
      .catch(async () => {
        const fallback = await reasoningApi.getResult(userId).catch(() => null);
        setCot(fallback);
      })
      .finally(() => setLoading(false));
  }, [userId]);

  const steps: any[] = normalizeCotSteps(cot);

  return (
    <Card className="border-border shadow-sm">
      <CardHeader className="py-3 px-4 border-b flex-row items-center justify-between">
        <CardTitle className="text-sm font-semibold flex items-center gap-2">
          <Brain className="w-4 h-4 text-primary" /> LLM Reasoning Trace (Chain of Thought)
        </CardTitle>
        {loading && <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />}
      </CardHeader>
      <CardContent className="p-4">
        {steps.length === 0 && !loading ? (
          <p className="text-xs text-muted-foreground text-center py-6">No CoT trace available. Run the reasoning engine first.</p>
        ) : (
          <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
            {steps.map((s: any, i: number) => {
              const open = expanded.includes(i);
              return (
                <div key={i} className="border border-border rounded-lg overflow-hidden">
                  <button
                    className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-muted/30 transition-colors"
                    onClick={() => setExpanded((prev) => open ? prev.filter((x) => x !== i) : [...prev, i])}
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

// ─── Audit Report Exporter ────────────────────────────────────────────────────
function AuditReportExporter({ userId, auditLog }: { userId: string; auditLog: any[] }) {
  const [generating, setGenerating] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  const triggerDownload = (blob: Blob, filename: string) => {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  const generateReport = async (format: "json" | "pdf") => {
    setGenerating(true);
    setExportError(null);
    try {
      if (format === "json") {
        const report = await adminApi.getTier10Report(userId);
        const merged = {
          ...report,
          ui_credit_decision_log_snapshot: auditLog.filter((e: any) =>
            ["loan_approved", "loan_denied", "score_submitted", "threshold_updated"].includes(e.action)
          ),
          exported_at: new Date().toISOString(),
        };
        const blob = new Blob([JSON.stringify(merged, null, 2)], { type: "application/json" });
        triggerDownload(blob, `neurocred_audit_${userId}_${Date.now()}.json`);
      } else {
        const { blob, filename } = await adminApi.downloadTier10ReportPdf(userId);
        triggerDownload(blob, filename);
      }
    } catch (error) {
      const msg = error instanceof Error ? error.message : "Failed to export report. Please retry.";
      setExportError(msg);
    } finally {
      setGenerating(false);
    }
  };

  return (
    <Card className="border-border shadow-sm">
      <CardHeader className="py-3 px-4 border-b">
        <CardTitle className="text-sm font-semibold flex items-center gap-2">
          <Download className="w-4 h-4 text-primary" /> Regulatory Audit Report
          <Badge className="text-[10px] bg-primary/10 text-primary border-primary/20 ml-auto">One-Click Export</Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="p-5">
        <p className="text-xs text-muted-foreground mb-4 leading-relaxed">
          Generates a complete compliance bundle per <strong>RBI Digital Lending Guidelines 2023 §4.2</strong>: twin state history,
          all LLM reasoning traces, credit decisions, intervention log, anomaly detections, and simulation artifacts.
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div className="border border-border rounded-xl p-4 space-y-2">
            <div className="flex items-center gap-2">
              <div className="p-2 bg-primary/10 rounded-lg"><FileText className="w-4 h-4 text-primary" /></div>
              <div>
                <p className="text-sm font-semibold">Full Audit Report</p>
                <p className="text-[10px] text-muted-foreground">JSON · full machine-readable compliance bundle</p>
              </div>
            </div>
            <Button
              className="w-full gap-2 text-xs h-8"
              disabled={generating}
              onClick={() => generateReport("json")}
            >
              {generating ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />}
              Export Report (JSON)
            </Button>
          </div>

          <div className="border border-border rounded-xl p-4 space-y-2">
            <div className="flex items-center gap-2">
              <div className="p-2 bg-emerald-500/10 rounded-lg"><FileText className="w-4 h-4 text-emerald-400" /></div>
              <div>
                <p className="text-sm font-semibold">Regulatory PDF</p>
                <p className="text-[10px] text-muted-foreground">PDF · compact compliance summary for auditors</p>
              </div>
            </div>
            <Button
              variant="outline"
              className="w-full gap-2 text-xs h-8"
              disabled={generating}
              onClick={() => generateReport("pdf")}
            >
              {generating ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />}
              Export Report (PDF)
            </Button>
          </div>
        </div>

        <div className="mt-4 text-[10px] text-muted-foreground border border-border/50 rounded-lg p-3 bg-muted/20 space-y-0.5">
          <p className="font-semibold text-foreground/70">Report Contents:</p>
          {[
            "Digital Twin state & evolution history",
            "LLM Chain-of-Thought reasoning traces",
            "Credit approval & denial decisioning log",
            "Fired intervention triggers & actions",
            "Anomaly detections & behavioral drift flags",
            "Monte Carlo simulation artifacts (if run)",
          ].map((item) => (
            <p key={item} className="flex items-center gap-1.5">
              <CheckCircle2 className="w-2.5 h-2.5 text-emerald-400 shrink-0" /> {item}
            </p>
          ))}
        </div>

        {exportError && (
          <div className="mt-3 text-xs text-red-300 border border-red-400/30 bg-red-500/10 rounded-lg px-3 py-2">
            {exportError}
          </div>
        )}
      </CardContent>
    </Card>
  );
}


// ─── Main Page ─────────────────────────────────────────────────────────────────
export default function ComplianceDashboard() {
  const { user } = useAuth();
  const router = useRouter();
  const [auditLog, setAuditLog] = useState<any[]>([]);
  const [twinUsers, setTwinUsers] = useState<string[]>([]);
  const [selectedUser, setSelectedUser] = useState<string>("");
  const [activeTab, setActiveTab] = useState("overview");

  useEffect(() => {
    if (!user) return;
    if (user.role !== "admin") { router.push("/unauthorized"); return; }
    adminApi.getAuditLog().then((d: any) => setAuditLog(Array.isArray(d) ? d : [])).catch(() => {});
    adminApi.getTwinUsers()
      .then((d: any) => {
        const ids: string[] = Array.isArray(d?.user_ids) ? d.user_ids : [];
        setTwinUsers(ids);
        if (ids.length > 0) setSelectedUser(ids[0]);
      })
      .catch(() => {});
  }, [user, router]);

  // Fallback: extract user IDs from audit log if twin-users fails
  useEffect(() => {
    if (twinUsers.length === 0 && auditLog.length > 0) {
      const ids = [...new Set(auditLog.map((e: any) => e.user_id).filter(Boolean))] as string[];
      setTwinUsers(ids);
      if (ids.length > 0 && !selectedUser) setSelectedUser(ids[0]);
    }
  }, [auditLog, twinUsers.length, selectedUser]);

  if (!user || user.role !== "admin") return null;

  return (
    <div className="p-6 max-w-[1600px] mx-auto space-y-6">
      <PageHeader
        title="Explainable Audit Repository"
        description="Full compliance dashboard — digital twin evolution, risk projections, intervention history, credit decisions, anomaly heatmap, live What-If, and one-click regulatory audit export."
        actions={
          <div className="flex items-center gap-2">
            {twinUsers.length > 0 && (
              <Select value={selectedUser} onValueChange={setSelectedUser}>
                <SelectTrigger className="w-48 h-8 text-xs">
                  <SelectValue placeholder="Select user" />
                </SelectTrigger>
                <SelectContent>
                  {twinUsers.map((uid) => (
                    <SelectItem key={uid} value={uid} className="text-xs font-mono">{uid}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
            <Button
              variant="outline" size="sm" className="gap-2 h-8 text-xs"
              onClick={() => {
                adminApi.getAuditLog().then((d: any) => setAuditLog(Array.isArray(d) ? d : [])).catch(() => {});
              }}
            >
              <RefreshCw className="w-3.5 h-3.5" /> Refresh
            </Button>
          </div>
        }
      />

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="mb-4">
          <TabsTrigger value="overview" className="text-xs">Overview</TabsTrigger>
          <TabsTrigger value="simulation" className="text-xs">Live Simulation</TabsTrigger>
          <TabsTrigger value="reasoning" className="text-xs">Reasoning Trace</TabsTrigger>
          <TabsTrigger value="export" className="text-xs">Audit Export</TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-4">
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
            {selectedUser && <TwinTimeline userId={selectedUser} />}
            {selectedUser && <RiskProjectionGraph userId={selectedUser} />}
          </div>
          <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
            {selectedUser && <InterventionHistory userId={selectedUser} />}
            <CreditDecisionLog auditLog={auditLog} />
            {selectedUser && <AnomalyHeatmap userId={selectedUser} />}
          </div>
        </TabsContent>

        {/* Simulation Tab */}
        <TabsContent value="simulation">
          {selectedUser ? (
            <LiveWhatIfPanel userId={selectedUser} />
          ) : (
            <div className="flex items-center justify-center h-64 text-muted-foreground text-sm">
              Select a user to run simulations.
            </div>
          )}
        </TabsContent>

        {/* Reasoning Trace */}
        <TabsContent value="reasoning">
          {selectedUser ? (
            <ReasoningTracePanel userId={selectedUser} />
          ) : (
            <div className="flex items-center justify-center h-64 text-muted-foreground text-sm">
              Select a user to view CoT traces.
            </div>
          )}
        </TabsContent>

        {/* Audit Export */}
        <TabsContent value="export">
          {selectedUser ? (
            <AuditReportExporter userId={selectedUser} auditLog={auditLog} />
          ) : (
            <div className="flex items-center justify-center h-64 text-muted-foreground text-sm">
              Select a user to generate reports.
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
