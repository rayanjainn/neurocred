"use client";
import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { useAuth, type Role } from "@/dib/authContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { 
  Eye, EyeOff, Loader2, Mail, Lock, 
  LogIn, User, Shield, Zap, Globe 
} from "lucide-react";
import { usersApi } from "@/dib/api";

const ROLE_LABELS: Record<string, string> = {
  individual: "Individual",
  msme: "MSME Owner",
  loan_officer: "Loan Officer",
  credit_analyst: "Credit Analyst",
  risk_manager: "Risk Manager",
  admin: "Admin",
};

const REDIRECT_MAP: Record<string, string> = {
  individual: "/individual/dashboard",
  msme: "/msme/dashboard",
  loan_officer: "/bank/loan-queue",
  credit_analyst: "/analyst/strategy-lab",
  risk_manager: "/risk/fraud-queue",
  admin: "/admin/overview",
};

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [demoUsers, setDemoUsers] = useState<any[]>([]);
  const demoScrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    usersApi.list().then(data => {
      // Prioritize showing one of each role if possible
      const seenRoles = new Set();
      const balanced = data.filter(u => {
        if (!seenRoles.has(u.role)) {
          seenRoles.add(u.role);
          return true;
        }
        return false;
      });
      // Fill up to 6 with others
      const others = data.filter(u => !balanced.find(b => b.id === u.id));
      setDemoUsers([...balanced, ...others].slice(0, 12));
    }).catch(err => {
      console.error("Failed to fetch demo users:", err);
      // Fallback for UI skeleton or empty state
    });
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const result = await login(email, password);
      if (!result.ok) {
        setError(result.error || "Login failed");
      } else {
        const role = result.user?.role as Role;
        router.push(REDIRECT_MAP[role] ?? "/");
      }
    } catch (err) {
      setError("Connection error. Is the backend running?");
    } finally {
      setLoading(false);
    }
  };

  const quickLogin = (uEmail: string) => {
    setEmail(uEmail);
    setPassword("demo");
  };

  const handleDemoWheel = (e: React.WheelEvent<HTMLDivElement>) => {
    const el = demoScrollRef.current;
    if (!el || el.scrollHeight <= el.clientHeight) return;
    e.preventDefault();
    e.stopPropagation();
    el.scrollTop += e.deltaY;
  };

  return (
    <div className="fixed inset-0 flex items-center justify-center p-0 lg:p-4 overflow-hidden bg-black selection:bg-[#c8ff00] selection:text-black">
      {/* Background Layer */}
      <div
        className="absolute inset-0 opacity-40 scale-105 blur-[2px]"
        style={{
          backgroundImage: "url('/image.png')",
          backgroundSize: "cover",
          backgroundPosition: "center",
          backgroundRepeat: "no-repeat",
        }}
      />
      <div className="absolute inset-0 bg-gradient-to-b from-black/80 via-black/40 to-black/80" />

      <div className="relative z-10 w-full h-full lg:h-[90vh] lg:max-h-[850px] lg:max-w-7xl lg:rounded-3xl border border-white/10 bg-black/40 shadow-[0_0_80px_rgba(0,0,0,0.5)] grid grid-cols-1 lg:grid-cols-[1fr_1.1fr] overflow-hidden backdrop-blur-xl">
        
        {/* Left Side: Login Form */}
        <div className="p-6 sm:p-10 lg:p-16 flex flex-col overflow-y-auto custom-scrollbar">
          <div className="w-full max-w-sm mx-auto my-auto space-y-8">
            <div className="space-y-2">
              <div className="flex items-center gap-2 mb-1">
                <div className="p-2 bg-[#c8ff00] rounded-lg">
                  <Shield className="w-5 h-5 text-black" />
                </div>
                <h1 className="text-2xl font-bold tracking-tight text-white uppercase">
                  AIRAVAT<span className="text-[#c8ff00]">.</span>
                </h1>
              </div>
              <p className="text-sm text-white/50">
                Advanced Intelligence for Risk Analysis & Visibility
              </p>
            </div>

            <Card className="bg-white/5 border-white/10 shadow-2xl backdrop-blur-md">
              <CardContent className="p-6 pt-8 space-y-6">
                <form onSubmit={handleSubmit} className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="email" className="text-xs font-semibold uppercase tracking-wider text-white/70">Email address</Label>
                    <div className="relative group">
                      <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/30 group-focus-within:text-[#c8ff00] transition-colors" />
                      <Input
                        id="email"
                        type="email"
                        placeholder="you@airavat.in"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        required
                        autoComplete="email"
                        className="pl-10 bg-white/5 border-white/10 text-white placeholder:text-white/20 focus:border-[#c8ff00]/50 h-11"
                      />
                    </div>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="password" className="text-xs font-semibold uppercase tracking-wider text-white/70">Password</Label>
                    <div className="relative group">
                      <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/30 group-focus-within:text-[#c8ff00] transition-colors" />
                      <Input
                        id="password"
                        type={showPw ? "text" : "password"}
                        placeholder="••••••••"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        required
                        className="pl-10 pr-10 bg-white/5 border-white/10 text-white placeholder:text-white/20 focus:border-[#c8ff00]/50 h-11"
                      />
                      <button
                        type="button"
                        onClick={() => setShowPw((v) => !v)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-white/30 hover:text-white transition-colors"
                      >
                        {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
                      </button>
                    </div>
                  </div>

                  {error && (
                    <div className="p-3 bg-red-500/10 border border-red-500/20 text-red-500 text-xs rounded-lg animate-in fade-in slide-in-from-top-2">
                      {error}
                    </div>
                  )}

                  <Button
                    type="submit"
                    className="w-full bg-[#c8ff00] hover:bg-[#b0e000] text-black font-bold h-11 flex items-center justify-center gap-2 transition-all active:scale-[0.98]"
                    disabled={loading}
                  >
                    {loading ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <LogIn className="w-4 h-4" />
                    )}
                    Sign into Dashboard
                  </Button>
                </form>

                {/* Quick Demo Section */}
                <div className="pt-4 border-t border-white/10">
                  <p className="text-[10px] text-white/40 uppercase tracking-[0.2em] font-bold text-center mb-4">
                    Quick Demo Access
                  </p>
                  <div
                    ref={demoScrollRef}
                    className="grid grid-cols-1 gap-2 max-h-[220px] overflow-y-scroll overscroll-contain touch-pan-y pr-1 custom-scrollbar"
                    style={{ scrollbarGutter: "stable", WebkitOverflowScrolling: "touch" }}
                    onWheel={handleDemoWheel}
                  >
                    {demoUsers.length === 0 ? (
                       <div className="flex flex-col items-center justify-center p-8 border border-dashed border-white/10 rounded-xl space-y-2 text-white/30">
                          <Loader2 className="w-5 h-5 animate-spin" />
                          <span className="text-[10px] uppercase font-bold tracking-widest">Awaiting Backend...</span>
                       </div>
                    ) : (
                      demoUsers.map((u) => (
                        <button
                          key={u.id}
                          type="button"
                          onClick={() => quickLogin(u.email)}
                          className="flex items-center justify-between p-3 rounded-xl border border-white/5 bg-white/[0.02] hover:bg-[#c8ff00]/10 hover:border-[#c8ff00]/30 transition-all text-left group"
                        >
                          <div className="flex items-center gap-3">
                            <div className="p-2 bg-white/5 rounded-lg group-hover:bg-[#c8ff00]/20 transition-colors">
                              <User className="w-3.5 h-3.5 text-white/50 group-hover:text-[#c8ff00]" />
                            </div>
                            <div className="flex flex-col">
                              <span className="text-[13px] font-semibold text-white/90 group-hover:text-white">
                                {u.name}
                              </span>
                              <span className="text-[10px] text-white/30 truncate max-w-[140px]">
                                {u.email}
                              </span>
                            </div>
                          </div>
                          <div className="flex flex-col items-end gap-1">
                             <div className="text-[9px] px-2 py-0.5 rounded-full bg-[#c8ff00]/10 text-[#c8ff00] font-bold border border-[#c8ff00]/20 uppercase tracking-tighter">
                                {ROLE_LABELS[u.role] || u.role}
                             </div>
                          </div>
                        </button>
                      ))
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>

        {/* Right Side: Immersive Visuals */}
        <div className="relative hidden lg:flex items-center justify-center h-full bg-black">
          <video
            autoPlay
            loop
            muted
            playsInline
            preload="metadata"
            className="absolute inset-0 h-full w-full object-cover opacity-80"
          >
            <source src="/NeuroCred_financial_intelligence…_202604111328.mp4" type="video/mp4" />
          </video>
          
          <div className="absolute inset-0 bg-gradient-to-t from-black via-transparent to-black" />
          
          {/* Overlay Content */}
          <div className="relative z-20 p-12 text-white max-w-md">
            <div className="inline-flex items-center gap-2 px-3 py-1 bg-white/10 backdrop-blur-md rounded-full border border-white/10 mb-6">
              <Zap size={14} className="text-[#c8ff00]" />
              <span className="text-[10px] font-bold uppercase tracking-widest text-[#c8ff00]">Network Pulse active</span>
            </div>
            <h2 className="text-4xl font-bold leading-tight mb-4">
              Real-time Resilience for <span className="italic">Modern Finance</span>
            </h2>
            <p className="text-white/60 text-sm leading-relaxed mb-8">
              Airavat leverages high-fidelity digital twins and multi-agent systems to secure financial boundaries and automate risk discovery.
            </p>
            
            <div className="grid grid-cols-2 gap-4">
                <div className="p-4 bg-white/5 backdrop-blur-md border border-white/10 rounded-2xl">
                    <div className="text-[#c8ff00] font-bold text-lg mb-1">99.8%</div>
                    <div className="text-[10px] text-white/40 uppercase font-bold tracking-widest">Accuracy</div>
                </div>
                <div className="p-4 bg-white/5 backdrop-blur-md border border-white/10 rounded-2xl">
                    <div className="text-[#c8ff00] font-bold text-lg mb-1">~0.4s</div>
                    <div className="text-[10px] text-white/40 uppercase font-bold tracking-widest">Latency</div>
                </div>
            </div>
          </div>

          <div className="absolute bottom-8 right-8 z-20 flex gap-4">
               <div className="flex items-center gap-2 text-[10px] text-white/50 uppercase font-bold tracking-widest">
                  <Globe size={12} />
                  Tier 8 Compliant
               </div>
          </div>
        </div>
      </div>

      <style dangerouslySetInnerHTML={{ __html: `
        .custom-scrollbar::-webkit-scrollbar {
          width: 4px;
        }
        .custom-scrollbar::-webkit-scrollbar-track {
          background: transparent;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb {
          background: rgba(255, 255, 255, 0.1);
          border-radius: 10px;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover {
          background: rgba(200, 255, 0, 0.3);
        }
      `}} />
    </div>
  );
}
