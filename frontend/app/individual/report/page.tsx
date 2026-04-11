"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/dib/authContext";
import { individualApi, vigilanceApi, reasoningApi } from "@/dib/api";
import { PageHeader } from "@/components/shared";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Loader2, AlertTriangle, RefreshCw, TrendingUp, TrendingDown,
  PiggyBank, Wallet, Smartphone, CreditCard, CheckCircle2, XCircle, Info,
} from "lucide-react";
import {
  Tooltip, TooltipContent, TooltipProvider, TooltipTrigger,
} from "@/components/ui/tooltip";
import { VigilanceReasoningCard } from "@/components/VigilanceReasoningCard";
import { cn } from "@/dib/utils";

function fmtINR(n: number) {
  if (n >= 100000) return `₹${(n / 100000).toFixed(1)}L`;
  if (n >= 1000) return `₹${(n / 1000).toFixed(0)}K`;
  return `₹${n}`;
}

const TIPS: Record<string, string> = {
  financial_health_score: "Score from 0–100 reflecting your overall personal financial wellbeing.",
  savings_rate_pct: "Percentage of estimated income saved. Above 20% is healthy.",
  emi_burden_pct: "Portion of income going towards EMIs. Below 30% is considered safe.",
  credit_card_utilisation_pct: "Credit used vs limit. Below 30% is ideal for a good credit profile.",
  debit_credit_ratio: "Ratio of outflows to inflows. Lower is better.",
};

