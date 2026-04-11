"use client";
import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/dib/authContext";
import { twinApi, simulationApi, reasoningApi, scoreApi } from "@/dib/api";
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
  CheckCircle2, AlertTriangle, Loader2, Brain, ChevronDown, ChevronRight,
  Zap, RefreshCw, Shield,
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

const SEVERITY_COLOR: Record<string, string> = {
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
  const [generating, setGenerating] = useState(false);
  const [status, setStatus] = useState<ScoreStatus>("pending");

  useEffect(() => {
    if (!user) return;
    if (user.role !== "individual") { router.push("/login"); return; }
    
    setLoading(true);
    setStatus("ingesting");

    let isMounted = true;

    const fetchTwinData = async () => {
      try {
        const [tw, hist, trig, cotData] = await Promise.all([
          twinApi.get(user.id).catch(() => null),
          twinApi.getHistory(user.id).catch(() => []),
          twinApi.getTriggers(user.id).catch(() => []),
          reasoningApi.getCot(user.id).catch(() => null),
        ]);
        if (!isMounted) return;
        setTwin(tw);
        setHistory(Array.isArray(hist) ? hist : (hist as any)?.history ?? []);
        setTriggers(Array.isArray(trig) ? trig : (trig as any)?.triggers ?? []);
        setCot(cotData);
        return tw;
      } catch (e) {
        console.error("Twin fetch error", e);
      }
    };

    const pollStatus = async () => {
        if (!isMounted) return;
        try {
            const res: any = await scoreApi.get(`task_${user.id}`);
            if (res.status === "complete") {
                await fetchTwinData();
                setStatus("complete");
                setLoading(false);
            } else {
                setStatus(res.status as ScoreStatus);
                setTimeout(pollStatus, 2000);
            }
        } catch (e) {
            // Fallback if score endpoint fails (maybe it's a mock user)
            const tw = await fetchTwinData();
            if (tw) {
                setStatus("complete");
                setLoading(false);
            } else {
                setTimeout(pollStatus, 3000);
            }
        }
    };

    pollStatus();

    return () => { isMounted = false; };
  }, [user, router]);

  const applyScenario = (s: string) => {
    setScenario(s);
    if (s === "job_loss") { setIncomeChg([-100]); setSpendChg([20]); }
    else if (s === "income_drop") { setIncomeChg([-20]); setSpendChg([0]); }
    else if (s === "spending_shock") { setIncomeChg([0]); setSpendChg([30]); }
    else if (s === "recovery") { setIncomeChg([15]); setSpendChg([-10]); }
    else { setIncomeChg([0]); setSpendChg([0]); }
  };

  const runSimulation = useCallback(async () => {
    if (!user) return;
    setSimRunning(true); setSimResult(null); setSimProgress(0);
    const interval = setInterval(() => {
      setSimProgress((p) => { if (p >= 90) { clearInterval(interval); return 90; } return p + Math.random() * 12; });
    }, 700);
    try {
      const res = await simulationApi.run({
        user_id: user.id,
        scenario_overrides: { income_change_pct: incomeChg[0], expense_change_pct: spendChg[0], scenario_name: scenario },
      });
      clearInterval(interval); setSimProgress(100); setSimResult(res);
    } catch { clearInterval(interval); setSimProgress(0); }
    finally { setTimeout(() => setSimRunning(false), 500); }
  }, [user, incomeChg, spendChg, scenario]);

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

  const fanChart: any[] = simResult?.fan_chart ?? simResult?.projections ?? [];
  const ews: any = simResult?.ews_snapshot ?? simResult?.risk_snapshot ?? {};
  const riskDelta = simResult?.risk_delta ?? simResult?.delta_risk_score;
  const newCreditLimit = simResult?.recommended_credit_limit ?? simResult?.new_credit_limit;

  const cotSteps: any[] = cot?.steps ?? cot?.chain_of_thought ?? [];

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

  return (
    <div className="p-6 w-full max-w-[1200px] mx-auto space-y-6">
      <PageHeader
        title="My Digital Twin"
        description="Your personal financial digital twin — see how your profile has evolved, simulate life events, and download your data."
        actions={
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" className="gap-2 h-8 text-xs font-medium" onClick={() => window.location.reload()}>
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
            { label: "Liquidity Health", value: `${Math.round((twin.liquidity_health ?? 0) * 100)}%`, bad: twin.liquidity_health < 0.4 },
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
               windows={twin.windows}
               scoreHistory={twin.score_history ?? []}
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

                  <Button className="w-full gap-2" onClick={runSimulation} disabled={simRunning}>
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
                          { label: "Risk Change", value: riskDelta !== undefined ? `${riskDelta > 0 ? "+" : ""}${(riskDelta * 100).toFixed(1)}%` : "—", bad: riskDelta > 0 },
                          { label: "Credit Limit", value: newCreditLimit ? `₹${(newCreditLimit / 100000).toFixed(1)}L` : "—", bad: false },
                          { label: "EWS Signal", value: ews.level ?? ews.status ?? "—", bad: ["RED", "ORANGE"].includes(ews.level ?? "") },
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
                          <AreaChart data={fanChart.slice(0, 12)} margin={{ top: 5, right: 5, left: -25, bottom: 0 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                            <XAxis dataKey="month" tick={{ fontSize: 9 }} />
                            <YAxis tick={{ fontSize: 9 }} />
                            <Tooltip contentStyle={{ fontSize: 10 }} />
                            <Area type="monotone" dataKey="p90" stroke="#22c55e" fill="#22c55e" fillOpacity={0.1} strokeWidth={1} />
                            <Area type="monotone" dataKey="p50" stroke="#c8ff00" fill="none" strokeWidth={2} />
                            <Area type="monotone" dataKey="p10" stroke="#ef4444" fill="#ef4444" fillOpacity={0.1} strokeWidth={1} />
                          </AreaChart>
                        </ResponsiveContainer>
                      )}

                      <Button variant="outline" className="w-full gap-2 text-xs h-8" onClick={() => exportAudit("json")} disabled={generating}>
                        {generating ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />}
                        Save Simulation to My Report
                      </Button>
                    </div>
                  )}
                </div>
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
