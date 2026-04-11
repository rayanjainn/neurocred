"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/dib/authContext";
import { vigilanceApi } from "@/dib/api";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Loader2, TrendingDown, TrendingUp, AlertTriangle, ShieldCheck, UserX, LineChart } from "lucide-react";

interface AnomalyMetricsCardProps {
  userId?: string;
}

export function AnomalyMetricsCard({ userId }: AnomalyMetricsCardProps) {
  const { user } = useAuth();
  const targetId = userId || user?.id;
  
  const [loading, setLoading] = useState(true);
  const [summary, setSummary] = useState<any>(null);

  useEffect(() => {
    if (!targetId) return;
    setLoading(true);
    // Use summary instead of full result to just get the top-level flags efficiently
    vigilanceApi.getSummary(targetId)
      .then(res => setSummary(res))
      .catch((e) => console.error("Summary fetch error", e))
      .finally(() => setLoading(false));
  }, [targetId]);

  if (loading) {
    return (
      <Card className="border-border/50 glass h-full">
        <CardContent className="flex items-center justify-center h-48">
          <Loader2 className="w-6 h-6 animate-spin text-primary/50" />
        </CardContent>
      </Card>
    );
  }

  if (!summary) {
    return (
      <Card className="border-border/50 glass h-full">
        <CardContent className="flex items-center justify-center justify-center p-8 text-muted-foreground text-sm flex-col gap-2">
           <AlertTriangle className="w-8 h-8 opacity-50 mb-2" />
           No anomaly telemetry streams connected for this profile.
        </CardContent>
      </Card>
    );
  }

  const stressScore = (summary.stress_score ?? 0) * 100;
  const underreportScore = (summary.underreport_score ?? 0) * 100;
  const identityShiftScore = (summary.identity_shift_score ?? 0) * 100;

  return (
    <Card className="border-border/50 glass h-full flex flex-col overflow-hidden relative">
      <CardHeader className="py-3 px-4 border-b border-white/5 bg-white/[0.02]">
        <CardTitle className="text-sm font-semibold flex items-center gap-2">
          <LineChart className="w-4 h-4 text-primary" />
          Behavioural & Synthetic Anomaly Radar
        </CardTitle>
        <CardDescription className="text-[11px]">
          Detects Bot activity, Mule clusters, and progressive financial distress signals hidden from standard static views.
        </CardDescription>
      </CardHeader>
      
      <CardContent className="p-4 space-y-5">
        {/* Synthetic DNA Flags */}
        <div className="grid grid-cols-3 gap-2">
           <div className={`p-3 rounded-lg border ${summary.bot_flag ? "bg-red-500/10 border-red-500/20" : "bg-teal-500/5 border-teal-500/10"} flex flex-col gap-1`}>
             <span className="text-[10px] text-muted-foreground uppercase font-bold tracking-widest whitespace-nowrap">Bot DNA</span>
             <span className={`text-sm font-bold ${summary.bot_flag ? "text-red-400" : "text-teal-400"}`}>{summary.bot_flag ? "DETECTED" : "CLEAR"}</span>
           </div>
           <div className={`p-3 rounded-lg border ${summary.mule_flag ? "bg-red-500/10 border-red-500/20" : "bg-teal-500/5 border-teal-500/10"} flex flex-col gap-1`}>
             <span className="text-[10px] text-muted-foreground uppercase font-bold tracking-widest whitespace-nowrap">Mule Flag</span>
             <span className={`text-sm font-bold ${summary.mule_flag ? "text-red-400" : "text-teal-400"}`}>{summary.mule_flag ? "DETECTED" : "CLEAR"}</span>
           </div>
           <div className={`p-3 rounded-lg border ${summary.is_shell_hub ? "bg-amber-500/10 border-amber-500/20" : "bg-teal-500/5 border-teal-500/10"} flex flex-col gap-1`}>
             <span className="text-[10px] text-muted-foreground uppercase font-bold tracking-widest whitespace-nowrap">Shell Hub</span>
             <span className={`text-sm font-bold ${summary.is_shell_hub ? "text-amber-400" : "text-teal-400"}`}>{summary.is_shell_hub ? "SUSPICIOUS" : "CLEAR"}</span>
           </div>
        </div>

        <div className="border-t border-white/5 pt-4 space-y-4">
           {/* Financial Stress */}
           <div className="space-y-1">
             <div className="flex justify-between text-xs">
                <span className="font-semibold text-foreground/80">Hidden Financial Stress</span>
                <span className="font-mono opacity-80">{stressScore.toFixed(1)}%</span>
             </div>
             <Progress value={stressScore} className="h-1.5" indicatorClassName={stressScore > 75 ? "bg-red-500" : stressScore > 40 ? "bg-amber-500" : "bg-teal-500"} />
             <div className="flex justify-between items-center pt-0.5">
               <span className="text-[10px] text-muted-foreground">Polars rolling buffer depletion tracker</span>
               {summary.stress_trend < 0 ? (
                 <span className="text-[10px] text-red-400 flex items-center font-medium"><TrendingDown className="w-3 h-3 mr-1" /> Buffer dropping</span>
               ) : (
                 <span className="text-[10px] text-teal-400 flex items-center font-medium"><TrendingUp className="w-3 h-3 mr-1" /> Expanding</span>
               )}
             </div>
           </div>

           {/* Income Underreporting */}
           <div className="space-y-1">
             <div className="flex justify-between text-xs">
                <span className="font-semibold text-foreground/80">Income Underreporting Proxmity</span>
                <span className="font-mono opacity-80">{underreportScore.toFixed(1)}%</span>
             </div>
             <Progress value={underreportScore} className="h-1.5" indicatorClassName={underreportScore > 70 ? "bg-amber-600" : "bg-teal-500"} />
             <span className="text-[10px] text-muted-foreground block pt-0.5">Observed vs cohort-expected standard deviation</span>
           </div>

           {/* Identity Shift */}
           <div className="space-y-1">
             <div className="flex justify-between text-xs">
                <span className="font-semibold text-foreground/80">Behaviour & Identity Drift</span>
                <span className="font-mono opacity-80">{identityShiftScore.toFixed(1)}%</span>
             </div>
             <Progress value={identityShiftScore} className="h-1.5" indicatorClassName={identityShiftScore > 60 ? "bg-indigo-500" : "bg-teal-500"} />
             <div className="flex justify-between items-center pt-0.5">
               <span className="text-[10px] text-muted-foreground">JS Divergence on transaction taxonomy</span>
               {summary.js_divergence !== undefined && (
                   <span className="text-[9px] font-mono opacity-50">JS_DIV={(summary.js_divergence ?? 0).toFixed(3)}</span>
               )}
             </div>
           </div>
        </div>
      </CardContent>
    </Card>
  );
}
