"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { 
  ShieldCheck, 
  BrainCircuit, 
  AlertOctagon, 
  ChevronRight, 
  MessageSquare,
  Search,
  Eye,
  ShieldAlert,
  Loader2,
  CheckCircle2,
  HelpCircle,
  RefreshCcw,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { vigilanceApi, reasoningApi } from "@/dib/api";
import { cn } from "@/dib/utils";
import { InterrogationRoom } from "./InterrogationRoom";

interface VigilanceReasoningCardProps {
  userId: string;
}

export function VigilanceReasoningCard({ userId }: VigilanceReasoningCardProps) {
  const [loading, setLoading] = useState(true);
  const [vigilance, setVigilance] = useState<any>(null);
  const [narrative, setNarrative] = useState<string>("");
  const [activeTab, setActiveTab] = useState<"vigilance" | "reasoning">("vigilance");
  const [refreshing, setRefreshing] = useState(false);
  const [interrogationSessionId, setInterrogationSessionId] = useState<string | null>(null);
  const [interrogationNeeded, setInterrogationNeeded] = useState(false);
  const [interrogationOpen, setInterrogationOpen] = useState(false);

  const fetchData = async (isManual = false) => {
    if (isManual) setRefreshing(true);
    else setLoading(true);
    
    try {
      if (isManual) {
        await Promise.all([
          vigilanceApi.run(userId).catch(() => null),
          reasoningApi.run(userId).catch(() => null)
        ]);
      }

      const [vResult, nResultRaw] = await Promise.all([
        vigilanceApi.getResult(userId).catch(() => null),
        reasoningApi.getNarrative(userId).catch(() => null)
      ]);
      
      const nResult = nResultRaw as any;
      setVigilance(vResult);
      setNarrative((nResult?.narrative as string) || "No autonomous explanation available for this profile yet.");
      
      if (nResult?.interrogation_needed && nResult?.interrogation_session_id) {
         setInterrogationNeeded(true);
         setInterrogationSessionId(nResult.interrogation_session_id);
      } else {
         setInterrogationNeeded(false);
         setInterrogationSessionId(null);
      }
    } catch (err) {
      console.error("Error fetching vigilance data:", err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    if (userId) fetchData();
  }, [userId]);

  if (loading) {
    return (
      <Card className="h-full border-border/50 glass overflow-hidden">
        <CardContent className="flex flex-col items-center justify-center h-[240px] gap-3">
          <Loader2 className="w-8 h-8 animate-spin text-primary/50" />
          <p className="text-xs text-muted-foreground font-mono uppercase tracking-widest">Initialising Guardian AI...</p>
        </CardContent>
      </Card>
    );
  }

  const riskLevel = vigilance?.overall_risk || "LOW";
  const deceptionScore = (vigilance?.deception_score || 0) * 100;

  return (
    <Card className="h-full border-border/50 glass overflow-hidden flex flex-col">
      <CardHeader className="py-3 px-4 border-b border-white/5 bg-white/[0.02] flex flex-row items-center justify-between space-y-0">
        <div className="flex bg-black/40 p-1 rounded-lg border border-white/5">
          <button
            onClick={() => setActiveTab("vigilance")}
            className={cn(
              "px-3 py-1 text-[10px] font-bold uppercase tracking-wider rounded-md transition-all flex items-center gap-1.5",
              activeTab === "vigilance" ? "bg-primary text-primary-foreground shadow-lg" : "text-muted-foreground hover:text-foreground"
            )}
          >
            <ShieldCheck className="w-3 h-3" /> Vigilance
          </button>
          <button
            onClick={() => setActiveTab("reasoning")}
            className={cn(
              "px-3 py-1 text-[10px] font-bold uppercase tracking-wider rounded-md transition-all flex items-center gap-1.5",
              activeTab === "reasoning" ? "bg-primary text-primary-foreground shadow-lg" : "text-muted-foreground hover:text-foreground"
            )}
          >
            <BrainCircuit className="w-3 h-3" /> Reasoning
          </button>
        </div>
        <div className="flex items-center gap-2">
           <Button 
            variant="ghost" 
            size="icon" 
            className="h-6 w-6 rounded-full hover:bg-white/5" 
            onClick={() => fetchData(true)}
            disabled={refreshing}
           >
            <RefreshCcw className={cn("w-3 h-3 text-muted-foreground", refreshing && "animate-spin text-primary")} />
           </Button>
           <Badge variant="outline" className={cn(
            "text-[9px] font-mono border-opacity-30",
            riskLevel === "HIGH" ? "text-red-400 border-red-500 bg-red-500/10" : "text-lime-400 border-lime-500 bg-lime-500/10"
          )}>
            {riskLevel} RISK INTEL
          </Badge>
        </div>
      </CardHeader>

      <CardContent className="p-0 flex-1 relative overflow-hidden">
        <AnimatePresence mode="wait">
          {activeTab === "vigilance" ? (
            <motion.div
              key="vigilance"
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 10 }}
              className="p-4 flex flex-col h-full gap-3 overflow-y-auto custom-scrollbar"
            >
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <div className="space-y-1">
                    <p className="text-xs text-muted-foreground font-medium flex items-center gap-1.5">
                      <Search className="w-3 h-3" /> Deception Analysis
                    </p>
                    <p className="text-lg font-bold tracking-tight">
                      {deceptionScore.toFixed(1)}% <span className="text-[10px] font-normal text-muted-foreground uppercase ml-1">Confidence</span>
                    </p>
                  </div>
                  <div className="w-16 h-16 rounded-full border-2 border-white/5 flex items-center justify-center relative">
                    <svg className="w-full h-full -rotate-90">
                      <circle
                        cx="32"
                        cy="32"
                        r="28"
                        fill="transparent"
                        stroke="currentColor"
                        strokeWidth="3"
                        className="text-white/5"
                      />
                      <circle
                        cx="32"
                        cy="32"
                        r="28"
                        fill="transparent"
                        stroke="currentColor"
                        strokeWidth="3"
                        strokeDasharray={175.9}
                        strokeDashoffset={175.9 * (1 - deceptionScore / 100)}
                        className={cn(
                          "transition-all duration-1000",
                          deceptionScore > 70 ? "text-red-500" : deceptionScore > 40 ? "text-amber-500" : "text-lime-500"
                        )}
                      />
                    </svg>
                    <ShieldAlert className={cn(
                      "w-5 h-5 absolute inset-0 m-auto opacity-50",
                      deceptionScore > 50 ? "text-red-400" : "text-lime-400"
                    )} />
                  </div>
                </div>

                <div className="space-y-3">
                  <div className="flex items-center justify-between text-[10px] text-muted-foreground uppercase font-bold tracking-widest">
                    <span>Integrity Signals</span>
                    <span>Status</span>
                  </div>
                  <div className="grid gap-2">
                    {(vigilance?.signals || [
                      { name: "Identity Consistency", score: 0.98, status: "clean" },
                      { name: "Transaction Velocity", score: 0.45, status: "warning" },
                      { name: "Network Ring Proximity", score: 0.12, status: "clean" },
                    ]).map((signal: any) => (
                      <div key={signal.name} className="bg-white/[0.03] border border-white/5 p-2 rounded-lg flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          {signal.status === "clean" ? (
                            <CheckCircle2 className="w-3.5 h-3.5 text-lime-400" />
                          ) : (
                            <AlertOctagon className="w-3.5 h-3.5 text-amber-400" />
                          )}
                          <span className="text-xs font-medium text-foreground/80">{signal.name}</span>
                        </div>
                        <span className="text-[10px] font-mono opacity-60">{((signal.score ?? 0) * 100).toFixed(0)}/100</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              <Button variant="outline" size="sm" className="w-full gap-2 border-white/10 hover:bg-white/5 group h-8">
                <Eye className="w-3 h-3 group-hover:text-primary transition-colors" />
                <span className="text-[10px] uppercase font-bold">Deep Scan Registry</span>
              </Button>
            </motion.div>
          ) : (
            <motion.div
              key="reasoning"
              initial={{ opacity: 0, x: 10 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -10 }}
              className="p-4 flex flex-col h-full gap-3 overflow-y-auto custom-scrollbar"
            >
              <div className="space-y-3">
                <p className="text-[10px] text-muted-foreground uppercase font-bold tracking-widest flex items-center gap-1.5">
                  <MessageSquare className="w-3 h-3" /> AI Narrative Explanation
                </p>
                <div className="bg-black/20 rounded-xl p-3 border border-white/5 min-h-[96px] relative">
                  <div className="absolute top-0 left-0 w-1 h-full bg-primary/40 rounded-full" />
                  <p className="text-sm italic leading-relaxed text-foreground/90 font-serif">
                    "{narrative}"
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <Button 
                  variant="ghost" 
                  size="sm" 
                  onClick={() => interrogationSessionId && setInterrogationOpen(true)}
                  disabled={!interrogationNeeded || !interrogationSessionId}
                  className={cn("flex-1 gap-2 bg-white/[0.02] text-[10px] uppercase font-bold h-9", interrogationNeeded ? "border border-amber-500/50 hover:bg-amber-500/10 text-amber-400" : "opacity-50")}
                >
                  <HelpCircle className="w-3.5 h-3.5" /> {interrogationNeeded ? "Interrogate (Action Req)" : "No Interrogation Req"}
                </Button>
                <Button variant="ghost" size="sm" className="flex-1 gap-2 bg-white/[0.02] hover:bg-white/5 text-[10px] uppercase font-bold h-9" onClick={() => fetchData(true)}>
                  <Search className="w-3.5 h-3.5 text-primary" /> Trace CoT
                </Button>
              </div>

              <div className="mt-auto space-y-2">
                <div className="flex items-center justify-between text-[9px] text-muted-foreground font-mono">
                  <span>REGULATORY AUDIT READY</span>
                  <span>TIER 7/9 COMPLIANT</span>
                </div>
                <div className="h-0.5 w-full bg-white/5 rounded-full overflow-hidden">
                  <motion.div 
                    initial={{ width: 0 }} 
                    animate={{ width: "100%" }} 
                    transition={{ duration: 2, repeat: Infinity }}
                    className="h-full bg-gradient-to-r from-transparent via-primary/50 to-transparent" 
                  />
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </CardContent>

      <InterrogationRoom
        open={interrogationOpen}
        onOpenChange={setInterrogationOpen}
        sessionId={interrogationSessionId || ""}
        onComplete={() => fetchData(true)}
      />
    </Card>
  );
}
