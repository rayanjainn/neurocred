"use client";

import { useState, useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Mic, MicOff, X, Loader2, Send } from "lucide-react";
import { TwinEnergyAura } from "@/components/TwinEnergyAura";
import { cn } from "@/dib/utils";
import { useAuth } from "@/dib/authContext";

interface VoiceModalProps {
  isOpen: boolean;
  onClose: () => void;
  twinName: string;
  dataContext?: any;
}

export function VoiceModal({ isOpen, onClose, twinName, dataContext }: VoiceModalProps) {
  const { user } = useAuth();
  const [mounted, setMounted] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [response, setResponse] = useState("");
  const [chatInput, setChatInput] = useState("");
  const recognitionRef = useRef<any>(null);
  const synthesisRef = useRef<SpeechSynthesisUtterance | null>(null);
  const lastSpokenRef = useRef("");
  const manualProcessRef = useRef(false);
  const chatScrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setMounted(true);
    if (typeof window !== "undefined") {
      const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
      if (SpeechRecognition) {
        recognitionRef.current = new SpeechRecognition();
        recognitionRef.current.continuous = false;
        recognitionRef.current.interimResults = true;
        recognitionRef.current.lang = "en-IN";

        recognitionRef.current.onresult = (event: any) => {
          let currentTranscript = "";
          for (let i = event.resultIndex; i < event.results.length; ++i) {
            currentTranscript += event.results[i][0].transcript;
          }
          setTranscript(currentTranscript);
        };

        recognitionRef.current.onerror = (event: any) => {
          console.error("Speech recognition error", event.error);
          setIsListening(false);
        };

        recognitionRef.current.onend = () => {
          setIsListening(false);
        };
      }
    }

    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.stop();
      }
      window.speechSynthesis?.cancel();
    };
  }, []);

  // Process transcript once listening stops
  useEffect(() => {
    if (manualProcessRef.current) {
      manualProcessRef.current = false;
      return;
    }
    if (!isListening && transcript && !isProcessing && !isSpeaking && !response) {
      handleProcessing(transcript);
    }
  }, [isListening, transcript]);

  // Always speak latest model output when it arrives.
  useEffect(() => {
    const text = response.trim();
    if (!text) return;
    if (isProcessing || isListening) return;
    if (lastSpokenRef.current === text) return;
    lastSpokenRef.current = text;
    speakResponse(text);
  }, [response, isProcessing, isListening]);

  // Keep transcript panel pinned to newest message.
  useEffect(() => {
    const el = chatScrollRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [transcript, response, isProcessing]);

  const handleProcessing = async (text: string) => {
    setIsProcessing(true);
    setResponse("");

    try {
      const { twinApi } = await import("@/dib/api");
      const userId =
        dataContext?.user_id ||
        dataContext?.userId ||
        user?.id ||
        "";

      if (!userId) {
        throw new Error("No active user context found for twin chat.");
      }

      // Pull live backend context on every prompt so voice reasoning is dynamic.
      const [twinState, twinHistory, twinTriggers, twinReport] = await Promise.all([
        twinApi.get(userId).catch(() => null),
        twinApi.getHistory(userId).catch(() => []),
        twinApi.getTriggers(userId).catch(() => []),
        twinApi.getReport(userId).catch(() => null),
      ]);

      // Fetch fresh score snapshot when GSTIN is available.
      const gstin = dataContext?.gstin || user?.gstin || dataContext?.user_profile?.gstin;
      let latestScore: any = null;
      if (gstin) {
        try {
          const { scoreApi } = await import("@/dib/api");
          const submit: any = await scoreApi.submit(String(gstin));
          if (submit?.task_id) {
            for (let i = 0; i < 3; i += 1) {
              const snap: any = await scoreApi.get(submit.task_id).catch(() => null);
              if (snap?.status === "complete") {
                latestScore = snap;
                break;
              }
              await new Promise((resolve) => setTimeout(resolve, 800));
            }
          }
        } catch {
          // Best-effort enrichment; fallback to available local context below.
        }
      }

      const dynamicContext = {
        ...(dataContext || {}),
        user_profile: {
          id: user?.id,
          name: user?.name,
          role: user?.role,
          gstin: user?.gstin,
        },
        twin_state: twinState,
        twin_history: Array.isArray(twinHistory) ? twinHistory.slice(0, 6) : twinHistory,
        twin_triggers: Array.isArray(twinTriggers) ? twinTriggers.slice(0, 6) : twinTriggers,
        twin_report: twinReport,
        latest_score: latestScore || {
          credit_score: dataContext?.credit_score,
          risk_band: dataContext?.risk_band,
          recommended_wc_amount: dataContext?.recommended_wc_amount,
          recommended_term_amount: dataContext?.recommended_term_amount,
          data_maturity_months: dataContext?.data_maturity_months,
          top_reasons: dataContext?.top_reasons,
        },
      };

      const res = await fetch("/api/twin-chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          userId,
          dataContext: dynamicContext,
        }),
      });

      const data: any = await res.json();

      setIsProcessing(false);

      const generatedResponse = data.reply || data.content || data.error || "Sorry, I am facing an issue right now connecting to the twin service.";
      setResponse(generatedResponse);

    } catch (err) {
      console.error(err);
      setIsProcessing(false);
      setResponse("An unexpected network error occurred.");
    }
  };

  const speakResponse = (text: string) => {
    if (!window.speechSynthesis) return;

    setIsSpeaking(true);
    window.speechSynthesis.cancel(); // Cancel any ongoing speech

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "en-IN";
    utterance.rate = 1.0;
    utterance.pitch = 1.0;

    utterance.onend = () => {
      setIsSpeaking(false);
    };
    utterance.onerror = () => {
      setIsSpeaking(false);
    };

    synthesisRef.current = utterance;
    window.speechSynthesis.speak(utterance);
  };

  const toggleListening = () => {
    if (isListening) {
      recognitionRef.current?.stop();
      setIsListening(false);
    } else {
      setTranscript("");
      setResponse("");
      window.speechSynthesis?.cancel();
      setIsSpeaking(false);
      try {
        recognitionRef.current?.start();
        setIsListening(true);
      } catch (e) {
        console.error(e);
      }
    }
  };

  const submitTypedChat = async () => {
    const text = chatInput.trim();
    if (!text || isProcessing) return;
    manualProcessRef.current = true;
    if (isListening) {
      recognitionRef.current?.stop();
      setIsListening(false);
    }
    setTranscript(text);
    setChatInput("");
    await handleProcessing(text);
  };

  const handleClose = () => {
    if (recognitionRef.current) recognitionRef.current.stop();
    window.speechSynthesis?.cancel();
    setIsListening(false);
    setIsProcessing(false);
    setIsSpeaking(false);
    setTranscript("");
    setResponse("");
    lastSpokenRef.current = "";
    onClose();
  };

  let statusText = "Ready to talk";
  if (isListening) statusText = "Listening...";
  else if (isProcessing) statusText = "Analyzing...";
  else if (isSpeaking) statusText = "Speaking...";

  if (!mounted) return null;

  return createPortal(
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-[9999] flex items-center justify-center p-4 sm:p-6" style={{ position: 'fixed' }}>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={handleClose}
          />

          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            className="relative w-full max-w-md overflow-hidden rounded-2xl border border-lime-500/30 bg-[#0d120e] shadow-2xl shadow-lime-900/20 flex flex-col"
          >
            {/* Header */}
            <div className="flex items-center justify-between border-b border-white/10 p-4">
              <div className="flex flex-col">
                <div className="flex items-center gap-2">
                  <div className={cn("h-2 w-2 rounded-full", isSpeaking || isListening ? "animate-pulse bg-lime-400" : "bg-white/30")} />
                  <span className="text-sm font-semibold tracking-wide text-foreground">
                    Digital Twin: {twinName}
                  </span>
                </div>
              </div>
              <button
                onClick={handleClose}
                className="rounded-full p-1.5 text-muted-foreground hover:bg-white/10 hover:text-foreground transition-colors"
                title="Close"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* Body */}
            <div className="p-6 flex flex-col items-center gap-6">

              {/* Avatar Aura container */}
              <div className="relative flex justify-center py-2 h-32 items-center">
                <TwinEnergyAura
                  avatarLabel={twinName.charAt(0)}
                  className={cn(
                    "transition-all duration-500 ease-out",
                    isSpeaking ? "scale-[1.15] ring-lime-400/80 shadow-[0_0_50px_rgba(163,230,53,0.5)]" : "ring-lime-400/40",
                    isListening ? "scale-105 ring-lime-400" : ""
                  )}
                />
              </div>

              {/* Status Text Indicator */}
              <div className="text-center relative h-6 w-full">
                <AnimatePresence mode="wait">
                  <motion.p
                    key={statusText}
                    initial={{ opacity: 0, y: 5 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -5 }}
                    className={cn(
                      "text-sm font-medium absolute inset-x-0",
                      isListening ? "text-lime-400 animate-pulse" :
                        isProcessing ? "text-amber-400" :
                          isSpeaking ? "text-lime-300" : "text-muted-foreground"
                    )}
                  >
                    {statusText}
                  </motion.p>
                </AnimatePresence>
              </div>

              {/* Chat / Transcript Area */}
              <div
                ref={chatScrollRef}
                className="w-full flex flex-col gap-3 h-[180px] overflow-y-scroll overscroll-contain touch-pan-y pr-2 [scrollbar-gutter:stable] [&::-webkit-scrollbar]:w-2 [&::-webkit-scrollbar-track]:bg-transparent [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-white/25 hover:[&::-webkit-scrollbar-thumb]:bg-white/40"
                style={{ scrollbarWidth: "thin", scrollbarColor: "rgba(255,255,255,0.35) transparent", WebkitOverflowScrolling: "touch" }}
              >
                <AnimatePresence>
                  {transcript && (
                    <motion.div
                      key="transcript"
                      initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }}
                      className="self-end max-w-[85%] rounded-2xl rounded-tr-sm bg-lime-900/40 border border-lime-800/50 p-3 text-sm text-lime-50"
                    >
                      {transcript}
                    </motion.div>
                  )}
                  {isProcessing && !response && (
                    <motion.div
                      key="processing"
                      initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }}
                      className="self-start max-w-[85%] rounded-2xl rounded-tl-sm bg-white/5 border border-white/10 p-3 text-sm text-muted-foreground flex items-center gap-2"
                    >
                      <Loader2 className="h-4 w-4 animate-spin text-lime-500" /> Thinking...
                    </motion.div>
                  )}
                  {response && (
                    <motion.div
                      key="response"
                      initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }}
                      className="self-start max-w-[85%] rounded-2xl rounded-tl-sm bg-[#151a16] border border-lime-900/40 p-3 text-sm text-foreground shadow-lg"
                    >
                      {response}
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </div>

            {/* Footer / Mic Button */}
            <div className="mt-auto border-t border-white/5 bg-black/20 p-4 space-y-3">
              <div className="flex items-center gap-2">
                <input
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      void submitTypedChat();
                    }
                  }}
                  placeholder="Type to chat with your twin..."
                  className="h-10 flex-1 rounded-lg border border-white/10 bg-white/5 px-3 text-sm text-white outline-none focus:border-lime-400/60"
                  disabled={isProcessing}
                />
                <button
                  type="button"
                  onClick={() => void submitTypedChat()}
                  disabled={isProcessing || !chatInput.trim()}
                  className="inline-flex h-10 w-10 items-center justify-center rounded-lg border border-lime-500/50 bg-lime-500/20 text-lime-300 hover:bg-lime-500/30 disabled:opacity-50"
                  title="Send message"
                >
                  <Send className="h-4 w-4" />
                </button>
              </div>

              <div className="flex justify-center">
                <button
                  onClick={toggleListening}
                  className={cn(
                    "relative flex h-14 w-14 items-center justify-center rounded-full border transition-all duration-300 transform",
                    isListening
                      ? "border-red-500 bg-red-500/20 text-red-400 shadow-[0_0_30px_rgba(239,68,68,0.4)] scale-95"
                      : "border-lime-500 bg-lime-500/20 text-lime-400 hover:bg-lime-500/30 hover:scale-105 shadow-[0_0_15px_rgba(163,230,53,0.15)]"
                  )}
                  title={isListening ? "Stop Listening" : "Start Listening"}
                >
                  {isListening ? <MicOff className="h-6 w-6" /> : <Mic className="h-6 w-6" />}
                </button>
              </div>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>,
    document.body
  );
}
