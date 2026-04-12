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

interface ChatMessage {
  role: "user" | "assistant";
  text: string;
}

const SESSION_PRELOAD_LIMIT = 16;

function twinChatSessionKey(userId: string) {
  return `twin.chat.session.${userId}`;
}

export function VoiceModal({ isOpen, onClose, twinName, dataContext }: VoiceModalProps) {
  const { user } = useAuth();
  const [mounted, setMounted] = useState(false);
  const [speechSupported, setSpeechSupported] = useState(false);
  const [speechError, setSpeechError] = useState("");
  const [isListening, setIsListening] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [response, setResponse] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [profileImageSeed, setProfileImageSeed] = useState<string | null>(null);
  const [chatSessionId, setChatSessionId] = useState("");
  const [isLoadingSession, setIsLoadingSession] = useState(false);
  const recognitionRef = useRef<any>(null);
  const synthesisRef = useRef<SpeechSynthesisUtterance | null>(null);
  const transcriptRef = useRef("");
  const shouldSubmitOnEndRef = useRef(false);
  const lastSpokenRef = useRef("");
  const chatScrollRef = useRef<HTMLDivElement | null>(null);

  const startListeningSafely = () => {
    if (typeof window === "undefined") return;
    const recognition = recognitionRef.current;
    if (!recognition) {
      setSpeechSupported(false);
      setSpeechError("Speech recognition is not available in this browser. Please use typed chat.");
      return;
    }

    try {
      transcriptRef.current = "";
      setTranscript("");
      setSpeechError("");
      shouldSubmitOnEndRef.current = false;
      recognition.start();
      setIsListening(true);
    } catch {
      setIsListening(false);
      setSpeechError("Unable to start microphone. Please allow permission and retry.");
    }
  };

  useEffect(() => {
    setMounted(true);
    if (typeof window !== "undefined") {
      const SpeechRecognitionCtor =
        (window as any).webkitSpeechRecognition || (window as any).SpeechRecognition;

      if (!SpeechRecognitionCtor) {
        setSpeechSupported(false);
        setSpeechError("Speech recognition is not available in this browser. Please use typed chat.");
      } else {
        const recognition = new SpeechRecognitionCtor();
        recognition.continuous = true;
        recognition.interimResults = true;
        recognition.lang = "en-IN";

        recognition.onresult = (event: any) => {
          let currentTranscript = "";
          for (let i = 0; i < event.results.length; i += 1) {
            currentTranscript += String(event.results[i][0]?.transcript || "");
          }
          const liveText = currentTranscript.trim();
          transcriptRef.current = liveText;
          setTranscript(liveText);
        };

        recognition.onerror = (event: any) => {
          const code = String(event?.error || "unknown");
          setIsListening(false);
          shouldSubmitOnEndRef.current = false;

          if (code === "not-allowed" || code === "service-not-allowed") {
            setSpeechError("Microphone permission denied. Please enable it in browser settings.");
            return;
          }

          if (code === "network") {
            setSpeechError("Speech recognition network issue. Check internet and retry.");
            return;
          }

          if (code === "no-speech") {
            setSpeechError("No speech detected. Please speak a little louder and retry.");
            return;
          }

          setSpeechError(`Voice input error: ${code}`);
        };

        recognition.onend = () => {
          setIsListening(false);

          const shouldSubmit = shouldSubmitOnEndRef.current;
          shouldSubmitOnEndRef.current = false;
          const finalText = transcriptRef.current.trim();

          if (!shouldSubmit) {
            // SpeechRecognition can stop on pauses/network; process captured text if present.
            if (finalText && !isProcessing) {
              setTranscript("");
              transcriptRef.current = "";
              void handleProcessing(finalText);
            }
            return;
          }

          if (!finalText) {
            setSpeechError("No speech captured. Please try again.");
            return;
          }

          setTranscript("");
          transcriptRef.current = "";
          void handleProcessing(finalText);
        };

        recognitionRef.current = recognition;
        setSpeechSupported(true);
      }
    }

    const loadProfileImage = () => {
      setProfileImageSeed(window.localStorage.getItem("profileImageSeed"));
    };
    loadProfileImage();
    window.addEventListener("profileImageUpdated", loadProfileImage);

    return () => {
      if (recognitionRef.current) {
        try {
          recognitionRef.current.stop();
        } catch {
          // Ignore stop failures during unmount.
        }
      }
      window.speechSynthesis?.cancel();
      window.removeEventListener("profileImageUpdated", loadProfileImage);
    };
  }, [user?.id]);

  useEffect(() => {
    if (!isOpen || typeof window === "undefined") return;

    let cancelled = false;

    const userId = String(
      dataContext?.user_id || dataContext?.userId || user?.id || "",
    ).trim();

    if (!userId) {
      setChatSessionId("");
      setMessages([]);
      return;
    }

    const existing = window.localStorage.getItem(twinChatSessionKey(userId));
    const sessionId = String(existing || "").trim();
    setChatSessionId(sessionId);

    if (!sessionId) {
      setMessages([]);
      return;
    }

    setIsLoadingSession(true);
    void (async () => {
      try {
        const { twinApi } = await import("@/dib/api");
        const sessionData: any = await twinApi.getChatSession(userId, sessionId, SESSION_PRELOAD_LIMIT);
        if (cancelled) return;

        const restoredMessages = (Array.isArray(sessionData?.messages) ? sessionData.messages : [])
          .map((item: any) => {
            const rawRole = String(item?.role || "").toLowerCase();
            const role: "user" | "assistant" =
              rawRole === "assistant" || rawRole === "twin" ? "assistant" : "user";
            const text = String(item?.content || item?.text || "").trim();
            if (!text) return null;
            return { role, text };
          })
          .filter(Boolean) as ChatMessage[];

        setMessages(restoredMessages);
      } catch {
        if (!cancelled) {
          setMessages([]);
        }
      } finally {
        if (!cancelled) {
          setIsLoadingSession(false);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [
    isOpen,
    dataContext?.user_id,
    dataContext?.userId,
    user?.id,
  ]);

  useEffect(() => {
    transcriptRef.current = transcript;
  }, [transcript]);

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
  }, [messages, transcript, response, isProcessing]);

  const handleProcessing = async (text: string) => {
    const cleanedText = text.trim();
    if (!cleanedText) return;

    const recentMemory = [
      ...messages.slice(-8),
      { role: "user" as const, text: cleanedText },
    ];

    setMessages((prev) => [...prev, { role: "user", text: cleanedText }]);
    setIsProcessing(true);
    setResponse("");

    try {
      const userId =
        dataContext?.user_id ||
        dataContext?.userId ||
        user?.id ||
        "";

      let data: any;

      if (userId) {
        try {
          const { twinApi } = await import("@/dib/api");
          data = await twinApi.chat(userId, {
            message: cleanedText,
            chat_session_id: chatSessionId || undefined,
            data_context: dataContext || {},
          });

          const nextSessionId = String(data?.chat_session_id || "").trim();
          if (nextSessionId && typeof window !== "undefined") {
            setChatSessionId(nextSessionId);
            window.localStorage.setItem(twinChatSessionKey(userId), nextSessionId);
          }
        } catch {
          // Fall back to frontend route when backend chat endpoint is unavailable.
        }
      }

      if (!data) {
        const res = await fetch("/api/twin-chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            message: cleanedText,
            userId,
            dataContext,
            chatSessionId: chatSessionId || undefined,
            conversationHistory: recentMemory,
          }),
        });
        data = await res.json().catch(() => ({}));
      }

      setIsProcessing(false);

      const generatedResponse = data.reply || data.content || data.error || "Sorry, I am facing an issue right now connecting to the twin service.";
      setResponse(generatedResponse);
      setMessages((prev) => [...prev, { role: "assistant", text: generatedResponse }]);

    } catch (err) {
      console.error(err);
      setIsProcessing(false);
      const fallback = "An unexpected network error occurred.";
      setResponse(fallback);
      setMessages((prev) => [...prev, { role: "assistant", text: fallback }]);
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
    if (!speechSupported) {
      setSpeechError("Speech recognition is not available. Please use typed chat.");
      return;
    }

    if (isListening) {
      shouldSubmitOnEndRef.current = true;
      if (recognitionRef.current) {
        try {
          recognitionRef.current.stop();
        } catch {
          shouldSubmitOnEndRef.current = false;
          setSpeechError("Unable to stop voice capture cleanly. Please retry.");
        }
      }
      setIsListening(false);
    } else {
      setSpeechError("");
      setTranscript("");
      setResponse("");
      window.speechSynthesis?.cancel();
      setIsSpeaking(false);
      startListeningSafely();
    }
  };

  const submitTypedChat = async () => {
    const text = chatInput.trim();
    if (!text || isProcessing) return;
    if (isListening) {
      shouldSubmitOnEndRef.current = false;
      if (recognitionRef.current) {
        try {
          recognitionRef.current.stop();
        } catch {
          // Ignore stop errors when switching input mode.
        }
      }
      setIsListening(false);
    }
    setTranscript("");
    transcriptRef.current = "";
    setChatInput("");
    await handleProcessing(text);
  };

  const handleClose = () => {
    shouldSubmitOnEndRef.current = false;
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch {
        // Ignore stop failures while closing.
      }
    }
    window.speechSynthesis?.cancel();
    setIsListening(false);
    setIsProcessing(false);
    setIsSpeaking(false);
    setTranscript("");
    transcriptRef.current = "";
    setResponse("");
    setMessages([]);
    setChatSessionId("");
    setSpeechError("");
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
                  avatarSeed={profileImageSeed}
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

              {speechError && (
                <div className="-mt-2 w-full rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-300">
                  <p>{speechError}</p>
                  {speechSupported && !isListening && (
                    <button
                      type="button"
                      onClick={() => {
                        setSpeechError("");
                        setTranscript("");
                        setResponse("");
                        startListeningSafely();
                      }}
                      className="mt-2 rounded border border-amber-300/40 px-2 py-1 text-[11px] font-medium text-amber-200 hover:bg-amber-300/10"
                    >
                      Retry microphone
                    </button>
                  )}
                </div>
              )}

              {/* Chat / Transcript Area */}
              <div
                ref={chatScrollRef}
                className="w-full flex flex-col gap-3 h-[180px] overflow-y-scroll overscroll-contain touch-pan-y pr-2 [scrollbar-gutter:stable] [&::-webkit-scrollbar]:w-2 [&::-webkit-scrollbar-track]:bg-transparent [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-white/25 hover:[&::-webkit-scrollbar-thumb]:bg-white/40"
                style={{ scrollbarWidth: "thin", scrollbarColor: "rgba(255,255,255,0.35) transparent", WebkitOverflowScrolling: "touch" }}
              >
                <AnimatePresence>
                  {isLoadingSession && messages.length === 0 && (
                    <motion.div
                      key="loading-session"
                      initial={{ opacity: 0, x: -20 }}
                      animate={{ opacity: 1, x: 0 }}
                      exit={{ opacity: 0 }}
                      className="self-start max-w-[85%] rounded-2xl rounded-tl-sm bg-white/5 border border-white/10 p-3 text-sm text-muted-foreground flex items-center gap-2"
                    >
                      <Loader2 className="h-4 w-4 animate-spin text-lime-500" /> Loading previous conversation...
                    </motion.div>
                  )}

                  {messages.map((msg, idx) => (
                    <motion.div
                      key={`${msg.role}-${idx}`}
                      initial={{ opacity: 0, x: msg.role === "user" ? 20 : -20 }}
                      animate={{ opacity: 1, x: 0 }}
                      className={cn(
                        "max-w-[85%] rounded-2xl p-3 text-sm",
                        msg.role === "user"
                          ? "self-end rounded-tr-sm bg-lime-900/40 border border-lime-800/50 text-lime-50"
                          : "self-start rounded-tl-sm bg-[#151a16] border border-lime-900/40 text-foreground shadow-lg"
                      )}
                    >
                      {msg.text}
                    </motion.div>
                  ))}

                  {transcript && (
                    <motion.div
                      key="interim-transcript"
                      initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }}
                      className="self-end max-w-[85%] rounded-2xl rounded-tr-sm border border-lime-700/40 bg-lime-900/20 p-3 text-sm italic text-lime-100"
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
                  disabled={!speechSupported}
                  className={cn(
                    "relative flex h-14 w-14 items-center justify-center rounded-full border transition-all duration-300 transform",
                    isListening
                      ? "border-red-500 bg-red-500/20 text-red-400 shadow-[0_0_30px_rgba(239,68,68,0.4)] scale-95"
                      : "border-lime-500 bg-lime-500/20 text-lime-400 hover:bg-lime-500/30 hover:scale-105 shadow-[0_0_15px_rgba(163,230,53,0.15)]",
                    !speechSupported && "cursor-not-allowed opacity-45"
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
