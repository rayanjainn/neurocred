import { NextResponse } from "next/server";

function clipText(value: unknown, max = 220): string {
  const text = String(value ?? "").replace(/\s+/g, " ").trim();
  return text.length > max ? `${text.slice(0, max)}...` : text;
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

export async function POST(request: Request) {
  try {
    const { message, dataContext, userId } = await request.json();
    const apiKey = process.env.FEATHERLESS_API_KEY;

    if (!apiKey) {
      return NextResponse.json(
        { error: "FEATHERLESS_API_KEY is missing. Please add it to frontend env." },
        { status: 500 },
      );
    }

    const systemPrompt = [
      "You are Priya, a Digital Twin Financial AI Assistant for an MSME/individual user.",
      "You MUST use provided backend twin context as source of truth.",
      "If data is sparse, say so clearly and provide practical next actions.",
      "Keep answer short, voice-friendly, and actionable (max 3 short sentences).",
      "Do not use markdown or bullets.",
    ].join(" ");

    const safeMessage = clipText(message, 280);
    const safeContext = compactContext(dataContext || {});
    const userPrompt = `User ID: ${userId || "unknown"}\nUser query: ${safeMessage}\n\nLive backend twin context (compact):\n${JSON.stringify(safeContext)}`;

    const response = await fetch("https://api.featherless.ai/v1/chat/completions", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: "deepseek-ai/DeepSeek-V3-0324",
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
      throw new Error(payload?.error?.message || "Featherless API error");
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
