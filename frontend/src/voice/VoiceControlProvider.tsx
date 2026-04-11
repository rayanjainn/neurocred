"use client";

import {
  createContext,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { usePathname, useRouter } from "next/navigation";
import { useTheme } from "next-themes";
import { parseCommand, type ParsedCommand } from "@/src/voice/commandParser";
import { useAuth } from "@/dib/authContext";

type VoiceControlContextValue = {
  isListening: boolean;
  transcript: string;
  feedback: string;
  isSupported: boolean;
  startListening: () => void;
  stopListening: () => void;
  toggleListening: () => void;
  handleCommand: (text: string) => void;
};

type SpeechRecognitionLike = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  maxAlternatives: number;
  start: () => void;
  stop: () => void;
  onresult: ((event: any) => void) | null;
  onerror: ((event: any) => void) | null;
  onend: (() => void) | null;
};

export const VoiceControlContext = createContext<VoiceControlContextValue | null>(null);
const VOICE_PENDING_ACTION_KEY = "voice.pendingAction";

const NAV_TARGETS: Record<string, Record<string, string>> = {
  dashboard: {
    msme: "/msme/dashboard",
    loan_officer: "/bank/loan-queue",
    credit_analyst: "/analyst/data-explorer",
    risk_manager: "/risk/fraud-queue",
    admin: "/admin/overview",
  },
  reports: {
    msme: "/msme/score-report",
    loan_officer: "/bank/decisions",
    credit_analyst: "/analyst/shap-explorer",
    risk_manager: "/risk/thresholds",
    admin: "/admin/audit-log",
  },
  analytics: {
    msme: "/msme/strategy-lab",
    loan_officer: "/bank/strategy-lab",
    credit_analyst: "/analyst/signal-trends",
    risk_manager: "/risk/fraud-topology",
    admin: "/admin/overview",
  },
  alerts: {
    msme: "/msme/disputes",
    loan_officer: "/bank/loan-queue",
    credit_analyst: "/analyst/dispute-queue",
    risk_manager: "/risk/fraud-queue",
    admin: "/admin/audit-log",
  },
  risk: {
    msme: "/msme/score-report",
    loan_officer: "/bank/decisions",
    credit_analyst: "/analyst/shap-explorer",
    risk_manager: "/risk/fraud-queue",
    admin: "/admin/overview",
  },
  loans: {
    msme: "/msme/loans",
    loan_officer: "/bank/loan-queue",
    credit_analyst: "/analyst/dispute-queue",
    risk_manager: "/risk/fraud-queue",
    admin: "/admin/overview",
  },
  reminders: {
    msme: "/msme/reminders",
    loan_officer: "/bank/loan-queue",
    credit_analyst: "/analyst/data-explorer",
    risk_manager: "/risk/thresholds",
    admin: "/admin/audit-log",
  },
  guide: {
    msme: "/msme/guide",
    loan_officer: "/bank/strategy-lab",
    credit_analyst: "/analyst/strategy-lab",
    risk_manager: "/risk/strategy-lab",
    admin: "/admin/overview",
  },
  shap_explorer: {
    msme: "/msme/score-report",
    loan_officer: "/bank/decisions",
    credit_analyst: "/analyst/shap-explorer",
    risk_manager: "/risk/thresholds",
    admin: "/admin/audit-log",
  },
  data_explorer: {
    msme: "/msme/dashboard",
    loan_officer: "/bank/decisions",
    credit_analyst: "/analyst/data-explorer",
    risk_manager: "/risk/fraud-topology",
    admin: "/admin/overview",
  },
  thresholds: {
    msme: "/msme/score-report",
    loan_officer: "/bank/decisions",
    credit_analyst: "/analyst/signal-trends",
    risk_manager: "/risk/thresholds",
    admin: "/admin/audit-log",
  },
  fraud_topology: {
    msme: "/msme/strategy-lab",
    loan_officer: "/bank/strategy-lab",
    credit_analyst: "/analyst/signal-trends",
    risk_manager: "/risk/fraud-topology",
    admin: "/admin/overview",
  },
  users: {
    msme: "/msme/dashboard",
    loan_officer: "/bank/loan-queue",
    credit_analyst: "/analyst/data-explorer",
    risk_manager: "/risk/fraud-queue",
    admin: "/admin/users",
  },
  api_keys: {
    msme: "/msme/dashboard",
    loan_officer: "/bank/loan-queue",
    credit_analyst: "/analyst/data-explorer",
    risk_manager: "/risk/fraud-queue",
    admin: "/admin/api-keys",
  },
  banks: {
    msme: "/msme/dashboard",
    loan_officer: "/bank/loan-queue",
    credit_analyst: "/analyst/data-explorer",
    risk_manager: "/risk/fraud-queue",
    admin: "/admin/banks",
  },
};