export default function IndividualReport() {
  const { user } = useAuth();
  const router = useRouter();
  const [score, setScore] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!user) return;
    if (user.role !== "individual") { router.push("/login"); return; }
    individualApi.getScore(user.id)
      .then((d: any) => { setScore(d); setError(false); })
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [user, router]);

  if (!user || user.role !== "individual") return null;

  if (loading) return (
    <div className="p-6 w-full max-w-[1200px] mx-auto flex flex-col items-center justify-center h-64 gap-4 text-muted-foreground">
      <Loader2 className="w-10 h-10 animate-spin text-primary" />
      <p className="text-sm">Building your financial report…</p>
    </div>
  );

  if (error || !score) return (
    <div className="p-6 w-full max-w-[1200px] mx-auto flex flex-col items-center justify-center h-64 gap-3 text-muted-foreground">
      <AlertTriangle className="w-10 h-10 text-amber-500" />
      <p className="text-sm">Could not load report. Is the backend running?</p>
      <Button size="sm" onClick={() => window.location.reload()}>Retry</Button>
    </div>
  );

  const metrics = [
    { label: "Financial Health Score", value: `${score.financial_health_score}/100`, tip: TIPS.financial_health_score, good: score.financial_health_score >= 60 },
    { label: "Savings Rate", value: `${(score.savings_rate_pct ?? 0).toFixed(1)}%`, tip: TIPS.savings_rate_pct, good: score.savings_rate_pct >= 20 },
    { label: "EMI Burden", value: `${(score.emi_burden_pct ?? 0).toFixed(1)}%`, tip: TIPS.emi_burden_pct, good: score.emi_burden_pct <= 30 },
    { label: "Card Utilisation", value: `${(score.credit_card_utilisation_pct ?? 0).toFixed(1)}%`, tip: TIPS.credit_card_utilisation_pct, good: score.credit_card_utilisation_pct <= 30 },
    { label: "Est. Monthly Income", value: fmtINR(score.monthly_income_estimate ?? 0), tip: "Estimated from UPI inflow patterns.", good: true },
    { label: "Est. Monthly Expenses", value: fmtINR(score.monthly_expense_estimate ?? 0), tip: "Estimated from UPI outflow patterns.", good: true },
    { label: "Debit / Credit Ratio", value: (score.debit_credit_ratio ?? 0).toFixed(2), tip: TIPS.debit_credit_ratio, good: (score.debit_credit_ratio ?? 0) <= 0.5 },
    { label: "UPI Txns (30d)", value: `${score.upi_transaction_count_30d ?? 0}`, tip: "Total UPI transactions in the last 30 days.", good: true },
  ];

  return (
    <TooltipProvider>
      <div className="p-6 w-full max-w-[1200px] mx-auto space-y-6">
        <PageHeader
          title="Financial Health Report"
          description={`Generated: ${new Date(score.computed_at || Date.now()).toLocaleDateString("en-IN", { day: "numeric", month: "long", year: "numeric" })}`}
          actions={<Button variant="outline" size="sm" className="gap-2" onClick={() => window.location.reload()}><RefreshCw className="w-3.5 h-3.5" /> Refresh</Button>}
        />

        {/* Metrics Grid */}
        <Card className="border-border shadow-sm">
          <CardHeader className="py-3 px-4 border-b">
            <CardTitle className="text-sm font-semibold">Score Details</CardTitle>
          </CardHeader>
          <CardContent className="p-4 grid grid-cols-2 md:grid-cols-4 gap-3">
            {metrics.map((m) => (
              <div key={m.label} className="bg-muted rounded-lg p-3">
                <div className="flex items-center gap-1 mb-1.5">
                  <span className="text-xs text-muted-foreground">{m.label}</span>
                  <Tooltip>
                    <TooltipTrigger><Info className="w-3 h-3 text-muted-foreground" /></TooltipTrigger>
                    <TooltipContent className="max-w-xs text-xs">{m.tip}</TooltipContent>
                  </Tooltip>
                </div>
                <div className="flex items-center gap-2">
                  {m.good
                    ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 shrink-0" />
                    : <XCircle className="w-3.5 h-3.5 text-amber-500 shrink-0" />}
                  <p className="text-sm font-bold text-foreground">{m.value}</p>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>

        {/* Spending Breakdown */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Card className="border-border shadow-sm">
            <CardHeader className="py-3 px-4 border-b">
              <CardTitle className="text-sm font-semibold">Spending Breakdown</CardTitle>
            </CardHeader>
            <CardContent className="p-4 space-y-3">
              {(score.top_spending_categories || []).map((cat: any, i: number) => (
                <div key={cat.category} className="space-y-1.5">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-medium">{cat.category}</span>
                    <span className="text-muted-foreground font-mono">{cat.pct}%</span>
                  </div>
                  <div className="h-2 w-full bg-muted rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full"
                      style={{
                        width: `${cat.pct}%`,
                        backgroundColor: ["#6366f1","#f59e0b","#22c55e","#ec4899","#14b8a6"][i % 5],
                      }}
                    />
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>

          {/* Income Trend + History */}
          <Card className="border-border shadow-sm">
            <CardHeader className="py-3 px-4 border-b">
              <CardTitle className="text-sm font-semibold">Score History</CardTitle>
            </CardHeader>
            <CardContent className="p-4">
              <div className="flex items-end gap-1.5 h-32">
                {(score.score_history || []).map((h: any, i: number) => {
                  const history = score.score_history || [];
                  const max = Math.max(...history.map((x: any) => x.score));
                  const min = Math.min(...history.map((x: any) => x.score));
                  const range = max - min || 1;
                  const heightPct = 20 + ((h.score - min) / range) * 70;
                  const isLast = i === history.length - 1;
                  return (
                    <div key={h.date} className="flex-1 flex flex-col items-center gap-1">
                      <span className={cn("text-[10px] font-mono", isLast ? "text-primary font-bold" : "text-muted-foreground")}>{h.score}</span>
                      <div
                        className="w-full rounded-t-sm"
                        style={{
                          height: `${heightPct}%`,
                          backgroundColor: isLast ? "#c8ff00" : "rgba(200,255,0,0.25)",
                        }}
                      />
                      <span className="text-[8px] text-muted-foreground font-mono">{h.date.slice(5)}</span>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* AI Insights */}
        <Card className="border-border shadow-sm">
          <CardHeader className="py-3 px-4 border-b">
            <CardTitle className="text-sm font-semibold">AI Insights</CardTitle>
          </CardHeader>
          <CardContent className="p-4">
            <ul className="space-y-3">
              {(score.insights || []).map((insight: string, i: number) => (
                <li key={i} className="flex items-start gap-3">
                  <span className="w-5 h-5 rounded-full bg-primary text-primary-foreground text-xs font-bold flex items-center justify-center shrink-0 mt-0.5">{i + 1}</span>
                  <p className="text-sm text-foreground/90 leading-relaxed">{insight}</p>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      </div>
    </TooltipProvider>
  );
}
