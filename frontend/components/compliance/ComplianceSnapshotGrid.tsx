"use client";

import { useEffect, useMemo, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  LineChart,
  PolarAngleAxis,
  PolarGrid,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { adminApi, reasoningApi, simulationApi, twinApi, vigilanceApi } from "@/dib/api";

function fmtTs(ts: string) {
  try {
    return new Date(ts).toLocaleString("en-IN", {
      day: "2-digit",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return ts;
  }
}

function TwinTimelineCard({ userId }: { userId: string }) {
  const [history, setHistory] = useState<any[]>([]);

  useEffect(() => {
    twinApi
      .getHistory(userId)
      .then((res: any) => setHistory(Array.isArray(res) ? res : (res?.history ?? [])))
      .catch(() => setHistory([]));
  }, [userId]);

  const chartData = history
    .map((v: any) => ({
      ver: `v${v.version ?? "?"}`,
      risk: Math.round(Number(v.risk_score ?? 0) * 100),
      cibil: Number(v.cibil_like_score ?? v.cibil_score ?? 0),
      ts: String(v.last_updated ?? v.created_at ?? ""),
      persona: String(v.persona ?? "unknown"),
    }))
    .reverse();

  return (
    <Card className="border-border shadow-sm h-full">
      <CardHeader className="py-3 px-4 border-b">
        <CardTitle className="text-sm font-semibold">Digital Twin Evolution Timeline</CardTitle>
      </CardHeader>
      <CardContent className="p-4">
        {chartData.length === 0 ? (
          <p className="text-xs text-muted-foreground text-center py-8">No timeline data yet.</p>
        ) : (
          <>
            <ResponsiveContainer width="100%" height={180}>
              <LineChart data={chartData} margin={{ top: 5, right: 8, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="ver" tick={{ fontSize: 10 }} />
                <YAxis tick={{ fontSize: 10 }} domain={[0, 100]} />
                <Tooltip contentStyle={{ fontSize: 11 }} />
                <Line type="monotone" dataKey="risk" stroke="#ef4444" strokeWidth={2} dot={{ r: 2 }} name="Risk %" />
                <Line type="monotone" dataKey="cibil" stroke="#c8ff00" strokeWidth={2} dot={{ r: 2 }} name="CIBIL-Like" />
              </LineChart>
            </ResponsiveContainer>
            <div className="mt-3 space-y-1 max-h-32 overflow-y-auto pr-1">
              {chartData.slice(-8).reverse().map((v: any, i: number) => (
                <div key={`${v.ver}:${i}`} className="flex items-center justify-between text-xs bg-muted/30 rounded px-2 py-1">
                  <span className="font-mono text-muted-foreground">{v.ver}</span>
                  <span className="capitalize text-foreground/80 truncate max-w-[20%]">{v.persona}</span>
                  <span className={v.risk > 60 ? "text-red-400" : "text-emerald-400"}>Risk {v.risk}%</span>
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

function RiskProjectionCard({ userId }: { userId: string }) {
  const [fanData, setFanData] = useState<any>(null);

  useEffect(() => {
    simulationApi.getFanChart(userId).then(setFanData).catch(() => setFanData(null));
  }, [userId]);

  const formatted = useMemo(() => {
    if (Array.isArray(fanData?.fan_chart_series)) {
      return fanData.fan_chart_series.map((p: any, idx: number) => ({
        day: p.day ?? idx + 1,
        p10: Number(p.p10 ?? 0),
        p50: Number(p.p50 ?? 0),
        p90: Number(p.p90 ?? 0),
      }));
    }
    if (fanData?.fan_chart && !Array.isArray(fanData.fan_chart)) {
      const fan = fanData.fan_chart;
      const p10 = Array.isArray(fan?.p10) ? fan.p10 : [];
      const p50 = Array.isArray(fan?.p50) ? fan.p50 : [];
      const p90 = Array.isArray(fan?.p90) ? fan.p90 : [];
      const n = Math.min(p10.length, p50.length, p90.length);
      return Array.from({ length: n }).map((_, idx) => ({
        day: idx + 1,
        p10: Number(p10[idx] ?? 0),
        p50: Number(p50[idx] ?? 0),
        p90: Number(p90[idx] ?? 0),
      }));
    }
    const arr = Array.isArray(fanData?.fan_chart) ? fanData.fan_chart : [];
    return arr.map((p: any, idx: number) => ({
      day: Number(p.day ?? p.month ?? idx + 1),
      p10: Number(p.p10 ?? 0),
      p50: Number(p.p50 ?? 0),
      p90: Number(p.p90 ?? 0),
    }));
  }, [fanData]);

  return (
    <Card className="border-border shadow-sm h-full">
      <CardHeader className="py-3 px-4 border-b">
        <CardTitle className="text-sm font-semibold">Risk Projection Graph</CardTitle>
      </CardHeader>
      <CardContent className="p-4">
        {formatted.length === 0 ? (
          <p className="text-xs text-muted-foreground text-center py-8">No projection data yet.</p>
        ) : (
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={formatted.slice(0, 90)} margin={{ top: 5, right: 5, left: -24, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
              <XAxis dataKey="day" tick={{ fontSize: 9 }} />
              <YAxis tick={{ fontSize: 9 }} />
              <Tooltip contentStyle={{ fontSize: 10 }} />
              <Area type="monotone" dataKey="p90" stroke="#22c55e" fill="#22c55e" fillOpacity={0.08} strokeWidth={1} />
              <Area type="monotone" dataKey="p50" stroke="#c8ff00" fill="none" strokeWidth={2} />
              <Area type="monotone" dataKey="p10" stroke="#ef4444" fill="#ef4444" fillOpacity={0.08} strokeWidth={1} />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  );
}

function InterventionHistoryCard({ userId }: { userId: string }) {
  const [triggers, setTriggers] = useState<any[]>([]);
  const [audit, setAudit] = useState<any[]>([]);

  useEffect(() => {
    Promise.all([
      twinApi.getTriggers(userId).catch(() => []),
      twinApi.getAudit(userId).catch(() => []),
    ]).then(([t, a]) => {
      const tr = Array.isArray(t) ? t : ((t as any)?.triggers ?? []);
      const rec = Array.isArray(a)
        ? a
        : (Array.isArray((a as any)?.records) ? (a as any).records : ((a as any)?.history ?? []));
      setTriggers(tr);
      setAudit(rec);
    });
  }, [userId]);

  return (
    <Card className="border-border shadow-sm h-full">
      <CardHeader className="py-3 px-4 border-b">
        <CardTitle className="text-sm font-semibold flex items-center justify-between">
          Intervention History
          <Badge variant="outline" className="text-[10px]">{triggers.length} active</Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="p-4 space-y-2">
        {triggers.slice(0, 6).map((t: any, i: number) => (
          <div key={`t:${i}`} className="text-xs border border-border/60 rounded px-2 py-1 bg-muted/20">
            <p className="font-semibold">{t.type ?? t.trigger_id ?? "Trigger"}</p>
            <p className="text-muted-foreground">{t.reason ?? t.message ?? "No detail"}</p>
          </div>
        ))}
        {audit.slice(0, 6).map((a: any, i: number) => (
          <div key={`a:${i}`} className="text-xs flex items-center justify-between bg-muted/30 rounded px-2 py-1">
            <span className="font-mono text-muted-foreground">{a.event_type ?? a.action ?? "update"}</span>
            <span className="truncate max-w-[55%] text-foreground/80">{a.summary ?? a.description ?? a.payload?.detail ?? ""}</span>
            <span className="text-muted-foreground">{fmtTs(String(a.timestamp ?? a.ts ?? ""))}</span>
          </div>
        ))}
        {triggers.length === 0 && audit.length === 0 && (
          <p className="text-xs text-muted-foreground text-center py-8">No intervention history yet.</p>
        )}
      </CardContent>
    </Card>
  );
}

function CreditDecisionLogCard({ userId }: { userId: string }) {
  const [decisions, setDecisions] = useState<any[]>([]);

  useEffect(() => {
    Promise.all([
      adminApi.getTier10Report(userId).catch(() => null),
      twinApi.getAudit(userId).catch(() => []),
    ]).then(([report, audit]) => {
      const reportDecisions = Array.isArray((report as any)?.credit_decisions)
        ? (report as any).credit_decisions
        : [];

      if (reportDecisions.length > 0) {
        setDecisions(reportDecisions);
        return;
      }

      const records = Array.isArray(audit)
        ? audit
        : (Array.isArray((audit as any)?.records)
          ? (audit as any).records
          : ((audit as any)?.history ?? []));

      const inferred = records
        .filter((e: any) => {
          const action = String(e?.action ?? e?.event_type ?? "").toLowerCase();
          return (
            action.includes("loan") ||
            action.includes("score") ||
            action.includes("decision") ||
            action.includes("threshold")
          );
        })
        .map((e: any) => ({
          task_id: e?.target_id ?? e?.id,
          status: e?.status ?? e?.action ?? e?.event_type,
          score_freshness: e?.timestamp ?? e?.ts,
          credit_score: e?.credit_score,
          risk_band: e?.risk_band,
          recommended_credit_limit: e?.recommended_credit_limit,
        }));

      setDecisions(inferred);
    });
  }, [userId]);

  return (
    <Card className="border-border shadow-sm h-full">
      <CardHeader className="py-3 px-4 border-b">
        <CardTitle className="text-sm font-semibold">Credit Decision Log</CardTitle>
      </CardHeader>
      <CardContent className="p-4">
        {decisions.length === 0 ? (
          <p className="text-xs text-muted-foreground text-center py-8">No credit decisions yet.</p>
        ) : (
          <div className="space-y-2 max-h-[260px] overflow-y-auto pr-1">
            {decisions.slice(0, 16).map((e: any, i: number) => (
              <div key={`${e.task_id ?? i}:${i}`} className="text-xs bg-muted/30 rounded px-2 py-1.5 border border-border/60">
                <div className="flex items-center justify-between">
                  <span className="font-semibold capitalize">{String(e.status ?? "decision").replace(/_/g, " ")}</span>
                  <span className="text-muted-foreground">{fmtTs(String(e.score_freshness ?? ""))}</span>
                </div>
                <div className="flex items-center gap-3 text-muted-foreground mt-0.5">
                  <span>Score: {e.credit_score ?? "—"}</span>
                  <span>Band: {e.risk_band ?? "—"}</span>
                  <span>Limit: {e.recommended_credit_limit ? `₹${Number(e.recommended_credit_limit).toLocaleString("en-IN")}` : "—"}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function AnomalyHeatmapCard({ userId }: { userId: string }) {
  const [cotData, setCotData] = useState<any>(null);
  const [reasoningResult, setReasoningResult] = useState<any>(null);
  const [vigilanceSummary, setVigilanceSummary] = useState<any>(null);
  const [twinState, setTwinState] = useState<any>(null);

  useEffect(() => {
    Promise.all([
      reasoningApi.getCot(userId).catch(() => null),
      reasoningApi.getResult(userId).catch(() => null),
      vigilanceApi.getSummary(userId).catch(() => null),
      twinApi.get(userId).catch(() => null),
    ]).then(([cot, res, vig, twin]) => {
      setCotData(cot);
      setReasoningResult(res);
      setVigilanceSummary(vig);
      setTwinState(twin);
    });
  }, [userId]);

  const base = cotData ?? reasoningResult ?? {};
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
      <CardHeader className="py-3 px-4 border-b">
        <CardTitle className="text-sm font-semibold">Anomaly Heatmap</CardTitle>
      </CardHeader>
      <CardContent className="p-4">
        <ResponsiveContainer width="100%" height={220}>
          <RadarChart data={radarData} outerRadius={75}>
            <PolarGrid stroke="rgba(255,255,255,0.15)" />
            <PolarAngleAxis dataKey="subject" tick={{ fontSize: 10 }} />
            <Radar name="Signals" dataKey="A" stroke="#c8ff00" fill="#c8ff00" fillOpacity={0.25} />
            <Tooltip contentStyle={{ fontSize: 10 }} />
          </RadarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}

export function ComplianceSnapshotGrid({ userId, title = "Tier 10 Compliance Snapshot" }: { userId: string; title?: string }) {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold tracking-wide">{title}</h3>
        <Badge variant="outline" className="text-[10px]">Admin parity</Badge>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <TwinTimelineCard userId={userId} />
        <RiskProjectionCard userId={userId} />
      </div>
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <InterventionHistoryCard userId={userId} />
        <CreditDecisionLogCard userId={userId} />
        <AnomalyHeatmapCard userId={userId} />
      </div>
    </div>
  );
}