export function VoiceControlProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { theme, resolvedTheme, setTheme } = useTheme();
  const { user } = useAuth();

  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [feedback, setFeedback] = useState("");
  const [isSupported, setIsSupported] = useState(false);

  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const feedbackTimeoutRef = useRef<number | null>(null);
  const shouldKeepListeningRef = useRef(false);

  const clearFeedbackAfterDelay = useCallback(() => {
    if (feedbackTimeoutRef.current) {
      window.clearTimeout(feedbackTimeoutRef.current);
    }

    feedbackTimeoutRef.current = window.setTimeout(() => {
      setFeedback("");
    }, 2600);
  }, []);

  const role = user?.role ?? "msme";

  const queueUiAction = useCallback((action: string) => {
    if (typeof window === "undefined") return;
    window.sessionStorage.setItem(VOICE_PENDING_ACTION_KEY, action);
    window.dispatchEvent(new CustomEvent("voice:ui-action", { detail: { action } }));
  }, []);

  const resolveRoute = useCallback(
    (target: keyof typeof NAV_TARGETS) => {
      const routesForTarget = NAV_TARGETS[target];
      return routesForTarget?.[role] ?? routesForTarget?.msme;
    },
    [role],
  );

  const executeParsedCommand = useCallback(
    (parsed: ParsedCommand) => {
      if (parsed.type === "navigate") {
        if (parsed.target in NAV_TARGETS) {
          const nextRoute = resolveRoute(parsed.target as keyof typeof NAV_TARGETS);
          if (nextRoute && nextRoute !== pathname) {
            router.push(nextRoute);
          }
          setFeedback(`Command executed: ${parsed.target}`);
          clearFeedbackAfterDelay();
          return;
        }
      }

      if (parsed.type === "action") {
        if (parsed.target === "risk") {
          const nextRoute = resolveRoute("risk");
          if (nextRoute) router.push(nextRoute);
          queueUiAction("show_risk");
          window.dispatchEvent(new CustomEvent("voice:show-risk"));
          setFeedback("Showing your risk");
          clearFeedbackAfterDelay();
          return;
        }

        if (parsed.target === "open_twin") {
          const dashboardRoute = resolveRoute("dashboard");
          if (dashboardRoute && dashboardRoute !== pathname) {
            router.push(dashboardRoute);
          }
          queueUiAction("open_twin");
          window.dispatchEvent(new CustomEvent("voice:open-digital-twin"));
          setFeedback("Opening digital twin");
          clearFeedbackAfterDelay();
          return;
        }

        if (parsed.target === "open_twin_chat") {
          const dashboardRoute = resolveRoute("dashboard");
          if (dashboardRoute && dashboardRoute !== pathname) {
            router.push(dashboardRoute);
          }
          queueUiAction("open_twin_chat");
          window.dispatchEvent(new CustomEvent("voice:open-twin-chat"));
          setFeedback("Opening twin chat");
          clearFeedbackAfterDelay();
          return;
        }

        if (parsed.target === "toggle_dark_mode") {
          const isDark = (resolvedTheme ?? theme) === "dark";
          setTheme(isDark ? "light" : "dark");
          setFeedback(`Theme changed to ${isDark ? "light" : "dark"}`);
          clearFeedbackAfterDelay();
          return;
        }
      }

      setFeedback("Sorry, I didn't understand that");
      clearFeedbackAfterDelay();
    },
    [clearFeedbackAfterDelay, pathname, queueUiAction, resolveRoute, resolvedTheme, router, setTheme, theme],
  );

  const handleCommand = useCallback(
    (text: string) => {
      const cleaned = text.trim();
      setTranscript(cleaned);

      if (!cleaned) {
        setFeedback("Sorry, I didn't understand that");
        clearFeedbackAfterDelay();
        return;
      }

      const parsed = parseCommand(cleaned);
      if (!parsed) {
        setFeedback("Sorry, I didn't understand that");
        clearFeedbackAfterDelay();
        return;
      }

      executeParsedCommand(parsed);
    },
    [clearFeedbackAfterDelay, executeParsedCommand],
  );

  const stopListening = useCallback(() => {
    shouldKeepListeningRef.current = false;
    recognitionRef.current?.stop();
    setIsListening(false);
  }, []);

  const startListening = useCallback(() => {
    if (!isSupported || !recognitionRef.current) {
      setFeedback("Voice control is not supported in this browser");
      clearFeedbackAfterDelay();
      return;
    }

    if (shouldKeepListeningRef.current) {
      return;
    }

    setTranscript("");
    setFeedback("Listening...");
    shouldKeepListeningRef.current = true;
    try {
      recognitionRef.current.start();
      setIsListening(true);
    } catch {
      shouldKeepListeningRef.current = false;
      setIsListening(false);
      setFeedback("Microphone is busy. Try again.");
      clearFeedbackAfterDelay();
    }
  }, [clearFeedbackAfterDelay, isSupported]);

  const toggleListening = useCallback(() => {
    if (isListening) stopListening();
    else startListening();
  }, [isListening, startListening, stopListening]);

  useEffect(() => {
    if (typeof window === "undefined") return;

    const SpeechRecognitionCtor =
      (window as any).webkitSpeechRecognition || (window as any).SpeechRecognition;

    if (!SpeechRecognitionCtor) {
      setIsSupported(false);
      return;
    }

    const recognition: SpeechRecognitionLike = new SpeechRecognitionCtor();
    recognition.lang = "en-IN";
    recognition.continuous = true;
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;

    recognition.onresult = (event) => {
      for (let i = event.resultIndex || 0; i < event.results.length; i += 1) {
        const result = event.results[i];
        if (!result?.isFinal) continue;

        const text = result[0]?.transcript ?? "";
        if (text) {
          handleCommand(text);
        } else {
          setFeedback("Sorry, I didn't understand that");
          clearFeedbackAfterDelay();
        }
      }
    };

    recognition.onerror = (event) => {
      setIsListening(false);
      if (event?.error === "aborted") {
        return;
      }

      shouldKeepListeningRef.current = false;
      setFeedback("Sorry, I didn't understand that");
      clearFeedbackAfterDelay();
    };

    recognition.onend = () => {
      if (shouldKeepListeningRef.current) {
        try {
          recognition.start();
          setIsListening(true);
          return;
        } catch {
          // Retry in next tick for browsers that briefly lock recognition state.
          window.setTimeout(() => {
            if (!shouldKeepListeningRef.current) return;
            try {
              recognition.start();
              setIsListening(true);
            } catch {
              shouldKeepListeningRef.current = false;
              setIsListening(false);
              setFeedback("Microphone is busy. Try again.");
              clearFeedbackAfterDelay();
            }
          }, 180);
          return;
        }
      }

      setIsListening(false);
    };

    recognitionRef.current = recognition;
    setIsSupported(true);

    return () => {
      shouldKeepListeningRef.current = false;
      recognition.stop();
      recognitionRef.current = null;
      if (feedbackTimeoutRef.current) {
        window.clearTimeout(feedbackTimeoutRef.current);
      }
    };
  }, [clearFeedbackAfterDelay, handleCommand]);

  const value = useMemo(
    () => ({
      isListening,
      transcript,
      feedback,
      isSupported,
      startListening,
      stopListening,
      toggleListening,
      handleCommand,
    }),
    [feedback, handleCommand, isListening, isSupported, startListening, stopListening, toggleListening, transcript],
  );

  return <VoiceControlContext.Provider value={value}>{children}</VoiceControlContext.Provider>;
}
