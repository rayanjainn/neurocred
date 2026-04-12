"use client";
import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { TrendingUp, BarChart3, Activity } from "lucide-react";
import {
  ComposedChart, AreaChart, Area, BarChart, Bar, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  Legend,
} from "recharts";
import { cn } from "@/dib/utils";

type Window = "30" | "60" | "90" | "365";

interface TimeSeriesPoint {
  date: string;
  volume?: number;
  count?: number;
  daily_volume?: number;
  daily_count?: number;
  daily_ewb_volume?: number;
  daily_ewb_count?: number;
}

interface TwinTimelinePoint {
  date: string;
  risk_score: number;
  version?: number;
}

interface WindowAgg {
  days: number;
  upi_volume: number;
  upi_count: number;
  ewb_volume?: number;
  ewb_count?: number;
  avg_daily_upi: number;
}

interface Props {
  upiTimeline: TimeSeriesPoint[];
  ewbTimeline?: TimeSeriesPoint[];
  twinTimeline?: TwinTimelinePoint[];
  windows?: { w30?: WindowAgg; w60?: WindowAgg; w90?: WindowAgg; w365?: WindowAgg };
  scoreHistory?: { date: string; score: number; risk_band?: string; delta?: number }[];
  title?: string;
  entityType?: "msme" | "individual";
  account?: import("@/dib/authContext").Account;
}

function fmtINR(n: number) {
  if (n >= 10_000_000) return `${(n / 10_000_000).toFixed(1)}Cr`;
  if (n >= 100_000) return `${(n / 100_000).toFixed(1)}L`;
  if (n >= 1000) return `${(n / 1000).toFixed(0)}K`;
  return String(n);
}

function sliceByDays<T extends { date: string }>(data: T[], days: number): T[] {
  // data is sorted oldest-first; take the last `days` entries
  return data.slice(-days);
}

// Downsample large arrays for performance (max ~60 points per chart)
function downsample<T>(data: T[], targetPoints = 60): T[] {
  if (data.length <= targetPoints) return data;
  const step = Math.ceil(data.length / targetPoints);
  return data.filter((_, i) => i % step === 0);
}

