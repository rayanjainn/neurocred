"use client";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/dib/authContext";
import { individualApi, vigilanceApi, reasoningApi } from "@/dib/api";
import { cn } from "@/dib/utils";
import { PageHeader, RiskBadge } from "@/components/shared";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  AlertTriangle,
  Loader2,
  RefreshCw,
  TrendingUp,
  TrendingDown,
  Wallet,
  PiggyBank,
  Activity,
  CreditCard,
  Smartphone,
  CheckCircle2,
  Lightbulb,
  ShieldCheck,
  BrainCircuit,
  BarChart3,
} from "lucide-react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
} from "recharts";
import { VigilanceReasoningCard } from "@/components/VigilanceReasoningCard";

function formatINR(n: number) {
  if (n >= 10000000) return `₹${(n / 10000000).toFixed(1)}Cr`;
  if (n >= 100000) return `₹${(n / 100000).toFixed(1)}L`;
  if (n >= 1000) return `₹${(n / 1000).toFixed(0)}K`;
  return `₹${n}`;
}

function HealthGauge({ score }: { score: number }) {
  const pct = ((score - 0) / 100) * 100;
  const color =
    score >= 75 ? "#22c55e" : score >= 50 ? "#f59e0b" : "#ef4444";
  const radius = 54;
  const circ = 2 * Math.PI * radius;
  const dash = (pct / 100) * circ;

  return (
    <div className="relative flex items-center justify-center w-36 h-36">
      <svg className="absolute inset-0 w-full h-full -rotate-90" viewBox="0 0 120 120">
        <circle cx="60" cy="60" r={radius} fill="none" stroke="currentColor" strokeWidth="8" className="text-white/5" />
        <circle
          cx="60" cy="60" r={radius} fill="none"
          stroke={color} strokeWidth="8"
          strokeDasharray={`${dash} ${circ}`}
          strokeLinecap="round"
          style={{ transition: "stroke-dasharray 1s ease" }}
        />
      </svg>
      <div className="text-center z-10">
        <p className="text-3xl font-bold tracking-tight" style={{ color }}>{score}</p>
        <p className="text-[9px] text-muted-foreground uppercase font-bold tracking-widest">/ 100</p>
      </div>
    </div>
  );
}

function MiniBar({ pct, color }: { pct: number; color: string }) {
  return (
    <div className="h-2 w-full bg-white/5 rounded-full overflow-hidden">
      <div
        className="h-full rounded-full transition-all duration-700"
        style={{ width: `${pct}%`, backgroundColor: color }}
      />
    </div>
  );
}

function fmtTrendLabel(dateStr: string) {
  const dt = new Date(dateStr);
  if (Number.isNaN(dt.getTime())) {
    return dateStr.slice(5);
  }
  return dt.toLocaleDateString("en-IN", { month: "short" });
}

