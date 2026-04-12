"use client";
import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/dib/authContext";
import { twinApi, simulationApi, reasoningApi, adminApi, interventionApi } from "@/dib/api";
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
  Zap, RefreshCw, BarChart3, FileText, MessageSquare, Send, Clock3,
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

  const [twin, setTwin] = useState<any>(null);
  const [history, setHistory] = useState<any[]>([]);
  const [triggers, setTriggers] = useState<any[]>([]);
  const [cot, setCot] = useState<any>(null);
  const [explorerData, setExplorerData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [explorerLoading, setExplorerLoading] = useState(false);
  const [tab, setTab] = useState("timeline");

  // Simulation
  const [incomeChg, setIncomeChg] = useState([0]);
  const [revenueChg, setRevenueChg] = useState([0]);
  const [scenario, setScenario] = useState("baseline");
  const [simResult, setSimResult] = useState<any>(null);
  const [simRunning, setSimRunning] = useState(false);
  const [simProgress, setSimProgress] = useState(0);
  const [autoSimEnabled, setAutoSimEnabled] = useState(true);
  const [autoSimEverySec, setAutoSimEverySec] = useState(120);
  const [lastSimAt, setLastSimAt] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);

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

  const loadTwinCore = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    try {
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

      setTwin(tw);
      setHistory(Array.isArray(hist) ? hist : (hist as any)?.history ?? []);
      const triggerPayload = Array.isArray(trig) ? { triggers: trig } : ((trig as any) ?? {});
      const nextTriggers = Array.isArray(triggerPayload?.triggers) ? triggerPayload.triggers : [];
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
    } finally {
      setLoading(false);
    }
  }, [user]);

  const loadExplorerData = useCallback(async () => {
    if (!user?.gstin) {
      setExplorerData(null);
      return;
    }
    setExplorerLoading(true);
    try {
      const explorer = await adminApi.getExplorerDetails(user.gstin);
      setExplorerData(explorer);
    } catch {
      setExplorerData(null);
    } finally {
      setExplorerLoading(false);
    }
  }, [user]);

  useEffect(() => {
    if (!user) return;
    if (user.role !== "msme") {
      router.push("/login");
      return;
    }
    loadTwinCore();
    loadExplorerData();
  }, [user, router, loadTwinCore, loadExplorerData]);

  const refreshAll = useCallback(() => {
    loadTwinCore();
    loadExplorerData();
  }, [loadTwinCore, loadExplorerData]);

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

  const twinScore = Number(twin?.cibil_like_score ?? 0);
  const twinRisk = Number(twin?.risk_score ?? 0);
  const twinRiskBand =
    twinRisk <= 0.30 ? "low_risk" : twinRisk <= 0.60 ? "medium_risk" : "high_risk";
  const derivedWc = twinScore
    ? Math.max(50_000, Math.min(50_00_000, Math.round(((twinScore - 300) / 600) * 50_00_000)))
    : null;

  const applyScenario = (s: string) => {
    setScenario(s);
    if (s === "revenue_crash") { setIncomeChg([-40]); setRevenueChg([-50]); }
    else if (s === "gst_shock") { setIncomeChg([-15]); setRevenueChg([0]); }
    else if (s === "expansion") { setIncomeChg([20]); setRevenueChg([30]); }
    else if (s === "supply_squeeze") { setIncomeChg([0]); setRevenueChg([-20]); }
    else { setIncomeChg([0]); setRevenueChg([0]); }
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
      const jobLoss = scenario === "revenue_crash";
      const medicalEmergency = scenario === "supply_squeeze";
      const res = await simulationApi.run({
        user_id: user.id,
        num_simulations: 1000,
        run_counterfactual: true,
        scenario_overrides: {
          income_change_pct: incomeChg[0],
          revenue_change_pct: revenueChg[0],
          expense_change_pct: revenueChg[0] > 0 ? 0 : Math.abs(revenueChg[0]),
          scenario_name: scenario,
          job_loss: jobLoss,
          medical_emergency: medicalEmergency,
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
        detail: "Could not compute the latest business projection.",
        severity: "high",
      });
    } finally {
      setTimeout(() => setSimRunning(false), silent ? 0 : 500);
    }
  }, [user, incomeChg, revenueChg, scenario, pushFeed]);

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
        loadTwinCore();
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
  }, [user, negSession, negInput, loadTwinCore, pushFeed]);

  useEffect(() => {
    if (!user || !autoSimEnabled) return;
    const timer = setInterval(() => {
      if (!simRunning) {
        runSimulation({ silent: true, source: "auto" });
      }
    }, autoSimEverySec * 1000);
    return () => clearInterval(timer);
  }, [user, autoSimEnabled, autoSimEverySec, simRunning, runSimulation]);

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
        current_credit_score: twinScore || null,
        risk_band: twinRiskBand,
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

  const exportPdf = () => {
    const escapeHtml = (value: unknown) =>
      String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/\"/g, "&quot;")
        .replace(/'/g, "&#39;");

    const historyRows = chartData
      .slice()
      .reverse()
      .slice(0, 12)
      .map(
        (v) => `
          <tr>
            <td>${escapeHtml(v.ver)}</td>
            <td>${escapeHtml(v.persona)}</td>
            <td>${escapeHtml(`${v.risk}%`)}</td>
            <td>${escapeHtml(String(v.cibil ?? "-"))}</td>
            <td>${escapeHtml(fmtTs(v.ts))}</td>
          </tr>
        `,
      )
      .join("");

    const triggerRows = (triggers || [])
      .slice(0, 20)
      .map(
        (t: any) => `
          <tr>
            <td>${escapeHtml(t.trigger_id ?? t.name ?? "Alert")}</td>
            <td>${escapeHtml(t.severity ?? "low")}</td>
            <td>${escapeHtml(t.message ?? t.description ?? "")}</td>
          </tr>
        `,
      )
      .join("");

    const cotRows = (cotSteps || [])
      .slice(0, 20)
      .map(
        (s: any, i: number) => `
          <tr>
            <td>T${i + 1}</td>
            <td>${escapeHtml(s.title ?? s.step ?? "Step")}</td>
            <td>${escapeHtml(
              s.content ?? s.reasoning ?? s.thought ?? JSON.stringify(s),
            )}</td>
          </tr>
        `,
      )
      .join("");

    const simulationSummary = simResult
      ? `
        <ul>
          <li><strong>Scenario:</strong> ${escapeHtml(scenario.replace(/_/g, " "))}</li>
          <li><strong>Risk Delta:</strong> ${escapeHtml(
              riskDelta !== undefined
                ? `${riskDelta > 0 ? "+" : ""}${(riskDelta * 100).toFixed(1)}%`
                : "-",
            )}</li>
          <li><strong>New Credit Limit:</strong> ${escapeHtml(newLimit ? fmtINR(newLimit) : "-")}</li>
          <li><strong>EWS:</strong> ${escapeHtml(ews.level ?? ews.status ?? "-")}</li>
        </ul>
      `
      : "<p>No simulation run in this session.</p>";

    const buildLineChartSvg = (
      points: Array<{ xLabel: string; value: number }>,
      stroke: string,
      yMax = 100,
    ) => {
      if (!points.length) return "";
      const width = 880;
      const height = 250;
      const padL = 42;
      const padR = 16;
      const padT = 14;
      const padB = 28;
      const innerW = width - padL - padR;
      const innerH = height - padT - padB;
      const x = (i: number) =>
        points.length === 1 ? padL + innerW / 2 : padL + (i / (points.length - 1)) * innerW;
      const y = (v: number) => padT + (1 - Math.max(0, Math.min(v, yMax)) / yMax) * innerH;

      const polyline = points.map((p, i) => `${x(i)},${y(p.value)}`).join(" ");
      const dots = points
        .map((p, i) => `<circle cx="${x(i)}" cy="${y(p.value)}" r="2.5" fill="${stroke}" />`)
        .join("");
      const xLabelStep = Math.max(1, Math.floor(points.length / 5));
      const xLabels = points
        .map((p, i) => {
          if (!(i === 0 || i === points.length - 1 || i % xLabelStep === 0)) return "";
          return `<text x="${x(i)}" y="${height - 8}" text-anchor="middle" font-size="10" fill="#6b7280">${escapeHtml(p.xLabel)}</text>`;
        })
        .join("");
      const yTicks = [0, 25, 50, 75, 100]
        .map(
          (tick) => `
            <line x1="${padL}" y1="${y(tick)}" x2="${width - padR}" y2="${y(tick)}" stroke="#e5e7eb" stroke-width="1" />
            <text x="${padL - 8}" y="${y(tick) + 3}" text-anchor="end" font-size="10" fill="#6b7280">${tick}</text>
          `,
        )
        .join("");

      return `
        <svg viewBox="0 0 ${width} ${height}" class="chart-svg" role="img" aria-label="Line chart">
          ${yTicks}
          <line x1="${padL}" y1="${height - padB}" x2="${width - padR}" y2="${height - padB}" stroke="#9ca3af" stroke-width="1" />
          <line x1="${padL}" y1="${padT}" x2="${padL}" y2="${height - padB}" stroke="#9ca3af" stroke-width="1" />
          <polyline fill="none" stroke="${stroke}" stroke-width="2.5" points="${polyline}" />
          ${dots}
          ${xLabels}
        </svg>
      `;
    };

    const timelineChartSvg = buildLineChartSvg(
      chartData.slice(-12).map((p: any, idx: number) => ({ xLabel: p.ver || `v${idx + 1}`, value: Number(p.risk ?? 0) })),
      "#ef4444",
    );

    const simulationChartSvg = fanChart.length
      ? buildLineChartSvg(
          fanChart.slice(0, 12).map((p: any, idx: number) => ({
            xLabel: String(p.month ?? idx + 1),
            value: Number(p.p50 ?? p.value ?? 0),
          })),
          "#0ea5e9",
        )
      : "";

    const printableHtml = `
      <!doctype html>
      <html>
        <head>
          <meta charset="utf-8" />
          <meta name="viewport" content="width=device-width, initial-scale=1" />
          <title>Business Twin Report</title>
          <style>
            * { box-sizing: border-box; }
            html, body {
              margin: 0;
              padding: 0;
              background: #ffffff !important;
              color: #111111 !important;
              font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
              -webkit-print-color-adjust: exact;
              print-color-adjust: exact;
            }
            .page { padding: 20px; }
            h1 { margin: 0 0 6px; font-size: 22px; color: #111111 !important; }
            h2 { margin: 22px 0 10px; font-size: 15px; border-bottom: 1px solid #e5e7eb; padding-bottom: 6px; color: #111111 !important; }
            p, li { font-size: 12px; line-height: 1.5; }
            .meta { color: #444; margin-bottom: 12px; }
            .topline {
              display: flex;
              justify-content: space-between;
              gap: 12px;
              align-items: center;
              border-bottom: 2px solid #111111;
              padding-bottom: 8px;
              margin-bottom: 14px;
            }
            .brand {
              font-size: 11px;
              letter-spacing: 0.08em;
              text-transform: uppercase;
              color: #374151;
              font-weight: 700;
            }
            .grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
            .card { border: 1px solid #d1d5db; border-radius: 8px; padding: 10px; }
            .label { font-size: 11px; color: #4b5563; }
            .value { font-size: 16px; font-weight: 700; margin-top: 4px; color: #111111 !important; }
            table { width: 100%; border-collapse: collapse; }
            th, td { border: 1px solid #d1d5db; padding: 6px 8px; text-align: left; font-size: 11px; vertical-align: top; }
            th { background: #f3f4f6; font-weight: 700; }
            .empty { color: #6b7280; font-style: italic; }
            .chart-wrap {
              border: 1px solid #d1d5db;
              border-radius: 8px;
              padding: 8px;
              margin: 8px 0 10px;
              background: #ffffff;
            }
            .chart-title {
              font-size: 11px;
              font-weight: 700;
              color: #111111;
              margin-bottom: 6px;
            }
            .chart-svg {
              width: 100%;
              height: auto;
              display: block;
            }
            .footer {
              margin-top: 16px;
              font-size: 10px;
              color: #6b7280;
              border-top: 1px solid #e5e7eb;
              padding-top: 8px;
            }
            tr { page-break-inside: avoid; }
            section { page-break-inside: avoid; }
            @page { size: A4; margin: 12mm; }
          </style>
        </head>
        <body>
          <main class="page">
            <div class="topline">
              <h1>Business Digital Twin Report</h1>
              <span class="brand">AIRAVAT Intelligence</span>
            </div>
            <p class="meta">Generated: ${escapeHtml(new Date().toLocaleString("en-IN"))}</p>
            <p class="meta">Business: ${escapeHtml(user?.name)} | GSTIN: ${escapeHtml(user?.gstin)} | User ID: ${escapeHtml(user?.id)}</p>

            <section>
              <h2>Snapshot</h2>
              <div class="grid">
                <div class="card"><div class="label">Credit Score</div><div class="value">${escapeHtml(String(score?.credit_score ?? "-"))}</div></div>
                <div class="card"><div class="label">Risk Band</div><div class="value">${escapeHtml(String(score?.risk_band ?? "-").replace(/_/g, " "))}</div></div>
                <div class="card"><div class="label">Twin Risk Score</div><div class="value">${escapeHtml(twin ? `${Math.round((twin.risk_score ?? 0) * 100)}%` : "-")}</div></div>
                <div class="card"><div class="label">Recommended WC</div><div class="value">${escapeHtml(score?.recommended_wc_amount ? fmtINR(score.recommended_wc_amount) : "-")}</div></div>
              </div>
            </section>

            <section>
              <h2>Twin Timeline (Latest 12)</h2>
              ${timelineChartSvg ? `<div class="chart-wrap"><p class="chart-title">Twin Risk Trend</p>${timelineChartSvg}</div>` : ""}
              ${historyRows ? `<table><thead><tr><th>Version</th><th>Persona</th><th>Risk</th><th>CIBIL-Like</th><th>Timestamp</th></tr></thead><tbody>${historyRows}</tbody></table>` : `<p class="empty">No twin history available.</p>`}
            </section>

            <section>
              <h2>Risk Alerts</h2>
              ${triggerRows ? `<table><thead><tr><th>Alert</th><th>Severity</th><th>Message</th></tr></thead><tbody>${triggerRows}</tbody></table>` : `<p class="empty">No risk alerts available.</p>`}
            </section>

            <section>
              <h2>AI Reasoning</h2>
              ${cotRows ? `<table><thead><tr><th>Step</th><th>Title</th><th>Reasoning</th></tr></thead><tbody>${cotRows}</tbody></table>` : `<p class="empty">No reasoning trace available.</p>`}
            </section>

            <section>
              <h2>Scenario Simulation</h2>
              ${simulationChartSvg ? `<div class="chart-wrap"><p class="chart-title">Projected Scenario Curve (P50)</p>${simulationChartSvg}</div>` : ""}
              ${simulationSummary}
            </section>

            <p class="footer">Generated by AIRAVAT Business Twin Module. This report is intended for credit monitoring and internal risk analysis.</p>
          </main>
        </body>
      </html>
    `;

    const iframe = document.createElement("iframe");
    iframe.style.position = "fixed";
    iframe.style.right = "0";
    iframe.style.bottom = "0";
    iframe.style.width = "0";
    iframe.style.height = "0";
    iframe.style.border = "0";
    document.body.appendChild(iframe);

    const frameDoc = iframe.contentDocument || iframe.contentWindow?.document;
    if (!frameDoc || !iframe.contentWindow) {
      document.body.removeChild(iframe);
      window.print();
      return;
    }

    frameDoc.open();
    frameDoc.write(printableHtml);
    frameDoc.close();

    const cleanup = () => {
      if (iframe.parentNode) iframe.parentNode.removeChild(iframe);
    };

    iframe.contentWindow.onafterprint = cleanup;
    setTimeout(() => {
      iframe.contentWindow?.focus();
      iframe.contentWindow?.print();
      setTimeout(cleanup, 1200);
    }, 200);
  };

  if (!user || user.role !== "msme") return null;

  const chartData = history.map((v: any) => ({
    ver: `v${v.version ?? "?"}`,
    risk: Math.round((v.risk_score ?? 0) * 100),
    cibil: v.cibil_like_score ?? 0,
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
  const riskDelta = simResult?.risk_delta ?? simResult?.delta_risk_score ?? day90?.default_probability;
  const activeOffer = useMemo(() => offer ?? simResult?.proactive_offer ?? null, [offer, simResult]);
  const newLimit = activeOffer?.approved_amount ?? simResult?.recommended_credit_limit ?? simResult?.new_credit_limit;
  const cotSteps: any[] = normalizeCotSteps(cot);

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
            <Button variant="outline" size="sm" className="gap-2 h-8 text-xs" onClick={refreshAll}>
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
      {twin && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            { label: "Credit Score", value: twinScore || "—", sub: twinRiskBand },
            { label: "Twin Risk Score", value: twin ? `${Math.round((twin.risk_score ?? 0) * 100)}%` : "—", bad: (twin?.risk_score ?? 0) > 0.5 },
            { label: "Recommended WC", value: derivedWc ? fmtINR(derivedWc) : "—" },
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
          {loading || explorerLoading ? (
            <Card className="border-border shadow-sm"><CardContent className="flex items-center justify-center h-48"><Loader2 className="w-8 h-8 animate-spin text-muted-foreground" /></CardContent></Card>
          ) : explorerData ? (
            <TimeSeriesPanel
              upiTimeline={explorerData.upi_timeline ?? []}
              ewbTimeline={explorerData.ewb_timeline ?? []}
              twinTimeline={explorerData.twin_timeline ?? []}
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

                  <Button className="w-full gap-2" onClick={() => runSimulation({ source: "manual" })} disabled={simRunning}>
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
                          { label: "Default P (90d)", value: day90?.default_probability !== undefined ? `${((day90.default_probability ?? 0) * 100).toFixed(1)}%` : "—", bad: (day90?.default_probability ?? 0) > 0.3 },
                          { label: "Pre-Qual Offer", value: newLimit ? fmtINR(newLimit) : "—", bad: false },
                          { label: "EWS Signal", value: ews.severity ?? ews.level ?? ews.status ?? "—", bad: ["RED", "ORANGE"].includes((ews.severity ?? ews.level ?? "").toUpperCase()) },
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

                      <div className="grid grid-cols-3 gap-2">
                        <div className="bg-muted/40 rounded-lg p-2">
                          <p className="text-[10px] text-muted-foreground">VaR 95</p>
                          <p className="text-xs font-mono text-red-300">{simResult?.tail_risk?.var_95 ? fmtINR(Math.abs(simResult.tail_risk.var_95)) : "—"}</p>
                        </div>
                        <div className="bg-muted/40 rounded-lg p-2">
                          <p className="text-[10px] text-muted-foreground">CVaR 95</p>
                          <p className="text-xs font-mono text-red-300">{simResult?.tail_risk?.cvar_95 ? fmtINR(Math.abs(simResult.tail_risk.cvar_95)) : "—"}</p>
                        </div>
                        <div className="bg-muted/40 rounded-lg p-2">
                          <p className="text-[10px] text-muted-foreground">Crash Date</p>
                          <p className="text-xs font-mono text-amber-300">{simResult?.liquidity_crash_date_estimate ?? "None"}</p>
                        </div>
                      </div>

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

                    {negSession?.last_impact && (
                      <div className="grid grid-cols-2 gap-2 text-xs">
                        <div className="bg-muted/30 rounded-lg p-2 border border-border/50">
                          <p className="text-[10px] text-muted-foreground mb-1">Baseline</p>
                          <p>Risk: <span className="font-semibold">{((Number(negSession.last_impact?.baseline?.risk_score ?? 0)) * 100).toFixed(1)}%</span></p>
                          <p>Buffer: <span className="font-semibold">{Number(negSession.last_impact?.baseline?.cash_buffer_days ?? 0).toFixed(1)}d</span></p>
                          <p>EMI Burden: <span className="font-semibold">{((Number(negSession.last_impact?.baseline?.emi_burden_ratio ?? 0)) * 100).toFixed(1)}%</span></p>
                        </div>
                        <div className="bg-emerald-500/5 rounded-lg p-2 border border-emerald-500/20">
                          <p className="text-[10px] text-muted-foreground mb-1">Projected</p>
                          <p>Risk: <span className="font-semibold">{((Number(negSession.last_impact?.projection?.risk_score ?? 0)) * 100).toFixed(1)}%</span></p>
                          <p>Buffer: <span className="font-semibold">{Number(negSession.last_impact?.projection?.cash_buffer_days ?? 0).toFixed(1)}d</span></p>
                          <p>EMI Burden: <span className="font-semibold">{((Number(negSession.last_impact?.projection?.emi_burden_ratio ?? 0)) * 100).toFixed(1)}%</span></p>
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
