"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/dib/authContext";
import { PageHeader } from "@/components/shared";
import { VigilanceReasoningCard } from "@/components/VigilanceReasoningCard";
import { ScamAnalyzerCard } from "@/components/ScamAnalyzerCard";
import { AnomalyMetricsCard } from "@/components/AnomalyMetricsCard";
import { Card, CardContent } from "@/components/ui/card";
import { ShieldCheck, Eye, Radar } from "lucide-react";

export default function IndividualVigilancePage() {
  const { user } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!user) return;
    if (user.role !== "individual") router.push("/login");
  }, [user, router]);

  if (!user || user.role !== "individual") return null;

  return (
    <div className="p-6 w-full max-w-[1400px] mx-auto space-y-6">
      <PageHeader
        title="Guard AI · Vigilance & Reasoning"
        description="Real-time deception analysis, identity integrity signals, and AI narrative explanation of your risk profile (Tier 7-9 engines)"
      />

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-2">
        {[
          { icon: ShieldCheck, label: "Deception Detection", desc: "ML-powered scam and identity-shift signal analysis across your transaction graph." },
          { icon: Eye, label: "Vigilance Engine", desc: "Tier 8/9: Continuous monitoring for fraud ring proximity and velocity anomalies." },
          { icon: Radar, label: "Reasoning Layer", desc: "Tier 7: Chain-of-thought explanation of every risk score factor for full transparency." },
        ].map((item) => (
          <Card key={item.label} className="border-border shadow-sm">
            <CardContent className="p-5 flex flex-col gap-3">
              <div className="p-2.5 bg-primary/10 rounded-xl w-fit">
                <item.icon className="w-5 h-5 text-primary" />
              </div>
              <div>
                <p className="text-sm font-semibold">{item.label}</p>
                <p className="text-xs text-muted-foreground leading-relaxed mt-1">{item.desc}</p>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="md:col-span-2">
          <VigilanceReasoningCard userId={user.id} />
        </div>
        <div className="md:col-span-1">
          <AnomalyMetricsCard userId={user.id} />
        </div>
      </div>
      
      <div className="grid grid-cols-1 gap-6 pb-12">
        <ScamAnalyzerCard />
      </div>
    </div>
  );
}

