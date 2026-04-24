"use client";
import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/dib/authContext";
import { PageHeader } from "@/components/shared";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { MessageSquare, Bot, User, Send, Play, BookOpen } from "lucide-react";
import { cn } from "@/dib/utils";

const GUIDE_TOPICS = [
  { id: "twin_intro", title: "The Power of Financial Digital Twins", duration: "4 min", videoId: "u31qwQUeGuM" },
  { id: "engine", title: "FinTwin: Cognitive Credit Engine Explained", duration: "5 min", videoId: "ka2raSNBPIs" },
  { id: "scenario", title: "Real-Time Scenario Modeling for MSMEs", duration: "3 min", videoId: "cYCGs0DNAyw" },
  { id: "fraud", title: "How FinTwin Predicts Anomaly & Fraud", duration: "6 min", videoId: "xgjLJ05LVHg" },
  { id: "score", title: "Understanding Your Credit Score", duration: "3 min", videoId: "GuyecpBm2Qs" },
  { id: "loan", title: "Applying for an MSME Loan Successfully", duration: "4 min", videoId: "LwMYQI7Rh0Y" },
  { id: "onboarding", title: "Configuring Your First Digital Twin", duration: "3 min", videoId: "2b9txcAt4e0" },
];

import { msmeApi } from "@/dib/api";

const LANGUAGES = ["English", "Hindi", "Marathi", "Tamil", "Telugu", "Kannada"];
const USE_MOCK = process.env.NEXT_PUBLIC_USE_MOCK !== "false";

