"use client";
import { Check, Loader2 } from "lucide-react";
import { cn } from "@/dib/utils";
import { ScoreStatus } from "@/hooks/useScore";

interface Step {
  id: ScoreStatus;
  label: string;
  description: string;
}

const STEPS: Step[] = [
  { id: "ingesting", label: "Tier 1: Ingestion", description: "Parsing GST, UPI and Bank signals" },
  { id: "classifying", label: "Tier 2: Semantic Classification", description: "Mapping transactions to financial taxonomy" },
  { id: "extracting_features", label: "Tier 3: Behavioural Feature Extraction", description: "Computing volatility, stability, and discretionary indices" },
  { id: "benchmarking", label: "Tier 3: Peer Cohort Benchmarking", description: "Comparing against anonymised cohort averages by income and city tier" },
  { id: "scoring", label: "Tier 4: Cognitive Scoring", description: "Running XGBoost ensemble on feature vectors" },
];

export function ProcessingWorkflow({ currentStatus }: { currentStatus: ScoreStatus }) {
  const getStepStatus = (stepId: ScoreStatus, index: number) => {
    const statuses: ScoreStatus[] = ["ingesting", "classifying", "extracting_features", "benchmarking", "scoring", "complete"];
    const currentIndex = statuses.indexOf(currentStatus);
    const stepIndex = statuses.indexOf(stepId);

    if (currentStatus === "complete") return "completed";
    if (currentIndex > stepIndex) return "completed";
    if (currentIndex === stepIndex) return "active";
    return "pending";
  };

  return (
    <div className="space-y-6 w-full max-w-md mx-auto py-8">
      {STEPS.map((step, idx) => {
        const state = getStepStatus(step.id, idx);
        return (
          <div key={step.id} className="relative flex gap-4">
            {idx !== STEPS.length - 1 && (
              <div 
                className={cn(
                  "absolute left-[15px] top-8 w-[2px] h-full bg-border transition-colors duration-500",
                  state === "completed" && "bg-primary"
                )} 
              />
            )}
            
            <div className={cn(
              "relative z-10 w-8 h-8 rounded-full border-2 flex items-center justify-center bg-background transition-all duration-500",
              state === "completed" && "bg-primary border-primary text-primary-foreground",
              state === "active" && "border-primary text-primary shadow-[0_0_15px_rgba(var(--primary),0.3)]",
              state === "pending" && "border-muted text-muted-foreground"
            )}>
              {state === "completed" ? (
                <Check className="w-4 h-4" />
              ) : state === "active" ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <span className="text-xs font-medium">{idx + 1}</span>
              )}
            </div>

            <div className="flex-1 pt-0.5 pb-8">
              <p className={cn(
                "font-semibold text-sm transition-colors duration-500",
                state === "completed" && "text-foreground",
                state === "active" && "text-primary",
                state === "pending" && "text-muted-foreground"
              )}>
                {step.label}
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                {step.description}
              </p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
