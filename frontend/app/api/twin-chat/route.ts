import { NextResponse } from "next/server";

function normalizeBackendBase(raw: string | undefined): string | null {
  const value = String(raw || "").trim();
  if (!value || value.startsWith("/")) return null;
  return value.replace(/\/$/, "");
}

function resolveBackendCandidates(): string[] {
  const ordered = [
    process.env.BACKEND_API_URL,
    process.env.API_PROXY_TARGET,
    process.env.NEXT_PUBLIC_API_URL,
    "http://localhost:8001",
    "http://127.0.0.1:8001",
    "http://10.10.43.20:8001",
  ];

  const seen = new Set<string>();
  const candidates: string[] = [];
  for (const item of ordered) {
    const normalized = normalizeBackendBase(item);
    if (!normalized || seen.has(normalized)) continue;
    seen.add(normalized);
    candidates.push(normalized);
  }
  return candidates;
}

function clipText(value: unknown, max = 220): string {
  const text = String(value ?? "").replace(/\s+/g, " ").trim();
  return text.length > max ? `${text.slice(0, max)}...` : text;
}

async function fetchBackendPath(path: string): Promise<any | null> {
  const backends = resolveBackendCandidates();
  for (const backend of backends) {
    try {
      const response = await fetch(`${backend}${path}`, {
        method: "GET",
        cache: "no-store",
      });
      if (!response.ok) continue;
      return await response.json().catch(() => null);
    } catch {
      // Try next backend candidate.
    }
  }
  return null;
}

async function buildDynamicContext(userId: string, dataContext: any) {
  const base = {
    ...(dataContext && typeof dataContext === "object" ? dataContext : {}),
    user_id: userId || dataContext?.user_id || dataContext?.userId || "",
  };

  if (!userId) return base;

  const [twinState, twinHistory, twinTriggers, twinReport] = await Promise.all([
    fetchBackendPath(`/twin/${encodeURIComponent(userId)}`),
    fetchBackendPath(`/twin/${encodeURIComponent(userId)}/history`),
    fetchBackendPath(`/twin/${encodeURIComponent(userId)}/triggers`),
    fetchBackendPath(`/twin/${encodeURIComponent(userId)}/report`),
  ]);

  return {
    ...base,
    twin_state: twinState ?? base.twin_state ?? {},
    twin_history: twinHistory ?? base.twin_history ?? [],
    twin_triggers: twinTriggers ?? base.twin_triggers ?? [],
    twin_report: twinReport ?? base.twin_report ?? {},
    context_refreshed_at: new Date().toISOString(),
  };
}

function compactContext(raw: any) {
  const state = raw?.twin_state || {};
  const history = Array.isArray(raw?.twin_history) ? raw.twin_history : [];
  const triggers = Array.isArray(raw?.twin_triggers) ? raw.twin_triggers : [];
  const report = raw?.twin_report || {};
  const score = raw?.latest_score || {};

  return {
    user: {
      id: raw?.user_profile?.id || raw?.user_id || null,
      name: raw?.user_profile?.name || null,
      role: raw?.user_profile?.role || null,
      gstin: raw?.user_profile?.gstin || null,
    },
    twin: {
      risk_score: state?.risk_score ?? null,
      liquidity_health: state?.liquidity_health ?? null,
      persona: state?.persona ?? null,
      cibil_like_score: state?.cibil_like_score ?? null,
      mood: state?.avatar_state?.mood_message ? clipText(state.avatar_state.mood_message, 120) : null,
      top_reasons: Array.isArray(state?.top_reasons) ? state.top_reasons.slice(0, 3).map((x: any) => clipText(x, 120)) : [],
    },
    history: history.slice(0, 3).map((h: any) => ({
      version: h?.version,
      risk_score: h?.risk_score,
      liquidity_health: h?.liquidity_health,
      persona: h?.persona,
      ts: h?.last_updated || h?.created_at || null,
    })),
    triggers: triggers.slice(0, 4).map((t: any) => ({
      id: t?.trigger_id || t?.type || "trigger",
      severity: t?.severity || t?.urgency || "info",
      message: clipText(t?.message || t?.reason || "", 140),
    })),
    report: {
      summary: clipText(report?.summary || report?.narrative || "", 220),
      actions: Array.isArray(report?.suggested_actions)
        ? report.suggested_actions.slice(0, 3).map((x: any) => clipText(x, 100))
        : [],
    },
    score: {
      credit_score: score?.credit_score ?? raw?.credit_score ?? null,
      risk_band: score?.risk_band ?? raw?.risk_band ?? null,
      recommended_wc_amount: score?.recommended_wc_amount ?? raw?.recommended_wc_amount ?? null,
      recommended_term_amount: score?.recommended_term_amount ?? raw?.recommended_term_amount ?? null,
      data_maturity_months: score?.data_maturity_months ?? raw?.data_maturity_months ?? null,
      top_reasons: Array.isArray(score?.top_reasons)
        ? score.top_reasons.slice(0, 3).map((x: any) => clipText(x, 120))
        : Array.isArray(raw?.top_reasons)
          ? raw.top_reasons.slice(0, 3).map((x: any) => clipText(x, 120))
          : [],
    },
  };
}