export default function IndividualDashboard() {
  const { user } = useAuth();
  const router = useRouter();
  const [score, setScore] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!user) return;
    if (user.role !== "individual") {
      router.push("/login");
      return;
    }
    setLoading(true);
    individualApi.getScore(user.id)
      .then((data: any) => { setScore(data); setError(false); })
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [user, router]);

  if (!user || user.role !== "individual") return null;

  if (loading) {
    return (
      <div className="p-6 w-full max-w-[1400px] mx-auto">
        <PageHeader title={`Welcome, ${user.name.split(" ")[0]}`} description="Loading your financial health report…" />
        <div className="flex flex-col items-center justify-center h-64 gap-4 text-muted-foreground">
          <Loader2 className="w-10 h-10 animate-spin text-primary" />
          <p className="text-sm">Analysing your financial signals…</p>
        </div>
      </div>
    );
  }

  if (error || !score) {
    return (
      <div className="p-6 w-full max-w-[1400px] mx-auto">
        <PageHeader title={`Welcome, ${user.name.split(" ")[0]}`} description="Could not load financial data" />
        <div className="flex flex-col items-center justify-center h-48 gap-3 text-muted-foreground">
          <AlertTriangle className="w-10 h-10 text-amber-500" />
          <p className="text-sm">Could not load score. Is the backend running?</p>
          <Button size="sm" onClick={() => window.location.reload()}>Retry</Button>
        </div>
      </div>
    );
  }

  const savingsRate = score.savings_rate_pct ?? 0;
  const emiPct = score.emi_burden_pct ?? 0;
  const creditUtil = score.credit_card_utilisation_pct ?? 0;
  const categories: { category: string; pct: number }[] = score.top_spending_categories ?? [];
  const insights: string[] = score.insights ?? [];
  const history: { date: string; score: number }[] = score.score_history ?? [];
  const scoreComponents: { id: string; label: string; weight: number; value: number; contribution: number }[] =
    score.score_components ?? [];
  const healthExplanation: string =
    score.health_explanation ?? "Backend score model explanation unavailable.";
  const scoreFormula: string =
    score.score_formula ?? "health = weighted blend of backend risk dimensions";

  const historySeries = history.map((h) => ({
    ...h,
    label: fmtTrendLabel(h.date),
  }));
  const firstScore = historySeries[0]?.score ?? 0;
  const lastScore = historySeries[historySeries.length - 1]?.score ?? 0;
  const deltaScore = lastScore - firstScore;
  const trendState = deltaScore > 1 ? "improving" : deltaScore < -1 ? "declining" : "stable";
  const maxScore = historySeries.length ? Math.max(...historySeries.map((x) => x.score)) : 0;
  const minScore = historySeries.length ? Math.min(...historySeries.map((x) => x.score)) : 0;

  const CATEGORY_COLORS = ["#6366f1", "#f59e0b", "#22c55e", "#ec4899", "#14b8a6"];

  return (
    <div className="p-6 w-full max-w-[1400px] mx-auto space-y-6">
      <PageHeader
        title={`Welcome, ${user.name.split(" ")[0]}`}
        description={`Personal Finance Dashboard · Last updated: ${new Date(score.computed_at || Date.now()).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}`}
        actions={
          <Button variant="outline" size="sm" className="gap-2 glass" onClick={() => window.location.reload()}>
            <RefreshCw className="w-4 h-4" /> Refresh
          </Button>
        }
      />

      {/* Row 1: Score + Key Stats */}
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-4">
        {/* Financial Health Score */}
        <Card className="xl:col-span-3 border-border shadow-sm">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold text-muted-foreground uppercase tracking-wide flex items-center gap-2">
              <Activity className="w-4 h-4 text-primary" /> Financial Health Score
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col items-center gap-3 pt-2">
            <HealthGauge score={score.financial_health_score ?? 0} />
            <RiskBadge band={score.risk_band ?? "low_risk"} />
            <p className="text-[11px] text-muted-foreground text-center leading-relaxed">
              {healthExplanation}
            </p>
            <p className="text-[10px] text-muted-foreground text-center font-mono leading-relaxed">
              {scoreFormula}
            </p>
            {scoreComponents.length > 0 && (
              <div className="w-full pt-1 space-y-1.5">
                {scoreComponents.map((c) => (
                  <div key={c.id} className="flex items-center justify-between text-[10px] text-muted-foreground">
                    <span>{c.label}</span>
                    <span className="font-mono">+{Number(c.contribution ?? 0).toFixed(1)}</span>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Key Metrics Grid */}
        <div className="xl:col-span-5 grid grid-cols-2 sm:grid-cols-2 gap-3">
          {[
            {
              label: "Est. Monthly Income",
              value: formatINR(score.monthly_income_estimate ?? 0),
              icon: TrendingUp,
              color: "text-emerald-400",
              bg: "bg-emerald-500/10",
            },
            {
              label: "Est. Monthly Expenses",
              value: formatINR(score.monthly_expense_estimate ?? 0),
              icon: TrendingDown,
              color: "text-red-400",
              bg: "bg-red-500/10",
            },
            {
              label: "Savings Rate",
              value: `${savingsRate.toFixed(1)}%`,
              icon: PiggyBank,
              color: savingsRate >= 20 ? "text-emerald-400" : "text-amber-400",
              bg: savingsRate >= 20 ? "bg-emerald-500/10" : "bg-amber-500/10",
            },
            {
              label: "EMI Burden",
              value: `${emiPct.toFixed(1)}%`,
              icon: Wallet,
              color: emiPct <= 30 ? "text-emerald-400" : "text-amber-400",
              bg: emiPct <= 30 ? "bg-emerald-500/10" : "bg-amber-500/10",
            },
            {
              label: "UPI Txns (30d)",
              value: `${score.upi_transaction_count_30d ?? 0}`,
              icon: Smartphone,
              color: "text-blue-400",
              bg: "bg-blue-500/10",
            },
            {
              label: "Card Utilisation",
              value: `${creditUtil.toFixed(1)}%`,
              icon: CreditCard,
              color: creditUtil <= 30 ? "text-emerald-400" : "text-amber-400",
              bg: creditUtil <= 30 ? "bg-emerald-500/10" : "bg-amber-500/10",
            },
          ].map((metric) => (
            <Card key={metric.label} className="border-border shadow-sm">
              <CardContent className="p-4 flex items-start gap-3">
                <div className={cn("p-2 rounded-lg shrink-0", metric.bg)}>
                  <metric.icon className={cn("w-4 h-4", metric.color)} />
                </div>
                <div>
                  <p className="text-xs text-muted-foreground font-medium">{metric.label}</p>
                  <p className="text-base font-bold text-foreground mt-0.5">{metric.value}</p>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Guard AI — Vigilance + Reasoning */}
        <div className="xl:col-span-4">
          <VigilanceReasoningCard userId={user.id} />
        </div>
      </div>

      {/* Row 2: Spending Breakdown + Score Trend + AI Insights */}
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-4">
        {/* Spending Breakdown */}
        <Card className="xl:col-span-4 border-border shadow-sm">
          <CardHeader className="py-3 px-4 border-b">
            <CardTitle className="text-sm font-semibold flex items-center gap-2">
              <BarChart3 className="w-4 h-4 text-primary" /> Spending Breakdown
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4 space-y-3">
            {categories.map((cat, i) => (
              <div key={cat.category} className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium text-foreground/80">{cat.category}</span>
                  <span className="text-xs font-mono text-muted-foreground">{cat.pct}%</span>
                </div>
                <MiniBar pct={cat.pct} color={CATEGORY_COLORS[i % CATEGORY_COLORS.length]} />
              </div>
            ))}
            {categories.length === 0 && (
              <p className="text-xs text-muted-foreground text-center py-4">No spending data available</p>
            )}
          </CardContent>
        </Card>

        {/* Score History Trend */}
        <Card className="xl:col-span-4 border-border shadow-sm">
          <CardHeader className="py-3 px-4 border-b">
            <CardTitle className="text-sm font-semibold flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-primary" /> Score Trend
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4">
            {historySeries.length > 0 ? (
              <div className="space-y-3">
                <ResponsiveContainer width="100%" height={150}>
                  <LineChart data={historySeries} margin={{ top: 5, right: 8, left: -24, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                    <XAxis dataKey="label" tick={{ fontSize: 9 }} />
                    <YAxis
                      tick={{ fontSize: 9 }}
                      domain={[
                        Math.max(0, minScore - 4),
                        Math.min(100, maxScore + 4),
                      ]}
                    />
                    <Tooltip
                      contentStyle={{ fontSize: 11 }}
                      formatter={(v: number) => [String(v), "Score"]}
                      labelFormatter={(label) => `Month: ${label}`}
                    />
                    <Line
                      type="monotone"
                      dataKey="score"
                      stroke="#c8ff00"
                      strokeWidth={2.5}
                      dot={{ r: 3 }}
                      activeDot={{ r: 5 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
                <div className="grid grid-cols-3 gap-2 text-[10px]">
                  <div className="bg-muted/30 rounded px-2 py-1.5 text-muted-foreground">
                    <p>Min</p>
                    <p className="font-mono text-foreground">{minScore}</p>
                  </div>
                  <div className="bg-muted/30 rounded px-2 py-1.5 text-muted-foreground">
                    <p>Max</p>
                    <p className="font-mono text-foreground">{maxScore}</p>
                  </div>
                  <div className="bg-muted/30 rounded px-2 py-1.5 text-muted-foreground">
                    <p>Delta</p>
                    <p className="font-mono text-foreground">{deltaScore > 0 ? "+" : ""}{deltaScore}</p>
                  </div>
                </div>
                <div className="flex items-center justify-between text-[10px] text-muted-foreground pt-0.5">
                  <span>6-month trend</span>
                  <span className={cn(
                    "font-bold",
                    trendState === "improving"
                      ? "text-emerald-400"
                      : trendState === "declining"
                        ? "text-red-400"
                        : "text-amber-400"
                  )}>
                    {trendState === "improving" ? "▲ Improving" : trendState === "declining" ? "▼ Declining" : "■ Stable"}
                  </span>
                </div>
              </div>
            ) : (
              <p className="text-xs text-muted-foreground text-center py-8">No history available</p>
            )}
          </CardContent>
        </Card>

        {/* AI Insights */}
        <Card className="xl:col-span-4 border-border shadow-sm">
          <CardHeader className="py-3 px-4 border-b">
            <CardTitle className="text-sm font-semibold flex items-center gap-2">
              <Lightbulb className="w-4 h-4 text-amber-400" /> AI Insights
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4">
            <ul className="space-y-3">
              {insights.map((insight, i) => (
                <li key={i} className="flex items-start gap-2.5">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                  <p className="text-xs text-foreground/85 leading-relaxed">{insight}</p>
                </li>
              ))}
              {insights.length === 0 && (
                <p className="text-xs text-muted-foreground text-center py-4">No insights available</p>
              )}
            </ul>
          </CardContent>
        </Card>
      </div>

      {/* Row 3: Debt-to-Credit Ratio + Income Trend Badge */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
        <Card className="border-border shadow-sm">
          <CardHeader className="py-3 px-4 border-b">
            <CardTitle className="text-sm font-semibold">Debit / Credit Ratio</CardTitle>
          </CardHeader>
          <CardContent className="p-4 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-2xl font-bold">{(score.debit_credit_ratio ?? 0).toFixed(2)}</span>
              <Badge
                variant="outline"
                className={cn(
                  "text-[10px]",
                  (score.debit_credit_ratio ?? 0) <= 0.5 ? "text-emerald-400 border-emerald-500" : "text-amber-400 border-amber-500"
                )}
              >
                {(score.debit_credit_ratio ?? 0) <= 0.5 ? "Healthy" : "Elevated"}
              </Badge>
            </div>
            <MiniBar pct={(score.debit_credit_ratio ?? 0) * 100} color={(score.debit_credit_ratio ?? 0) <= 0.5 ? "#22c55e" : "#f59e0b"} />
            <p className="text-[11px] text-muted-foreground">A ratio below 0.5 indicates healthy spending discipline.</p>
          </CardContent>
        </Card>

        <Card className="border-border shadow-sm">
          <CardHeader className="py-3 px-4 border-b">
            <CardTitle className="text-sm font-semibold">Income Trend</CardTitle>
          </CardHeader>
          <CardContent className="p-4 flex items-center gap-4">
            <div className={cn(
              "p-4 rounded-2xl",
              score.income_trend === "stable" ? "bg-emerald-500/10" : "bg-amber-500/10"
            )}>
              {score.income_trend === "stable" ? (
                <TrendingUp className="w-8 h-8 text-emerald-400" />
              ) : (
                <TrendingDown className="w-8 h-8 text-amber-400" />
              )}
            </div>
            <div>
              <p className="text-xl font-bold capitalize">{score.income_trend ?? "Unknown"}</p>
              <p className="text-xs text-muted-foreground mt-1">Based on 6-month UPI inflow analysis</p>
            </div>
          </CardContent>
        </Card>

        <Card className="border-border shadow-sm">
          <CardHeader className="py-3 px-4 border-b">
            <CardTitle className="text-sm font-semibold">Quick Actions</CardTitle>
          </CardHeader>
          <CardContent className="p-4 flex flex-col gap-2">
            {[
              { label: "Download Report", icon: BarChart3, desc: "Export your financial health report" },
              { label: "View Full Vigilance", icon: ShieldCheck, desc: "See detailed fraud signal analysis" },
              { label: "Ask AI Assistant", icon: BrainCircuit, desc: "Get personalised financial advice" },
            ].map((a) => (
              <button
                key={a.label}
                className="flex items-center gap-3 p-3 rounded-xl border border-border hover:border-primary/50 hover:bg-primary/5 transition-all text-left group"
              >
                <div className="p-1.5 bg-primary/10 rounded-lg">
                  <a.icon className="w-3.5 h-3.5 text-primary" />
                </div>
                <div>
                  <p className="text-xs font-semibold text-foreground group-hover:text-primary transition-colors">{a.label}</p>
                  <p className="text-[10px] text-muted-foreground">{a.desc}</p>
                </div>
              </button>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
