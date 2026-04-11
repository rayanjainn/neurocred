"use client";
import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/dib/authContext";
import { twinApi, simulationApi, reasoningApi, adminApi } from "@/dib/api";
import { useScore } from "@/hooks/useScore";
import { PageHeader } from "@/components/shared";
import { TimeSeriesPanel } from "@/components/TimeSeriesPanel";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Slider } from "@/components/ui/slider";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  GitBranch, Activity, Download, Play, TrendingUp,
  CheckCircle2, AlertTriangle, Loader2, Brain, ChevronDown, ChevronRight,
  Zap, RefreshCw, BarChart3, FileText,
} from "lucide-react";
import {
  LineChart, Line, AreaChart, Area,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import { cn } from "@/dib/utils";

function fmtTs(ts: string) {
  try { return new Date(ts).toLocaleString("en-IN", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }); }
  catch { return ts; }
}
function fmtINR(n: number) {
  if (n >= 10000000) return `₹${(n / 10000000).toFixed(1)}Cr`;
  if (n >= 100000) return `₹${(n / 100000).toFixed(1)}L`;
  return `₹${n.toLocaleString("en-IN")}`;
}

function ReasoningTab({ cotSteps, loading }: { cotSteps: any[]; loading: boolean }) {
  const [expanded, setExpanded] = useState<number[]>([]);
  const toggle = (i: number) =>
    setExpanded((prev) => prev.includes(i) ? prev.filter((x) => x !== i) : [...prev, i]);

  return (
    <Card className="border-border shadow-sm">
      <CardHeader className="py-3 px-4 border-b">
        <CardTitle className="text-sm font-semibold flex items-center gap-2">
          <Brain className="w-4 h-4 text-primary" /> AI Reasoning — Why Your Score Changed
        </CardTitle>
      </CardHeader>
      <CardContent className="p-4">
        {loading ? (
          <div className="flex items-center justify-center h-32"><Loader2 className="w-6 h-6 animate-spin text-muted-foreground" /></div>
        ) : cotSteps.length === 0 ? (
          <p className="text-xs text-muted-foreground text-center py-8">No reasoning trace yet. Submit a score request first.</p>
        ) : (
          <div className="space-y-2 max-h-96 overflow-y-auto pr-1">
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

export default function MsmeTwinPage() {
  const { user } = useAuth();
  const router = useRouter();
  const { score } = useScore(user?.gstin);

  const [twin, setTwin] = useState<any>(null);
  const [history, setHistory] = useState<any[]>([]);
  const [triggers, setTriggers] = useState<any[]>([]);
  const [cot, setCot] = useState<any>(null);
  const [explorerData, setExplorerData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState("timeline");

  // Simulation
  const [incomeChg, setIncomeChg] = useState([0]);
  const [revenueChg, setRevenueChg] = useState([0]);
  const [scenario, setScenario] = useState("baseline");
  const [simResult, setSimResult] = useState<any>(null);
  const [simRunning, setSimRunning] = useState(false);
  const [simProgress, setSimProgress] = useState(0);
  const [generating, setGenerating] = useState(false);

  useEffect(() => {
    if (!user) return;
    if (user.role !== "msme") { router.push("/login"); return; }
    setLoading(true);
    Promise.all([
      twinApi.get(user.id).catch(() => null),
      twinApi.getHistory(user.id).catch(() => []),
      twinApi.getTriggers(user.id).catch(() => []),
      reasoningApi.getCot(user.id).catch(() => null),
      user.gstin ? adminApi.getExplorerDetails(user.gstin).catch(() => null) : Promise.resolve(null),
    ]).then(([tw, hist, trig, cotData, explorer]) => {
      setTwin(tw);
      setHistory(Array.isArray(hist) ? hist : (hist as any)?.history ?? []);
      setTriggers(Array.isArray(trig) ? trig : (trig as any)?.triggers ?? []);
      setCot(cotData);
      setExplorerData(explorer);
    }).finally(() => setLoading(false));
  }, [user, router]);

  const applyScenario = (s: string) => {
    setScenario(s);
    if (s === "revenue_crash") { setIncomeChg([-40]); setRevenueChg([-50]); }
    else if (s === "gst_shock") { setIncomeChg([-15]); setRevenueChg([0]); }
    else if (s === "expansion") { setIncomeChg([20]); setRevenueChg([30]); }
    else if (s === "supply_squeeze") { setIncomeChg([0]); setRevenueChg([-20]); }
    else { setIncomeChg([0]); setRevenueChg([0]); }
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
        gstin: user.gstin,
        scenario_overrides: { income_change_pct: incomeChg[0], revenue_change_pct: revenueChg[0], scenario_name: scenario },
      });
      clearInterval(interval); setSimProgress(100); setSimResult(res);
    } catch { clearInterval(interval); setSimProgress(0); }
    finally { setTimeout(() => setSimRunning(false), 500); }
  }, [user, incomeChg, revenueChg, scenario]);

  const exportJson = async () => {
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
        user_id: user.id, gstin: user.gstin, business_name: user.name,
        regulatory_note: "Business data export under RBI Digital Lending Guidelines 2023",
        current_credit_score: score?.credit_score, risk_band: score?.risk_band,
        twin_current_state: currentTwin, twin_evolution_history: twinHist,
        intervention_triggers: twinTriggers, llm_chain_of_thought: cotTrace,
        ews_snapshot: ews, transaction_timeseries: explorerData,
        simulation_artifacts: simResult ?? { note: "No simulation run this session." },
      };
      const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a"); a.href = url;
      a.download = `msme_twin_report_${user.gstin}_${Date.now()}.json`; a.click();
      URL.revokeObjectURL(url);
    } finally { setGenerating(false); }
  };

  const exportPdf = () => window.print();

  if (!user || user.role !== "msme") return null;

  const chartData = history.map((v: any) => ({
    ver: `v${v.version ?? "?"}`,
    risk: Math.round((v.risk_score ?? 0) * 100),
    cibil: v.cibil_like_score ?? 0,
    ts: v.last_updated ?? v.created_at ?? "",
    persona: v.persona ?? "unknown",
  }));

  const fanChart: any[] = simResult?.fan_chart ?? simResult?.projections ?? [];
  const ews: any = simResult?.ews_snapshot ?? simResult?.risk_snapshot ?? {};
  const riskDelta = simResult?.risk_delta ?? simResult?.delta_risk_score;
  const newLimit = simResult?.recommended_credit_limit ?? simResult?.new_credit_limit;
  const cotSteps: any[] = cot?.steps ?? cot?.chain_of_thought ?? [];

  const SEVERITY_COLOR: Record<string, string> = {
    critical: "text-red-400 bg-red-500/10 border-red-500/20",
    high: "text-orange-400 bg-orange-500/10 border-orange-500/20",
    medium: "text-amber-400 bg-amber-500/10 border-amber-500/20",
    low: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
  };

  return (
    <div className="p-6 w-full max-w-[1200px] mx-auto space-y-6">
      <PageHeader
        title="My Business Digital Twin"
        description="Your GSTIN financial twin — see evolution, simulate business scenarios, and download your credit profile."
        actions={
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" className="gap-2 h-8 text-xs" onClick={() => window.location.reload()}>
              <RefreshCw className="w-3.5 h-3.5" /> Refresh
            </Button>
            <Button variant="outline" size="sm" className="gap-2 h-8 text-xs" onClick={exportJson} disabled={generating}>
              {generating ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />} JSON
            </Button>
            <Button size="sm" className="gap-2 h-8 text-xs" onClick={exportPdf}>
              <FileText className="w-3.5 h-3.5" /> PDF
            </Button>
          </div>
        }
      />

      {/* Snapshot banner */}
      {(twin ?? score) && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            { label: "Credit Score", value: score?.credit_score ?? "—", sub: score?.risk_band },
            { label: "Twin Risk Score", value: twin ? `${Math.round((twin.risk_score ?? 0) * 100)}%` : "—", bad: (twin?.risk_score ?? 0) > 0.5 },
            { label: "Recommended WC", value: score?.recommended_wc_amount ? fmtINR(score.recommended_wc_amount) : "—" },
            { label: "Persona", value: twin?.persona ?? "—" },
          ].map((m) => (
            <Card key={m.label} className="border-border shadow-sm">
              <CardContent className="p-4">
                <p className="text-xs text-muted-foreground">{m.label}</p>
                <p className={cn("text-lg font-bold mt-1 capitalize", (m as any).bad ? "text-amber-400" : "text-foreground")}>{String(m.value)}</p>
                {(m as any).sub && <p className="text-[10px] text-muted-foreground capitalize">{(m as any).sub?.replace(/_/g, " ")}</p>}
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="mb-4">
          <TabsTrigger value="timeline" className="text-xs gap-1.5"><GitBranch className="w-3.5 h-3.5" />Twin Timeline</TabsTrigger>
          <TabsTrigger value="transactions" className="text-xs gap-1.5"><Activity className="w-3.5 h-3.5" />Transactions</TabsTrigger>
          <TabsTrigger value="simulation" className="text-xs gap-1.5"><BarChart3 className="w-3.5 h-3.5" />Scenario Sim</TabsTrigger>
          <TabsTrigger value="reasoning" className="text-xs gap-1.5"><Brain className="w-3.5 h-3.5" />AI Reasoning</TabsTrigger>
          <TabsTrigger value="export" className="text-xs gap-1.5"><FileText className="w-3.5 h-3.5" />Audit Report</TabsTrigger>
        </TabsList>

        {/* Twin Timeline */}
        <TabsContent value="timeline" className="space-y-4">
          <Card className="border-border shadow-sm">
            <CardHeader className="py-3 px-4 border-b">
              <CardTitle className="text-sm font-semibold flex items-center gap-2">
                <GitBranch className="w-4 h-4 text-primary" /> Business Twin Evolution
              </CardTitle>
            </CardHeader>
            <CardContent className="p-4">
              {loading ? (
                <div className="flex items-center justify-center h-48"><Loader2 className="w-8 h-8 animate-spin text-muted-foreground" /></div>
              ) : chartData.length === 0 ? (
                <p className="text-xs text-muted-foreground text-center py-12">No twin history yet. Data appears after your first score run.</p>
              ) : (
                <>
                  <ResponsiveContainer width="100%" height={200}>
                    <LineChart data={chartData} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                      <XAxis dataKey="ver" tick={{ fontSize: 10 }} />
                      <YAxis tick={{ fontSize: 10 }} domain={[0, 100]} />
                      <Tooltip contentStyle={{ fontSize: 11 }} formatter={(v: any, n: string) => [`${v}${n === "cibil" ? "" : "%"}`, n]} />
                      <Line type="monotone" dataKey="risk" stroke="#ef4444" strokeWidth={2} dot={{ r: 3 }} name="Risk %" />
                      <Line type="monotone" dataKey="cibil" stroke="#c8ff00" strokeWidth={2} dot={{ r: 3 }} name="CIBIL-Like" />
                    </LineChart>
                  </ResponsiveContainer>
                  <div className="mt-3 space-y-1.5 max-h-40 overflow-y-auto pr-1">
                    {[...chartData].reverse().map((v, i) => (
                      <div key={i} className="flex items-center justify-between text-xs bg-muted/40 rounded px-3 py-1.5">
                        <span className="font-mono text-muted-foreground">{v.ver}</span>
                        <span className="capitalize text-foreground/80">{v.persona}</span>
                        <span className={v.risk > 50 ? "text-red-400" : "text-emerald-400"}>Risk {v.risk}%</span>
                        <span className="text-muted-foreground">{fmtTs(v.ts)}</span>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </CardContent>
          </Card>

          {triggers.length > 0 && (
            <Card className="border-border shadow-sm">
              <CardHeader className="py-3 px-4 border-b">
                <CardTitle className="text-sm font-semibold flex items-center gap-2">
                  <Zap className="w-4 h-4 text-primary" /> Business Risk Alerts
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

        {/* Transactions / Time Series */}
        <TabsContent value="transactions">
          {loading ? (
            <Card className="border-border shadow-sm"><CardContent className="flex items-center justify-center h-48"><Loader2 className="w-8 h-8 animate-spin text-muted-foreground" /></CardContent></Card>
          ) : explorerData ? (
            <TimeSeriesPanel
              upiTimeline={explorerData.upi_timeline ?? []}
              ewbTimeline={explorerData.ewb_timeline ?? []}
              windows={explorerData.windows}
              scoreHistory={explorerData.score_history ?? []}
              title="Business Transaction Time Series"
              entityType="msme"
            />
          ) : (
            <Card className="border-border shadow-sm">
              <CardContent className="flex items-center justify-center h-48">
                <p className="text-xs text-muted-foreground">No transaction data available. Ensure your GSTIN is linked.</p>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Simulation */}
        <TabsContent value="simulation">
          <Card className="border-border shadow-sm">
            <CardHeader className="py-3 px-4 border-b">
              <CardTitle className="text-sm font-semibold flex items-center gap-2">
                <Activity className="w-4 h-4 text-primary" /> Business Scenario Simulator
                <Badge variant="outline" className="text-[10px] ml-auto">10s SLA</Badge>
              </CardTitle>
            </CardHeader>
            <CardContent className="p-5">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-5">
                  <div>
                    <p className="text-xs font-semibold text-muted-foreground mb-2">Business Events</p>
                    <div className="flex flex-wrap gap-2">
                      {[
                        { id: "baseline", label: "Baseline" },
                        { id: "revenue_crash", label: "Revenue -40%" },
                        { id: "gst_shock", label: "GST Shock" },
                        { id: "expansion", label: "Business Expansion" },
                        { id: "supply_squeeze", label: "Supply Squeeze" },
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
                        <label className="text-xs font-medium">Income / Cash Flow Change</label>
                        <span className={cn("text-xs font-bold font-mono", incomeChg[0] < 0 ? "text-red-400" : "text-emerald-400")}>
                          {incomeChg[0] > 0 ? "+" : ""}{incomeChg[0]}%
                        </span>
                      </div>
                      <Slider value={incomeChg} onValueChange={setIncomeChg} min={-100} max={50} step={5} />
                    </div>
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <label className="text-xs font-medium">Revenue / GST Turnover Change</label>
                        <span className={cn("text-xs font-bold font-mono", revenueChg[0] < 0 ? "text-red-400" : "text-emerald-400")}>
                          {revenueChg[0] > 0 ? "+" : ""}{revenueChg[0]}%
                        </span>
                      </div>
                      <Slider value={revenueChg} onValueChange={setRevenueChg} min={-100} max={100} step={5} />
                    </div>
                  </div>

                  <Button className="w-full gap-2" onClick={runSimulation} disabled={simRunning}>
                    {simRunning ? <><Loader2 className="w-4 h-4 animate-spin" /> Simulating...</> : <><Play className="w-4 h-4" /> Run Scenario</>}
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
                      <BarChart3 className="w-10 h-10 opacity-20" />
                      <p className="text-xs text-center">Select a business scenario and run simulation to see projected credit impact</p>
                    </div>
                  )}

                  {simResult && (
                    <div className="space-y-4 animate-in fade-in slide-in-from-bottom-2 duration-400">
                      <div className="grid grid-cols-2 gap-3">
                        {[
                          { label: "Risk Change", value: riskDelta !== undefined ? `${riskDelta > 0 ? "+" : ""}${(riskDelta * 100).toFixed(1)}%` : "—", bad: riskDelta > 0 },
                          { label: "New Credit Limit", value: newLimit ? fmtINR(newLimit) : "—", bad: false },
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
        </TabsContent>

        {/* Reasoning */}
        <TabsContent value="reasoning">
          <ReasoningTab cotSteps={cotSteps} loading={loading} />
        </TabsContent>

        {/* Export */}
        <TabsContent value="export">
          <Card className="border-border shadow-sm">
            <CardHeader className="py-3 px-4 border-b">
              <CardTitle className="text-sm font-semibold flex items-center gap-2">
                <Download className="w-4 h-4 text-primary" /> Business Audit Report
                <Badge className="text-[10px] bg-primary/10 text-primary border-primary/20 ml-auto">One-Click</Badge>
              </CardTitle>
            </CardHeader>
            <CardContent className="p-5">
              <p className="text-xs text-muted-foreground mb-4 leading-relaxed">
                Export your complete business credit intelligence record — twin state, AI reasoning, risk alerts, transaction timeseries, and any simulation artifacts from this session.
              </p>
              <div className="flex gap-3">
                <Button className="gap-2" onClick={exportJson} disabled={generating}>
                  {generating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
                  {generating ? "Preparing..." : "Download JSON"}
                </Button>
                <Button variant="outline" className="gap-2" onClick={exportPdf}>
                  <FileText className="w-4 h-4" /> Download PDF
                </Button>
              </div>
              <div className="mt-4 text-[10px] text-muted-foreground border border-border/50 rounded-lg p-3 bg-muted/20 space-y-0.5">
                <p className="font-semibold text-foreground/70">Includes:</p>
                {[
                  "Business Digital Twin current state and history",
                  "AI Chain-of-Thought credit score reasoning",
                  "Business risk intervention alerts",
                  "Current credit score and recommended limits",
                  "Full 12-month transaction time series",
                  `Simulation artifacts ${simResult ? "(from this session)" : "(run a scenario first)"}`,
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
