"use client";
import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import gsap from "gsap";
import { useGSAP } from "@gsap/react";
import { useAuth } from "@/dib/authContext";
import { loanApi } from "@/dib/api";
import { useScore } from "@/hooks/useScore";
import { cn } from "@/dib/utils";
import {
  ScoreGauge,
  RiskBadge,
  PageHeader,
  StatCard,
  formatINR,
} from "@/components/shared";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  AlertTriangle,
  CheckCircle2,
  ArrowRight,
  Briefcase,
  CalendarClock,
  FileCheck2,
  FileText,
  Flag,
  Network,
  RefreshCw,
  TrendingUp,
  Shield,
  Loader2,
} from "lucide-react";
import { DigitalTwinCard } from "@/components/DigitalTwinCard";
import { SimulationPanel } from "@/components/SimulationPanel";
import { VigilanceReasoningCard } from "@/components/VigilanceReasoningCard";
import { ProcessingWorkflow } from "@/components/ProcessingWorkflow";

export default function MsmeDashboard() {
  const containerRef = useRef<HTMLDivElement>(null);

  const { user } = useAuth();
  const router = useRouter();
  const { score, status, refresh } = useScore(user?.gstin);
  const [loans, setLoans] = useState<any[]>([]);

  useGSAP(() => {
    if (!containerRef.current) return;
    gsap.fromTo(".gsap-card",
      { opacity: 0, y: 30, scale: 0.98 },
      { opacity: 1, y: 0, scale: 1, duration: 0.6, stagger: 0.08, ease: "power3.out", delay: 0.1 }
    );
  }, { scope: containerRef, dependencies: [status] });

  useEffect(() => {
    if (!user?.gstin) return;
    loanApi.list({ gstin: user.gstin }).then(setLoans).catch(() => { });
  }, [user?.gstin]);

  useEffect(() => {
    if (!user || user.role !== "msme") {
      router.push("/login");
    }
  }, [user, router]);

  if (!user || user.role !== "msme") {
    return null;
  }

  const pendingLoans = loans.filter((lr: any) =>
    ["submitted", "permission_requested", "data_shared", "bank_reviewing"].includes(lr.status),
  );

  const isCalculating = ["pending", "ingesting", "classifying", "extracting_features", "benchmarking", "scoring", "processing"].includes(status);

  if (isCalculating) {
    return (
      <div className="p-6 w-full max-w-[1400px] mx-auto min-h-screen flex flex-col">
        <PageHeader
          title={`Initializing Data Twin for ${(user.name || "User").split(" ")[0]}...`}
          description={`GSTIN: ${user.gstin} · Running autonomous credit pipeline`}
        />
        <div className="flex-1 flex flex-col items-center justify-center">
          <div className="w-full max-w-xl p-8 rounded-3xl border bg-card/50 backdrop-blur-xl shadow-2xl relative overflow-hidden gsap-card">
            <div className="absolute top-0 left-0 w-full h-1 bg-muted">
              <div className="h-full bg-primary transition-all duration-500" style={{
                width: (
                  status === "ingesting" ? "20%" :
                    status === "classifying" ? "40%" :
                      status === "extracting_features" ? "60%" :
                        status === "benchmarking" ? "80%" :
                          status === "scoring" ? "95%" : "5%"
                )
              }} />
            </div>
            <h3 className="text-xl font-bold mb-8 flex items-center gap-3">
              <Shield className="w-6 h-6 text-primary" />
              Calculating Credit Score
            </h3>
            <ProcessingWorkflow currentStatus={status} />
          </div>
          <p className="mt-8 text-sm text-muted-foreground animate-pulse tracking-wide uppercase">
            Airavat Tier 4 Cognitive Engine Active
          </p>
        </div>
      </div>
    );
  }

  if (status === "failed" || !score) {
    return (
      <div className="p-6 w-full max-w-[1400px] mx-auto">
        <PageHeader
          title={`Welcome back, ${(user.name || "User").split(" ")[0]}`}
          description={`GSTIN: ${user.gstin}`}
          actions={
            <Button variant="outline" size="sm" className="gap-2" onClick={refresh}>
              <RefreshCw className="w-3.5 h-3.5" /> Retry
            </Button>
          }
        />
        <div className="flex flex-col items-center justify-center h-48 gap-3 text-muted-foreground">
          <AlertTriangle className="w-10 h-10 text-amber-500" />
          <p className="text-sm">Could not load score. Is the backend running?</p>
          <Button size="sm" onClick={refresh}>Retry</Button>
        </div>
      </div>
    );
  }

  return (
    <div ref={containerRef} className="p-6 w-full max-w-[1400px] mx-auto">
      <div className="gsap-card opacity-0">
        <PageHeader
          title={`Welcome back, ${(user.name || "User").split(" ")[0]}`}
          description={`GSTIN: ${user.gstin} · Last scored: ${score.score_freshness ? new Date(score.score_freshness).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }) : new Date(score.computed_at || Date.now()).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}`}
          actions={
            <Button
              variant="outline"
              size="sm"
              onClick={() => refresh()}
              disabled={false}
              className="glass"
            >
              <RefreshCw className="w-4 h-4 mr-2" />
              Recalculate
            </Button>
          }
        />
      </div>

      {/* Banners */}
      {score.data_maturity_months < 3 && (
        <div className="mb-4 flex items-start gap-3 p-4 bg-[rgba(255,170,0,0.08)] border border-[rgba(255,170,0,0.25)] rounded-xl text-[#FFAA00] gsap-card opacity-0">
          <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" />
          <div>
            <p className="font-semibold text-sm">Low Data Quality Warning</p>
            <p className="text-sm text-[#E09500]">
              Your data maturity is only {score.data_maturity_months} months.
              Scores improve with more history.
            </p>
          </div>
        </div>
      )}
      {score.fraud_flag && (
        <div className="mb-4 flex items-start gap-3 p-4 bg-[rgba(255,0,64,0.08)] border border-[rgba(255,0,64,0.25)] rounded-xl gsap-card opacity-0">
          <Flag className="w-5 h-5 shrink-0 mt-0.5 text-[#FF0040]" />
          <div className="flex-1">
            <p className="font-semibold text-sm text-[#FF0040]">Fraud Alert</p>
            <p className="text-sm text-[#E0003A]">
              Your GSTIN has been flagged as part of a suspicious transaction
              pattern. You can raise a dispute to review this.
            </p>
          </div>
          <Button
            size="sm"
            variant="destructive"
            onClick={() => router.push("/msme/disputes")}
          >
            Raise Dispute
          </Button>
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-12 gap-4">
        <div className="xl:col-span-5 flex flex-col gap-4">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="gsap-card opacity-0">
              <StatCard
                label="Category"
                value={
                  score.msme_category
                    ? score.msme_category.charAt(0).toUpperCase() + score.msme_category.slice(1)
                    : "Individual"
                }
                icon={TrendingUp}
              />
            </div>
            <div className="gsap-card opacity-0">
              <StatCard
                label="Data Maturity"
                value={`${score.data_maturity_months}mo`}
                icon={FileText}
              />
            </div>
            <div className="gsap-card opacity-0">
              <StatCard
                label="Pending Loans"
                value={pendingLoans.length}
                icon={Briefcase}
              />
            </div>
          </div>

          <div className="gsap-card opacity-0">
            <DigitalTwinCard score={score} />
          </div>

          <Card className="border-border shadow-sm gsap-card opacity-0">
            <CardHeader className="py-3 px-4 border-b">
              <CardTitle className="text-sm font-semibold">
                Scheme Eligibility
              </CardTitle>
            </CardHeader>
            <CardContent className="p-4 flex gap-4">
              <div
                className={`flex items-center gap-2 px-3 py-2 rounded-lg ${score.cgtmse_eligible ? "bg-emerald-50 text-emerald-700" : "bg-muted text-muted-foreground"}`}
              >
                {score.cgtmse_eligible ? (
                  <CheckCircle2 className="w-4 h-4" />
                ) : (
                  <Shield className="w-4 h-4" />
                )}
                <span className="text-sm font-medium">CGTMSE</span>
              </div>
              <div
                className={`flex items-center gap-2 px-3 py-2 rounded-lg ${score.mudra_eligible ? "bg-emerald-50 text-emerald-700" : "bg-muted text-muted-foreground"}`}
              >
                {score.mudra_eligible ? (
                  <CheckCircle2 className="w-4 h-4" />
                ) : (
                  <Shield className="w-4 h-4" />
                )}
                <span className="text-sm font-medium">MUDRA</span>
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="xl:col-span-4 flex flex-col gap-4">
          <div className="gsap-card opacity-0 min-h-[380px] xl:h-[380px]">
            <VigilanceReasoningCard userId={user.gstin ?? user.id} />
          </div>

          <Card className="border-border shadow-sm gsap-card opacity-0">
            <CardHeader className="py-3 px-4 border-b">
              <CardTitle className="text-sm font-semibold">
                Top Score Drivers
              </CardTitle>
            </CardHeader>
            <CardContent className="p-4">
              <ul className="space-y-3">
                {(score.top_reasons || [])
                  .filter((r: string) => !r.startsWith("Path to Prime"))
                  .slice(0, 3)
                  .map((reason: string, i: number) => {
                    const icon =
                      i === 0 ? CalendarClock : i === 1 ? FileCheck2 : Network;
                    const impactLabel = i < 2 ? "HIGH IMPACT" : "MEDIUM IMPACT";
                    const impactValue = i < 2 ? 88 : 64;
                    const Icon = icon;
                    return (
                    <li
                      key={i}
                      className="rounded-2xl border border-white/10 bg-white/[0.02] p-3"
                    >
                      <div className="flex items-center gap-3">
                        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-primary/25 bg-primary/10 text-primary">
                          <Icon className="h-5 w-5" />
                        </div>
                        <div className="min-w-0 flex-1">
                          <p className="text-sm font-medium text-foreground leading-snug">{reason}</p>
                        </div>
                        <div className="w-32 shrink-0">
                          <p className="text-[10px] font-semibold tracking-wide text-lime-400 text-right">{impactLabel}</p>
                          <div className="mt-1 h-2 w-full rounded-full bg-white/10 overflow-hidden">
                            <div
                              className="h-full rounded-full bg-gradient-to-r from-lime-400 to-lime-300"
                              style={{ width: `${impactValue}%` }}
                            />
                          </div>
                        </div>
                      </div>
                    </li>
                    );
                  })}
              </ul>
            </CardContent>
          </Card>
        </div>

        <div className="xl:col-span-3 flex flex-col gap-4">
          <Card className="border-border shadow-sm gsap-card opacity-0">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
                Credit Score
              </CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col items-center gap-3">
              <ScoreGauge score={score.credit_score} size={180} />
              <RiskBadge band={score.risk_band} />
              <div className="w-full grid grid-cols-2 gap-2 mt-2">
                <div className="text-center p-2 bg-muted rounded-lg">
                  <p className="text-xs text-muted-foreground">WC Eligible</p>
                  <p className="text-sm font-bold text-foreground">
                    {formatINR(score.recommended_wc_amount)}
                  </p>
                </div>
                <div className="text-center p-2 bg-muted rounded-lg">
                  <p className="text-xs text-muted-foreground">Term Eligible</p>
                  <p className="text-sm font-bold text-foreground">
                    {score.recommended_term_amount > 0
                      ? formatINR(score.recommended_term_amount)
                      : "N/A"}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="border-border shadow-sm gsap-card opacity-0 min-h-[380px] xl:h-[380px] flex flex-col py-0">
            <CardHeader className="py-3 px-4 border-b">
              <CardTitle className="text-sm font-semibold">Quick Actions</CardTitle>
            </CardHeader>
            <CardContent className="p-3 flex flex-col gap-2.5 flex-1">
              {[
                {
                  label: "Request a Loan",
                  desc: "Apply to a bank with your credit profile",
                  href: "/msme/loans",
                  primary: true,
                },
                {
                  label: "View Full Report",
                  desc: "See detailed score metrics",
                  href: "/msme/score-report",
                  primary: false,
                },
                {
                  label: "Raise a Dispute",
                  desc: "Contest a fraud flag on your GSTIN",
                  href: "/msme/disputes",
                  primary: false,
                },
              ].map((action) => (
                <button
                  key={action.href}
                  onClick={() => router.push(action.href)}
                  className={cn(
                    "flex flex-col justify-center p-3 rounded-lg transition-all text-left border",
                    action.primary
                      ? "bg-primary text-primary-foreground border-primary hover:bg-primary/90"
                      : "glass border-border hover:border-primary/50"
                  )}
                >
                  <div className="flex items-center justify-between w-full mb-0.5">
                    <span className="font-semibold text-[15px] tracking-tight leading-tight">{action.label}</span>
                    <ArrowRight className="w-[18px] h-[18px] shrink-0 opacity-70" />
                  </div>
                  <p
                    className={cn("text-[13px] leading-snug", action.primary ? "text-primary-foreground/80" : "text-muted-foreground")}
                  >
                    {action.desc}
                  </p>
                </button>
              ))}
            </CardContent>
          </Card>
        </div>

        {(score.top_reasons || []).some((r: string) => r.startsWith("Path to Prime")) && (
          <Card className="xl:col-span-12 border-[rgba(200,255,0,0.15)] shadow-sm gsap-card opacity-0 bg-[rgba(200,255,0,0.04)]">
            <CardHeader className="py-3 px-4 border-b border-[rgba(200,255,0,0.1)]">
              <CardTitle className="text-sm font-semibold text-[#C8FF00] flex items-center gap-2">
                <TrendingUp className="w-4 h-4" />
                Path to Prime
              </CardTitle>
            </CardHeader>
            <CardContent className="p-4">
              <p className="text-sm text-[#F0F0F0]/90 leading-relaxed">
                {(score.top_reasons || [])
                  .find((r: string) => r.startsWith("Path to Prime"))
                  ?.replace("Path to Prime:", "")
                  .trim()}
              </p>
            </CardContent>
          </Card>
        )}

        {/* Tier 6 Risk Simulation Panel */}
        <div className="xl:col-span-12 gsap-card opacity-0">
          <SimulationPanel userId={user.gstin ?? user.id} score={score} />
        </div>
      </div>
    </div>
  );
}