export default function MsmeGuidePage() {
  const { user } = useAuth();
  const router = useRouter();
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      content:
        "Namaste! I'm your NeuroCred MSME Assistant. How can I help you today? You can ask about your credit score, GST filing, loan products, or schemes like CGTMSE and MUDRA.",
      timestamp: new Date().toISOString(),
    },
  ]);
  const [input, setInput] = useState("");
  const [language, setLanguage] = useState("English");
  const [selectedTopic, setSelectedTopic] = useState<string | null>(null);
  const [topics, setTopics] = useState<any[]>(GUIDE_TOPICS);
  const [activeTab, setActiveTab] = useState<"chatbot" | "video" | "ai">("video");
  const chatContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    msmeApi.getGuideTopics().then((res) => {
      if (res && res.length > 0) {
        const mapped = res.map((t: any, i: number) => ({
          ...t,
          videoId: t.video_url ? t.video_url.split('v=')[1] : GUIDE_TOPICS[i % GUIDE_TOPICS.length].videoId,
          duration: "3 min"
        }));
        setTopics(mapped);
      }
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTo({
        top: chatContainerRef.current.scrollHeight,
        behavior: "smooth",
      });
    }
  }, [messages]);

  useEffect(() => {
    if (!user || user.role !== "msme") {
      router.push("/unauthorized");
    }
  }, [user, router]);

  if (!user || user.role !== "msme") {
    return null;
  }

  const sendMessage = async () => {
    if (!input.trim()) return;
    const prompt = input;
    const userMsg = {
      role: "user",
      content: prompt,
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");

    if (USE_MOCK) {
      const response =
        selectedTopic === "loan"
          ? "Mock assistant: for loan readiness, maintain GST filing timeliness, keep UPI inflows stable, and avoid concentration in 1-2 counterparties."
          : selectedTopic === "cgtmse"
            ? "Mock assistant: CGTMSE supports collateral-free MSME loans; eligibility depends on lender policy, business profile, and recent signal quality."
            : `Mock assistant (${language}): this guide is in frontend mock mode. You can continue end-to-end testing without backend.`;
      // We will skip mock entirely to use the actual Groq API if possible.
    }

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messages: [{ role: "user", content: prompt }],
          context: { language, selectedTopic }
        })
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Network error");
      
      setMessages(prev => [...prev, { role: "assistant", content: data.reply, timestamp: new Date().toISOString() }]);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "Sorry, I am currently offline.",
          timestamp: new Date().toISOString(),
        },
      ]);
    }
  };

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <PageHeader
        title="Help & Guide"
        description="Chatbot assistance and video explainers"
      />

      <div className="flex justify-center mb-8">
        <div className="bg-muted p-1.5 rounded-full flex flex-col md:flex-row items-center gap-2 shadow-inner border border-white/5">
          <button 
            onClick={() => setActiveTab('chatbot')} 
            className={cn("px-6 py-2.5 rounded-full text-sm font-bold transition-all w-full md:w-auto", activeTab === 'chatbot' ? 'bg-primary text-black shadow-md' : 'text-muted-foreground hover:text-foreground')}
          >
            Credit Assistant
          </button>
          <button 
            onClick={() => setActiveTab('video')} 
            className={cn("px-6 py-2.5 rounded-full text-sm font-bold transition-all w-full md:w-auto", activeTab === 'video' ? 'bg-primary text-black shadow-md' : 'text-muted-foreground hover:text-foreground')}
          >
            Video Library
          </button>
          <button 
            onClick={() => setActiveTab('ai')} 
            className={cn("px-6 py-2.5 rounded-full text-sm font-bold transition-all w-full md:w-auto", activeTab === 'ai' ? 'bg-primary text-black shadow-md' : 'text-muted-foreground hover:text-foreground')}
          >
            Interactive AI Guide
          </button>
        </div>
      </div>

      <div className="flex flex-col gap-8">
        {/* Chatbot */}
        {activeTab === 'chatbot' && (
        <Card className="border-border shadow-xl flex flex-col h-[600px] overflow-hidden bg-white/50 backdrop-blur-sm">
          <CardHeader className="py-4 px-6 border-b flex-row items-center justify-between gap-2 shrink-0 bg-white/10">
            <div className="flex items-center gap-2">
              <MessageSquare className="w-4 h-4 text-primary" />
              <CardTitle className="text-sm font-semibold">
                Credit Assistant
              </CardTitle>
            </div>
            <Select value={language} onValueChange={setLanguage}>
              <SelectTrigger className="w-28 h-7 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {LANGUAGES.map((l) => (
                  <SelectItem key={l} value={l} className="text-xs">
                    {l}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </CardHeader>
          <div 
            ref={chatContainerRef}
            className="flex-1 overflow-y-auto p-6 space-y-6 scroll-smooth scrollbar-thin scrollbar-thumb-primary/20"
          >
            {messages.map((m, i) => (
              <div
                key={i}
                className={cn(
                  "flex gap-4 animate-in fade-in slide-in-from-bottom-2 duration-300",
                  m.role === "user" && "flex-row-reverse",
                )}
              >
                <div
                  className={cn(
                    "w-10 h-10 rounded-full flex items-center justify-center shrink-0 text-sm shadow-md transition-transform hover:scale-110",
                    m.role === "assistant"
                      ? "bg-primary text-black ring-4 ring-primary/10"
                      : "bg-background text-foreground border shadow-sm",
                  )}
                >
                  {m.role === "assistant" ? (
                    <Bot className="w-5 h-5 text-black" />
                  ) : (
                    <User className="w-5 h-5" />
                  )}
                </div>
                <div
                  className={cn(
                    "max-w-[70%] rounded-2xl px-5 py-3.5 text-sm leading-relaxed shadow-sm border",
                    m.role === "assistant"
                      ? "bg-card text-foreground rounded-tl-none border-border"
                      : "bg-primary text-black rounded-tr-none border-primary/20",
                  )}
                >
                  {m.content}
                </div>
              </div>
            ))}
          </div>
          <div className="p-3 border-t flex gap-2 shrink-0">
            <Input
              placeholder="Ask anything about your score, GST, loans..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && sendMessage()}
              className="text-sm"
            />
            <Button
              size="icon"
              onClick={sendMessage}
              className="bg-primary hover:bg-primary/90 shrink-0 text-black"
            >
              <Send className="w-4 h-4" />
            </Button>
          </div>
        </Card>
        )}

        {/* Video guides */}
        {activeTab === 'video' && (
        <Card className="border-border shadow-xl flex flex-col h-[auto] min-h-[600px] overflow-hidden bg-card/60 backdrop-blur-xl">
          <CardHeader className="py-4 px-6 border-b flex-row items-center justify-between bg-white/10 shrink-0">
             <div className="flex items-center gap-3">
               <div className="p-2 bg-primary/10 rounded-xl">
                  <BookOpen className="w-5 h-5 text-primary" />
               </div>
               <div>
                  <CardTitle className="text-lg font-bold">Video Learning Library</CardTitle>
                  <p className="text-xs text-muted-foreground">Expert guides for MSME growth</p>
               </div>
             </div>
             <Badge className="bg-primary/5 text-primary border-primary/20 hover:bg-primary/10 tracking-widest px-3 py-1 text-[10px] uppercase font-black">
               {topics.length} MODULES
             </Badge>
          </CardHeader>
          <div className="flex flex-col lg:flex-row h-full min-h-[600px] divide-y lg:divide-y-0 lg:divide-x divide-border/50">
            {/* Left Sidebar: Lesson Modules */}
            <div className="w-full lg:w-80 shrink-0 bg-black/5 flex flex-col h-[400px] lg:h-auto">
              <div className="p-5 border-b border-border/50 sticky top-0 bg-card/60 backdrop-blur-xl z-10">
                <h3 className="text-xs font-black text-foreground uppercase tracking-widest flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-primary animate-pulse" />
                  Playlist Modules
                </h3>
              </div>
              <div className="flex-1 overflow-y-auto p-4 space-y-3 scrollbar-thin scrollbar-thumb-primary/20">
                {topics.map((topic, index) => (
                  <button
                    key={topic.id}
                    onClick={() =>
                      setSelectedTopic(selectedTopic === topic.id ? null : topic.id)
                    }
                    className={cn(
                      "w-full group p-1 rounded-2xl transition-all duration-500 text-left",
                      selectedTopic === topic.id
                        ? "bg-gradient-to-br from-primary via-primary to-blue-500 shadow-lg shadow-primary/20"
                        : "bg-transparent hover:bg-muted/30"
                    )}
                  >
                    <div className={cn(
                      "w-full text-left p-3.5 rounded-xl flex items-center gap-3 border transition-all duration-300",
                      selectedTopic === topic.id
                        ? "bg-white/5 border-transparent text-white"
                        : "bg-white/50 border-border group-hover:border-primary/40 group-hover:bg-background"
                    )}>
                      <div
                        className={cn(
                          "w-7 h-7 rounded-lg flex items-center justify-center shrink-0 font-bold text-[10px] ring-1",
                          selectedTopic === topic.id
                            ? "bg-white/20 ring-white/30 text-white"
                            : "bg-muted ring-border text-foreground"
                        )}
                      >
                        {index + 1}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className={cn(
                          "text-[11px] font-black truncate mb-1 uppercase tracking-tight leading-tight",
                          selectedTopic === topic.id ? "text-white" : "text-foreground"
                        )}>
                          {topic.title}
                        </p>
                        <div className="flex items-center gap-2">
                           <Play className={cn("w-2 h-2", selectedTopic === topic.id ? "text-white" : "text-primary/70")} />
                           <span className={cn("text-[9px] font-bold", selectedTopic === topic.id ? "text-white/70" : "text-muted-foreground")}>
                             {topic.duration}
                           </span>
                        </div>
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            </div>

            {/* Right side: Premium Video Player Area */}
            <div className="flex-1 p-6 lg:p-8 overflow-y-auto bg-black/5">
              <div className="w-full max-w-4xl mx-auto">
                {selectedTopic ? (
                  <div className="space-y-6 animate-in fade-in slide-in-from-top-8 duration-700">
                    <div className="relative group p-1 bg-gradient-to-br from-primary/30 via-transparent to-blue-400/30 rounded-3xl">
                      <div className="absolute inset-0 bg-primary/20 blur-3xl opacity-20 -z-10 group-hover:opacity-40 transition-opacity duration-1000" />
                      <div className="relative aspect-video rounded-2xl overflow-hidden bg-black shadow-2xl ring-1 ring-white/10">
                        <iframe
                          width="100%"
                          height="100%"
                          src={`https://www.youtube.com/embed/${topics.find((t) => t.id === selectedTopic)?.videoId}?autoplay=1&rel=0`}
                          title="YouTube video player"
                          frameBorder="0"
                          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
                          allowFullScreen
                          className="w-full h-full"
                        ></iframe>
                      </div>
                    </div>

                    <div className="flex flex-col xl:flex-row xl:items-start justify-between gap-6 p-4">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-3">
                           <Badge variant="outline" className="text-primary border-primary/20 bg-primary/5 font-extrabold px-3 py-1">
                              LESSON {topics.findIndex(t => t.id === selectedTopic) + 1}
                           </Badge>
                           <span className="text-xs text-muted-foreground bg-muted/30 px-3 py-1 rounded-full border border-border/50">
                              Duration: {topics.find((t) => t.id === selectedTopic)?.duration}
                           </span>
                        </div>
                        <h2 className="text-2xl font-black tracking-tight text-foreground line-clamp-2">
                          {topics.find((t) => t.id === selectedTopic)?.title}
                        </h2>
                        <p className="text-sm text-muted-foreground mt-3 max-w-3xl leading-relaxed font-medium">
                          Elevate your knowledge with our masterclass on {topics.find((t) => t.id === selectedTopic)?.title.toLowerCase()}. Learn actionable insights to optimize your financial posture with FinTwin.
                        </p>
                      </div>
                      <Button size="lg" className="h-12 px-8 rounded-full font-bold shadow-lg shadow-primary/25 hover:scale-105 transition-transform text-black shrink-0">
                         Mark Lesson Done
                      </Button>
                    </div>
                  </div>
                ) : (
                  <div className="aspect-video bg-muted/10 rounded-3xl flex flex-col items-center justify-center border-2 border-dashed border-border/50 transition-colors p-8">
                    <div className="relative w-24 h-24 mb-6">
                      <div className="absolute inset-0 bg-primary/20 rounded-full blur-2xl animate-pulse" />
                      <div className="relative w-full h-full bg-primary/10 rounded-full flex items-center justify-center border border-primary/20">
                        <Play className="w-10 h-10 text-primary opacity-60 ml-1" />
                      </div>
                    </div>
                    <h3 className="text-xl font-bold text-foreground">Select a Masterclass</h3>
                    <p className="text-sm text-muted-foreground mt-2 max-w-xs text-center leading-relaxed">
                      Choose a module from the sidebar playlist to start your financial learning journey.
                    </p>
                  </div>
                )}
              </div>
            </div>
          </div>
        </Card>
        )}
      </div>

      {/* AI Agent */}
      {activeTab === 'ai' && (
        <Card className="border-border shadow-md overflow-hidden">
          <CardHeader className="py-4 px-6 border-b bg-muted/30 flex-row items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
              <Bot className="w-5 h-5 text-primary" />
            </div>
            <div>
              <CardTitle className="text-base font-bold">Interactive AI Guide</CardTitle>
              <p className="text-xs text-muted-foreground">Speak with our virtual credit expert</p>
            </div>
          </CardHeader>
          <CardContent className="p-0 border-t border-border/50">
            <div className="relative w-full h-[550px] bg-[#000] overflow-hidden rounded-b-xl">
              <iframe
                src="https://embed.liveavatar.com/v1/c82bf1c5-4229-4588-831c-746488888418"
                allow="microphone"
                title="LiveAvatar Embed"
                className="absolute inset-0 w-full h-full border-0"
                scrolling="no"
              ></iframe>
            </div>
          </CardContent>
        </Card>
        )}
    </div>
  );
}