function compactConversationHistory(raw: any): Array<{ role: string; text: string }> {
  if (!Array.isArray(raw)) return [];

  return raw
    .slice(-10)
    .map((item: any) => {
      const role = String(item?.role || "").toLowerCase();
      const normalizedRole = role === "assistant" ? "assistant" : "user";
      const text = clipText(item?.text || item?.content || "", 220);
      return { role: normalizedRole, text };
    })
    .filter((item) => item.text.length > 0);
}

export async function POST(request: Request) {
  try {
    const { message, dataContext, userId, conversationHistory, chatSessionId } = await request.json();
    const apiKey = process.env.GROQ_API_KEY;

    if (!apiKey) {
      return NextResponse.json(
        { error: "GROQ_API_KEY is missing. Please add it to frontend env." },
        { status: 500 },
      );
    }

    const resolvedUserId = String(
      userId || dataContext?.user_id || dataContext?.userId || "",
    ).trim();

    const dynamicContext = await buildDynamicContext(resolvedUserId, dataContext);
    const memory = compactConversationHistory(conversationHistory);
    const memoryBlock = memory.length
      ? memory
          .map((item, idx) => `${idx + 1}. ${item.role}: ${item.text}`)
          .join("\n")
      : "none";

    const systemPrompt = `You are Priya, a Digital Twin Financial AI Assistant for an MSME.
Here is the user's financial data context:
${JSON.stringify(compactContext(dynamicContext || {}))}

Answer the user's query clearly and concisely (strictly maximum 3 short sentences). Speak directly to the business owner in a conversational and supportive way. Give immediate, actionable insights based on their data if applicable. Do not use formatting like bolding or bullet points, as this text will simply be read aloud by TTS.`;

    const safeMessage = clipText(message, 280);
    const safeSessionId = clipText(chatSessionId || "", 80);
    const userPrompt = [
      `User ID: ${resolvedUserId || "unknown"}`,
      `Chat session ID: ${safeSessionId || "none"}`,
      `Recent chat memory:\n${memoryBlock}`,
      `User query: ${safeMessage}`,
    ].join("\n\n");

    const response = await fetch("https://api.groq.com/openai/v1/chat/completions", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: "llama-3.1-8b-instant",
        temperature: 0.7,
        max_tokens: 150,
        messages: [
          { role: "system", content: systemPrompt },
          { role: "user", content: userPrompt },
        ],
      }),
    });

    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload?.error?.message || "Error from Groq API");
    }

    const reply = payload?.choices?.[0]?.message?.content?.trim() || "I could not generate a response right now.";
    return NextResponse.json({ reply });
  } catch (error: any) {
    return NextResponse.json(
      { error: error?.message || "Failed to generate twin response" },
      { status: 500 },
    );
  }
}
