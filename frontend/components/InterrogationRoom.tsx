"use client";

import { useState, useEffect, useRef } from "react";
import { reasoningApi } from "@/dib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { AlertCircle, FileText, Send, CheckCircle2, Bot } from "lucide-react";
import { Progress } from "@/components/ui/progress";

interface InterrogationRoomProps {
  sessionId: string;
  onComplete: () => void;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function InterrogationRoom({ sessionId, onComplete, open, onOpenChange }: InterrogationRoomProps) {
  const [loading, setLoading] = useState(true);
  const [answering, setAnswering] = useState(false);
  const [sessionData, setSessionData] = useState<any>(null);
  const [answer, setAnswer] = useState("");
  const [history, setHistory] = useState<{q: string, a: string}[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (open && sessionId) {
      setLoading(true);
      reasoningApi.startInterrogation(sessionId)
        .then(res => {
          setSessionData(res);
          // if res.completed is true, we could close immediately or show success.
        })
        .catch(console.error)
        .finally(() => setLoading(false));
    }
  }, [open, sessionId]);

  const handleSubmit = async () => {
    if (!answer.trim()) return;
    setAnswering(true);
    
    // Optimistic UI
    const currentQ = sessionData.next_question;
    const currentA = answer;
    setHistory(prev => [...prev, { q: currentQ, a: currentA }]);
    setAnswer("");

    try {
      const resp = await reasoningApi.answerInterrogation(sessionId, currentA);
      setSessionData(resp);
      if (resp.completed) {
        setTimeout(() => {
          onComplete();
          onOpenChange(false);
        }, 3000);
      }
    } catch (e) {
      console.error(e);
      // Revert optimistic
      setHistory(prev => prev.slice(0, -1));
      setAnswer(currentA);
    } finally {
      setAnswering(false);
      setTimeout(() => {
        if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
      }, 100);
    }
  };

  if (!open) return null;

  const isComplete = sessionData?.completed;
  const progress = sessionData ? ((sessionData.current_question_index) / sessionData.total_questions) * 100 : 0;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl p-0 overflow-hidden border-border/50 bg-[#0c0c0e] text-slate-200">
        <DialogHeader className="p-4 border-b border-white/5 bg-white/[0.02]">
          <DialogTitle className="flex items-center gap-2 text-sm font-semibold">
            {isComplete ? <CheckCircle2 className="w-5 h-5 text-emerald-500" /> : <AlertCircle className="w-5 h-5 text-primary" />}
            Resolving Ambiguity Signals (Interrogation Mode)
          </DialogTitle>
          <div className="w-full mt-2 space-y-1">
             <div className="flex justify-between text-[10px] text-muted-foreground font-mono">
               <span>P-Q{sessionData?.current_question_index || 1}/{sessionData?.total_questions || 5}</span>
               <span>{Math.round(progress)}% CONFIDENCE</span>
             </div>
             <Progress value={progress} className="h-1 bg-white/5" indicatorClassName="bg-primary" />
          </div>
        </DialogHeader>

        <div 
          ref={scrollRef}
          className="p-4 max-h-[60vh] min-h-[40vh] overflow-y-auto space-y-6 bg-gradient-to-b from-transparent to-black/20"
        >
          {loading ? (
             <div className="flex flex-col items-center justify-center py-10 opacity-50 space-y-3 font-mono text-[10px] uppercase">
                <div className="w-6 h-6 border-[1.5px] border-primary border-t-transparent rounded-full animate-spin" />
                <p>Initializing Session Context...</p>
             </div>
          ) : (
             <>
               {history.map((h, i) => (
                 <div key={i} className="space-y-4">
                   <div className="flex gap-3">
                     <div className="w-6 h-6 rounded-full bg-primary/20 flex items-center justify-center shrink-0">
                       <Bot className="w-3.5 h-3.5 text-primary" />
                     </div>
                     <div className="bg-white/5 rounded-xl rounded-tl-none p-3 text-sm flex-1 leading-relaxed border border-white/5">
                        {h.q}
                     </div>
                   </div>
                   <div className="flex gap-3 justify-end">
                     <div className="bg-primary/10 text-primary-foreground rounded-xl rounded-tr-none p-3 text-sm flex-1 max-w-[80%] leading-relaxed border border-primary/20 bg-primary/20">
                        {h.a}
                     </div>
                   </div>
                 </div>
               ))}

               {!isComplete && sessionData?.next_question && (
                 <div className="flex gap-3 animate-in fade-in slide-in-from-bottom-2">
                   <div className="w-6 h-6 rounded-full bg-primary/20 flex items-center justify-center shrink-0 shadow-[0_0_15px_rgba(var(--primary),0.3)]">
                     <Bot className="w-3.5 h-3.5 text-primary" />
                   </div>
                   <div className="bg-white/5 backdrop-blur-md rounded-xl rounded-tl-none p-3 text-sm flex-1 leading-relaxed border border-white/10 shadow-lg">
                      {sessionData.next_question}
                   </div>
                 </div>
               )}

               {isComplete && (
                 <div className="flex flex-col items-center justify-center py-6 text-center space-y-3 animate-in fade-in zoom-in-95">
                   <div className="w-12 h-12 rounded-full bg-emerald-500/20 flex items-center justify-center">
                     <CheckCircle2 className="w-6 h-6 text-emerald-400" />
                   </div>
                   <div>
                     <p className="font-semibold text-emerald-400">Ambiguity Resolved</p>
                     <p className="text-xs text-muted-foreground mt-1">
                       Twin baseline updated. Re-computing statistical limits.
                     </p>
                   </div>
                 </div>
               )}
             </>
          )}
        </div>

        {!isComplete && (
          <div className="p-4 border-t border-white/5 bg-white/[0.01]">
            <form 
              onSubmit={e => { e.preventDefault(); handleSubmit(); }}
              className="flex items-center gap-2"
            >
              <Input 
                className="flex-1 bg-black/40 border-white/10 focus-visible:ring-primary/50" 
                placeholder="Type your explanation here..."
                value={answer}
                onChange={e => setAnswer(e.target.value)}
                disabled={answering || loading}
                autoFocus
              />
              <Button type="submit" disabled={!answer.trim() || answering || loading} className="shrink-0 bg-primary/90 hover:bg-primary">
                {answering ? <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : <Send className="w-4 h-4" />}
              </Button>
            </form>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
