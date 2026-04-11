"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/dib/authContext";
import LandingPage from "@/components/landing";

export default function Home() {
  const { user } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (user) {
      const redirectMap: Record<string, string> = {
        msme: "/msme/dashboard",
        loan_officer: "/bank/loan-queue",
        credit_analyst: "/analyst/shap-explorer",
        risk_manager: "/risk/fraud-queue",
        admin: "/admin/overview",
      };
      router.replace(redirectMap[user.role] || "/login");
    }
  }, [user, router]);

  // Show landing page for unauthenticated users
  if (!user) {
    return <LandingPage />;
  }

  return null;
}
