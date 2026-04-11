"use client";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/dib/authContext";
import { adminApi } from "@/dib/api";
import { PageHeader } from "@/components/shared";
import { TimeSeriesPanel } from "@/components/TimeSeriesPanel";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Search, Loader2, AlertTriangle, BarChart3, User, Building2,
  TrendingUp, TrendingDown, ShieldAlert, CheckCircle2, FileText,
  Download,
} from "lucide-react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import { cn } from "@/dib/utils";

function fmtINR(n: number) {
  if (n >= 10_000_000) return `${(n / 10_000_000).toFixed(1)}Cr`;
  if (n >= 100_000) return `${(n / 100_000).toFixed(1)}L`;
  return `₹${n.toLocaleString("en-IN")}`;
}

function RiskBadge({ band }: { band?: string }) {
  if (!band) return null;
  const map: Record<string, string> = {
    low_risk: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
    medium_risk: "bg-amber-500/15 text-amber-400 border-amber-500/30",
    high_risk: "bg-red-500/15 text-red-400 border-red-500/30",
  };
  return (
    <Badge variant="outline" className={cn("text-xs capitalize", map[band] ?? "")}>
      {band.replace(/_/g, " ")}
    </Badge>
  );
}

export default function EntityProfilePage() {
  const { user } = useAuth();
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);

  useEffect(() => {
    if (!user) return;
    if (!["credit_analyst", "risk_manager", "admin"].includes(user.role)) {
      router.push("/unauthorized");
    }
  }, [user, router]);

  const search = async (q = query) => {
    if (!q.trim()) return;
    setLoading(true); setResult(null); setError(null);
    try {
      const res = await adminApi.profileSearch(q.trim());
      setResult(res);
    } catch (e: any) {
      setError(e?.message ?? "Entity not found. Try a valid GSTIN or user ID.");
    } finally {
      setLoading(false);
    }
  };

  const exportProfile = async () => {
    if (!result) return;
    setGenerating(true);
    try {
      const blob = new Blob([JSON.stringify(result, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `entity_profile_${result.gstin ?? result.user?.id ?? "unknown"}_${Date.now()}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } finally {
      setGenerating(false);
    }
  };

  const printPdf = () => {
    window.print();
  };

  if (!user || !["credit_analyst", "risk_manager", "admin"].includes(user.role)) return null;

  const shap: any[] = result?.shap_waterfall ?? [];
  const scoreBreakdown = result?.score_breakdown ?? {};
  const fraudAlerts: any[] = result?.fraud_alerts ?? [];
  const indScore: any = result?.individual_score;

  return (
    <div className="p-6 max-w-[1300px] mx-auto space-y-6 print:p-2">
      <PageHeader
        title="Entity Profile — End-to-End Intelligence"
        description="Search any GSTIN, user ID, Account Number, or IFSC for a full 360-degree view: transactions, credit score, risk signals, SHAP breakdown, and time-series analytics."
        actions={
          result && (
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" className="gap-1.5 h-8 text-xs" onClick={exportProfile} disabled={generating}>
                {generating ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />}
                JSON
              </Button>
              <Button variant="outline" size="sm" className="gap-1.5 h-8 text-xs print:hidden" onClick={printPdf}>
                <FileText className="w-3.5 h-3.5" /> PDF
              </Button>
            </div>
          )
        }
      />

      {/* Search bar */}
      <Card className="border-border shadow-sm print:hidden">
        <CardContent className="p-4">
          <div className="flex gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground pointer-events-none" />
              <Input
                className="pl-9 font-mono text-sm h-10"
                placeholder="Enter GSTIN, user ID, Account Number (e.g. 4099...) or IFSC (e.g. SBIN...)"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && search()}
              />
            </div>
            <Button className="gap-2 h-10" onClick={() => search()} disabled={loading || !query.trim()}>
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
              Search
            </Button>
          </div>

          {/* Quick access chips */}
          <div className="flex flex-wrap gap-2 mt-3">
            <p className="text-xs text-muted-foreground self-center">Quick:</p>
            {["19HLPRM4249Z3Z1", "09EXVAF9205D6Z0", "29ABCDE1234F1Z5", "usr_007", "409912345678", "SBIN0002499"].map((q) => (
              <button
                key={q}
                className="text-[10px] font-mono px-2 py-0.5 rounded bg-muted/50 border border-border text-muted-foreground hover:text-primary hover:border-primary transition-colors"
                onClick={() => { setQuery(q); search(q); }}
              >
                {q}
              </button>
            ))}
          </div>

          {error && (
            <p className="text-xs text-red-400 flex items-center gap-1.5 mt-3">
              <AlertTriangle className="w-3.5 h-3.5" /> {error}
            </p>
          )}
        </CardContent>
      </Card>

      {result && (
        <div className="space-y-5 animate-in fade-in slide-in-from-bottom-2 duration-300">

          {/* Identity header */}
          <Card className="border-border shadow-sm">
            <CardContent className="p-5">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="flex items-start gap-4">
                  <div className="p-3 rounded-xl bg-primary/10">
                    {result.gstin ? <Building2 className="w-6 h-6 text-primary" /> : <User className="w-6 h-6 text-primary" />}
                  </div>
                  <div>
                    <h2 className="text-base font-bold">
                      {result.business_name ?? result.user?.name ?? result.user_id ?? "Unknown Entity"}
                    </h2>
                    <div className="flex flex-wrap items-center gap-2 mt-1">
                      {result.gstin && <span className="text-xs font-mono text-muted-foreground">{result.gstin}</span>}
                      {result.user?.email && <span className="text-xs text-muted-foreground">{result.user.email}</span>}
                      {result.user?.account && (
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-mono text-muted-foreground">Acc: {result.user.account.accountNumber}</span>
                          <span className="text-xs font-mono text-muted-foreground">IFSC: {result.user.account.ifsc}</span>
                          <Badge variant="secondary" className="text-[9px] h-3.5 px-1">{result.user.account.type}</Badge>
                        </div>
                      )}
                      {result.user?.role && <Badge variant="outline" className="text-[10px] capitalize">{result.user.role.replace(/_/g, " ")}</Badge>}
                      <RiskBadge band={result.risk_band} />
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  {result.credit_score && (
                    <div className="text-right">
                      <p className="text-xs text-muted-foreground">Credit Score</p>
                      <p className="text-2xl font-black text-primary">{result.credit_score}</p>
                    </div>
                  )}
                </div>
              </div>

              {/* Score breakdown */}
              {Object.keys(scoreBreakdown).length > 0 && (
                <div className="mt-4 pt-4 border-t border-border grid grid-cols-2 sm:grid-cols-4 gap-3">
                  {Object.entries(scoreBreakdown).map(([k, v]: any) => (
                    <div key={k} className="bg-muted/40 rounded-lg px-3 py-2">
                      <p className="text-[10px] text-muted-foreground capitalize">{k.replace(/_/g, " ")}</p>
                      <p className="text-sm font-bold mt-0.5">
                        {typeof v === "number" && v < 2 ? `${(v * 100).toFixed(0)}%` : v?.toLocaleString?.() ?? v}
                      </p>
                    </div>
                  ))}
                </div>
              )}

              {/* Individual score detail */}
              {indScore && (
                <div className="mt-4 pt-4 border-t border-border">
                  <p className="text-xs font-semibold text-muted-foreground mb-2">Individual Financial Profile</p>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    {[
                      { label: "Monthly Income", value: indScore.monthly_income ? `${fmtINR(indScore.monthly_income)}` : "—" },
                      { label: "Monthly Expenses", value: indScore.monthly_expenses ? `${fmtINR(indScore.monthly_expenses)}` : "—" },
                      { label: "Savings Rate", value: indScore.savings_rate ? `${(indScore.savings_rate * 100).toFixed(1)}%` : "—" },
                      { label: "Risk Band", value: indScore.risk_band?.replace(/_/g, " ") ?? "—" },
                    ].map((m) => (
                      <div key={m.label} className="bg-muted/40 rounded-lg px-3 py-2">
                        <p className="text-[10px] text-muted-foreground">{m.label}</p>
                        <p className="text-sm font-bold mt-0.5 capitalize">{m.value}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Fraud alerts */}
          {fraudAlerts.length > 0 && (
            <Card className="border-red-500/20 bg-red-500/5 shadow-sm">
              <CardHeader className="py-3 px-4 border-b border-red-500/20">
                <CardTitle className="text-sm font-semibold flex items-center gap-2 text-red-400">
                  <ShieldAlert className="w-4 h-4" /> Active Fraud Alerts
                  <Badge variant="outline" className="text-[10px] border-red-500/30 text-red-400 ml-auto">{fraudAlerts.length}</Badge>
                </CardTitle>
              </CardHeader>
              <CardContent className="p-4 space-y-2">
                {fraudAlerts.map((a: any, i: number) => (
                  <div key={i} className="border border-red-500/20 rounded-lg px-3 py-2.5 text-xs">
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-semibold text-red-300 capitalize">{a.alert_type?.replace(/_/g, " ")}</span>
                      <span className="text-muted-foreground">{Math.round((a.confidence ?? 0) * 100)}% confidence</span>
                    </div>
                    <p className="text-foreground/70">{a.summary}</p>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {/* SHAP Waterfall */}
          {shap.length > 0 && (
            <Card className="border-border shadow-sm">
              <CardHeader className="py-3 px-4 border-b">
                <CardTitle className="text-sm font-semibold flex items-center gap-2">
                  <BarChart3 className="w-4 h-4 text-primary" /> SHAP Feature Attribution
                </CardTitle>
              </CardHeader>
              <CardContent className="p-4">
                <ResponsiveContainer width="100%" height={180}>
                  <BarChart
                    data={shap.map((s: any) => ({
                      label: s.label ?? s.feature_name?.replace(/_/g, " "),
                      value: Math.round(Math.abs(s.shap_value ?? s.abs_magnitude ?? 0) * 100),
                      direction: s.direction,
                    }))}
                    layout="vertical"
                    margin={{ top: 0, right: 20, left: 10, bottom: 0 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                    <XAxis type="number" tick={{ fontSize: 9 }} />
                    <YAxis type="category" dataKey="label" tick={{ fontSize: 9 }} width={140} />
                    <Tooltip contentStyle={{ fontSize: 11 }} formatter={(v: any) => [`${v}pts`, "Impact"]} />
                    <Bar
                      dataKey="value"
                      radius={[0, 3, 3, 0]}
                      fill="#c8ff00"
                      fillOpacity={0.8}
                      name="SHAP Impact"
                    />
                  </BarChart>
                </ResponsiveContainer>
                <div className="flex gap-4 mt-2 text-[10px] text-muted-foreground">
                  <span className="flex items-center gap-1"><TrendingUp className="w-3 h-3 text-emerald-400" /> Decreases risk</span>
                  <span className="flex items-center gap-1"><TrendingDown className="w-3 h-3 text-red-400" /> Increases risk</span>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Time Series Panel */}
          {(result.upi_timeline?.length > 0) && (
            <TimeSeriesPanel
              upiTimeline={result.upi_timeline}
              ewbTimeline={result.ewb_timeline ?? []}
              windows={result.windows}
              scoreHistory={result.score_history ?? []}
              title="Transaction Time Series — Full History"
              entityType={result.gstin ? "msme" : "individual"}
              account={result.user?.account}
            />
          )}

          {/* Insights (individual) */}
          {indScore?.insights?.length > 0 && (
            <Card className="border-border shadow-sm">
              <CardHeader className="py-3 px-4 border-b">
                <CardTitle className="text-sm font-semibold flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-primary" /> AI-Generated Insights
                </CardTitle>
              </CardHeader>
              <CardContent className="p-4 space-y-2">
                {indScore.insights.map((ins: any, i: number) => (
                  <div key={i} className="flex items-start gap-2 text-xs border border-border rounded-lg px-3 py-2">
                    <CheckCircle2 className="w-3.5 h-3.5 text-primary shrink-0 mt-0.5" />
                    <span className="text-foreground/80">{ins.text ?? ins}</span>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
