"use client";

import { useState } from "react";
import { useAuth } from "@/dib/authContext";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { vigilanceApi } from "@/dib/api";
import { ShieldAlert, CheckCircle2, ShieldQuestion, AlertTriangle, Fingerprint, Loader2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";

export function ScamAnalyzerCard() {
  const { user } = useAuth();
  const [text, setText] = useState("");
  const [senderId, setSenderId] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const handleAnalyze = async () => {
    if (!text.trim()) return;
    setLoading(true);
    setResult(null);
    setError(null);

    try {
      const resp = await vigilanceApi.analyzeScam({
        user_id: user?.id || "anonymous",
        text,
        sender_id: senderId || undefined
      });
      setResult(resp);
    } catch (e: any) {
      setError(e.message ?? "Analysis failed");
    } finally {
      setLoading(false);
    }
  };

  const scamProb = result?.scam_probability ?? 0;
  
  return (
    <Card className="h-full border-border/50 glass overflow-hidden flex flex-col">
      <CardHeader className="py-3 px-4 border-b border-white/5 bg-white/[0.02]">
        <CardTitle className="text-sm font-semibold flex items-center gap-2">
          <Fingerprint className="w-4 h-4 text-primary" />
          Social Engineering Defence (Scam Analyzer)
        </CardTitle>
        <CardDescription className="text-xs">
          Instantly scan SMS or Voice transcripts for authority impersonation and urgency manipulation.
        </CardDescription>
      </CardHeader>
      <CardContent className="p-4 flex flex-col gap-4">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <div className="md:col-span-1">
             <Input 
               placeholder="Sender ID (e.g. TM-HDFCBK)" 
               className="text-xs"
               value={senderId}
               onChange={e => setSenderId(e.target.value)}
             />
          </div>
          <div className="md:col-span-3 flex gap-2">
            <Textarea 
              placeholder="Paste suspicious SMS or voice transcript here..." 
              className="min-h-[40px] resize-none text-xs"
              value={text}
              onChange={e => setText(e.target.value)}
            />
            <Button 
               size="sm" 
               className="h-full px-4" 
               onClick={handleAnalyze} 
               disabled={loading || !text.trim()}
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : "Scan"}
            </Button>
          </div>
        </div>

        {/* Demo buttons */}
        {!result && !loading && (
          <div className="flex gap-2 flex-wrap pb-2 pt-1 border-b border-border/50">
            <span className="text-xs text-muted-foreground mr-1 self-center">Try:</span>
            <Button variant="outline" size="sm" className="h-6 text-[10px]" onClick={() => {
              setSenderId("VK-ITDEPT");
              setText("URGENT: Income Tax Department requires immediate verification of your filing. Click here to avoid 50,000 INR penalty.");
            }}>IT Dept Scam</Button>
            <Button variant="outline" size="sm" className="h-6 text-[10px]" onClick={() => {
              setSenderId("VK-ZOMATO");
              setText("Your order 4598 has been delayed. Click to track.");
            }}>Clean SMS</Button>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-md text-red-500 text-xs flex items-center gap-2">
            <AlertTriangle className="w-4 h-4" /> {error}
          </div>
        )}

        {/* Results */}
        {result && (
          <div className="bg-black/20 p-4 rounded-xl border border-white/5 space-y-4 animate-in fade-in zoom-in-95">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className={`p-2 rounded-lg ${scamProb > 0.6 ? "bg-red-500/20 text-red-400" : scamProb > 0.2 ? "bg-amber-500/20 text-amber-400" : "bg-teal-500/20 text-teal-400"}`}>
                  {scamProb > 0.6 ? <ShieldAlert className="w-6 h-6" /> : scamProb > 0.2 ? <ShieldQuestion className="w-6 h-6" /> : <CheckCircle2 className="w-6 h-6" />}
                </div>
                <div>
                  <p className="text-sm font-bold">
                    {scamProb > 0.6 ? "High Risk Active Scam Detected" : scamProb > 0.2 ? "Suspicious Content" : "Looks Safe"}
                  </p>
                  <p className="text-xs text-muted-foreground uppercase tracking-wider font-mono mt-0.5">Scam Probability Score</p>
                </div>
              </div>
              <div className={`text-2xl font-bold font-mono tracking-tighter ${scamProb > 0.6 ? "text-red-400" : scamProb > 0.2 ? "text-amber-400" : "text-teal-400"}`}>
                {(scamProb * 100).toFixed(1)}%
              </div>
            </div>

            {/* Attack Vectors */}
            {result.manipulation_vectors && result.manipulation_vectors.length > 0 && (
               <div className="space-y-2 mt-4 pt-4 border-t border-white/10">
                 <p className="text-[10px] uppercase font-bold text-muted-foreground tracking-widest">Identified Attack Vectors</p>
                 <div className="flex flex-col gap-2">
                    {result.manipulation_vectors.map((vec: string, idx: number) => {
                      const tokens = vec.split(":");
                      return (
                        <div key={idx} className="flex flex-col p-2 bg-red-500/5 border border-red-500/10 rounded">
                           <span className="text-xs font-semibold text-red-400">{tokens[0]}</span>
                           {tokens.length > 1 && <span className="text-[11px] text-muted-foreground mt-1">{tokens.slice(1).join(":")}</span>}
                        </div>
                      )
                    })}
                 </div>
               </div>
            )}
            
            {/* Safe Signals */}
            {scamProb <= 0.2 && scamProb >= 0 && (
              <div className="mt-4 pt-4 border-t border-white/10">
                 <p className="text-[10px] uppercase font-bold text-muted-foreground tracking-widest">Analysis Matrix</p>
                 <div className="mt-2 grid grid-cols-2 gap-2">
                   <div className="bg-white/5 p-2 rounded text-xs border border-white/5 flex flex-col">
                     <span className="text-teal-400 font-semibold mb-1">Sentiment</span>
                     <span className="opacity-80">Neutral/Transactional</span>
                   </div>
                   <div className="bg-white/5 p-2 rounded text-xs border border-white/5 flex flex-col">
                     <span className="text-teal-400 font-semibold mb-1">Entity Check</span>
                     <span className="opacity-80">No manipulation</span>
                   </div>
                 </div>
              </div>
            )}

            <div className="pt-2 text-right">
              <Badge variant="outline" className={`font-mono text-[9px] px-2 py-0.5 ${result.risk_level === 'CRITICAL' ? 'border-red-500/50 text-red-500' : 'border-white/20'}`}>
                {result.risk_level} LEVEL
              </Badge>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