export function TimeSeriesPanel({
  upiTimeline,
  ewbTimeline = [],
  twinTimeline = [],
  windows,
  scoreHistory = [],
  title = "Transaction Time Series",
  entityType = "msme",
  account,
}: Props) {
  const [window, setWindow] = useState<Window>("90");

  const days = parseInt(window);
  const upiSlice = downsample(sliceByDays(upiTimeline, days));
  const ewbSlice = downsample(sliceByDays(ewbTimeline, days));
  const twinSlice = downsample(sliceByDays(twinTimeline, days));
  const winData = windows?.[`w${window}` as keyof typeof windows] as WindowAgg | undefined;

  // Merge UPI + EWB by date for combo chart
  const dateMap = new Map<string, { date: string; upi?: number; ewb?: number; upi_count?: number; twin_risk?: number }>();
  upiSlice.forEach((p) => {
    const label = (p.date || "").slice(0, 10); // YYYY-MM-DD
    const upiVolume = p.volume ?? p.daily_volume;
    const upiCount = p.count ?? p.daily_count;
    dateMap.set(p.date, { date: label, upi: upiVolume, upi_count: upiCount });
  });
  ewbSlice.forEach((p) => {
    const label = (p.date || "").slice(0, 10);
    const existing = dateMap.get(p.date) ?? { date: label };
    const ewbVolume = p.volume ?? p.daily_ewb_volume ?? p.daily_volume;
    dateMap.set(p.date, { ...existing, ewb: ewbVolume });
  });
  twinSlice.forEach((p) => {
    const label = (p.date || "").slice(0, 10);
    const existing = dateMap.get(p.date) ?? { date: label };
    dateMap.set(p.date, { ...existing, twin_risk: p.risk_score });
  });
  const combo = Array.from(dateMap.values());

  const WINDOW_LABELS: Record<Window, string> = {
    "30": "30 days",
    "60": "60 days",
    "90": "90 days",
    "365": "12 months",
  };

  return (
    <Card className="border-border shadow-sm">
      <CardHeader className="py-3 px-4 border-b flex-row items-center justify-between gap-2 flex-wrap">
        <CardTitle className="text-sm font-semibold flex items-center gap-2">
          <Activity className="w-4 h-4 text-primary" /> {title}
          {account && (
            <Badge variant="outline" className="text-[10px] font-mono ml-2 border-primary/20 text-primary/80">
              Acc: {account.accountNumber}
            </Badge>
          )}
        </CardTitle>
        <div className="flex items-center gap-1">
          {(["30", "60", "90", "365"] as Window[]).map((w) => (
            <Button
              key={w}
              size="sm"
              variant={window === w ? "default" : "ghost"}
              className="text-xs h-6 px-2"
              onClick={() => setWindow(w)}
            >
              {WINDOW_LABELS[w]}
            </Button>
          ))}
        </div>
      </CardHeader>
      <CardContent className="p-4 space-y-5">

        {/* Window Summary Stats */}
        {winData && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            {[
              { label: "UPI Volume", value: `₹${fmtINR(winData.upi_volume)}`, icon: TrendingUp, color: "text-primary" },
              { label: "UPI Transactions", value: winData.upi_count.toLocaleString(), icon: BarChart3, color: "text-blue-400" },
              { label: entityType === "msme" ? "EWB Volume" : "Expense Volume", value: `₹${fmtINR(winData.ewb_volume ?? 0)}`, icon: TrendingUp, color: "text-emerald-400" },
              { label: "Avg Daily UPI", value: `₹${fmtINR(winData.avg_daily_upi)}`, icon: Activity, color: "text-amber-400" },
            ].map((s) => (
              <div key={s.label} className="bg-muted/40 rounded-lg px-3 py-2.5">
                <p className="text-[10px] text-muted-foreground">{s.label}</p>
                <p className={cn("text-sm font-bold mt-0.5", s.color)}>{s.value}</p>
              </div>
            ))}
          </div>
        )}

        {/* UPI + EWB Volume Combo Chart */}
        {combo.length > 0 && (
          <div>
            <p className="text-xs font-semibold text-muted-foreground mb-2">
              UPI vs {entityType === "msme" ? "E-Way Bill" : "Expense"} Volume + Twin Risk — Last {WINDOW_LABELS[window]}
            </p>
            <ResponsiveContainer width="100%" height={200}>
              <ComposedChart data={combo} margin={{ top: 5, right: 10, left: -10, bottom: 0 }}>
                <defs>
                  <linearGradient id="upiGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="hsl(var(--primary))" stopOpacity={0.25} />
                    <stop offset="95%" stopColor="hsl(var(--primary))" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="ewbGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#22c55e" stopOpacity={0.25} />
                    <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="date" tick={{ fontSize: 9 }} interval={Math.ceil(combo.length / 8)} />
                <YAxis tick={{ fontSize: 9 }} tickFormatter={(v) => fmtINR(v)} width={48} />
                <YAxis
                  yAxisId="risk"
                  orientation="right"
                  domain={[0, 1]}
                  tick={{ fontSize: 9 }}
                  tickFormatter={(v) => `${Math.round((Number(v) || 0) * 100)}%`}
                  width={40}
                />
                <Tooltip
                  contentStyle={{ fontSize: 11 }}
                  formatter={(v: number, n: string) => {
                    if (n === "Twin Risk") return [`${(Number(v) * 100).toFixed(1)}%`, n];
                    return [`₹${fmtINR(Number(v) || 0)}`, n];
                  }}
                />
                <Legend iconSize={10} wrapperStyle={{ fontSize: 10 }} />
                <Area type="monotone" dataKey="upi" stroke="hsl(var(--primary))" fill="url(#upiGrad)" strokeWidth={2} name="UPI" />
                <Area type="monotone" dataKey="ewb" stroke="#22c55e" fill="url(#ewbGrad)" strokeWidth={1.5} name={entityType === "msme" ? "E-Way Bill" : "Expense"} />
                {twinSlice.length > 0 && (
                  <Line yAxisId="risk" type="monotone" dataKey="twin_risk" stroke="#f59e0b" strokeWidth={2} dot={false} name="Twin Risk" />
                )}
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Daily Transaction Count Bar Chart */}
        {upiSlice.length > 0 && (
          <div>
            <p className="text-xs font-semibold text-muted-foreground mb-2">Daily Transaction Count</p>
            <ResponsiveContainer width="100%" height={130}>
              <BarChart data={upiSlice.map((p) => ({ date: p.date.slice(5), count: p.count ?? p.daily_count }))} margin={{ top: 0, right: 10, left: -10, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="date" tick={{ fontSize: 9 }} interval={Math.ceil(upiSlice.length / 8)} />
                <YAxis tick={{ fontSize: 9 }} />
                <Tooltip contentStyle={{ fontSize: 11 }} />
                <Bar dataKey="count" fill="hsl(var(--primary))" fillOpacity={0.7} name="Transactions" radius={[2, 2, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Credit Score History (12-month) */}
        {scoreHistory.length > 0 && (
          <div>
            <p className="text-xs font-semibold text-muted-foreground mb-2">Credit Score History — 12 Months</p>
            <ResponsiveContainer width="100%" height={140}>
              <ComposedChart data={scoreHistory.map((p) => ({
                date: p.date.slice(0, 7),
                score: p.score,
                delta: p.delta ?? 0,
              }))} margin={{ top: 5, right: 10, left: -10, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="date" tick={{ fontSize: 9 }} />
                <YAxis yAxisId="score" domain={["auto", "auto"]} tick={{ fontSize: 9 }} />
                <YAxis yAxisId="delta" orientation="right" tick={{ fontSize: 9 }} />
                <Tooltip contentStyle={{ fontSize: 11 }} />
                <Line yAxisId="score" type="monotone" dataKey="score" stroke="#c8ff00" strokeWidth={2.5} dot={{ r: 4 }} name="Score" />
                <Bar yAxisId="delta" dataKey="delta" name="Delta" fill="#6366f1" fillOpacity={0.5} radius={[2, 2, 0, 0]} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        )}

      </CardContent>
    </Card>
  );
}
