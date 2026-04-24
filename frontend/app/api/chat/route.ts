import { NextResponse } from 'next/server';

export async function POST(request: Request) {
  try {
    const { messages, context } = await request.json();
    const apiKey = process.env.GROQ_API_KEY;

    if (!apiKey) {
      return NextResponse.json({ error: 'GROQ_API_KEY is missing.' }, { status: 500 });
    }

    const { language = "English", selectedTopic } = context || {};

    let systemPrompt = `You are the NeuroCred Application Assistant. The user prefers the language: ${language}. Answer ONLY in this language using clear, practical, concise terms.

CRITICAL INSTRUCTION: You MUST ONLY answer questions related to finance, digital twin use cases, NeuroCred, credit score, loan eligibility, repayment planning, and fraud/risk signals.
NeuroCred is a cognitive credit engine that creates Digital Twins for MSMEs and Individuals to track financial stability, predict risk scores in real-time, detect anomalies/fraud, and model loan scenarios.
If the user asks about anything outside finance/product context, politely decline in one short sentence.

For affordability/purchase questions (car, bike, phone, property, etc.), respond with this structure:
1) First token must be exactly one word: YES or MAYBE or NO.
2) Then 2 to 4 short sentences with reasoning using score, EMI burden, liquidity/cash buffer, and risk.
3) If exact numbers are missing, state assumptions briefly and still give a verdict.

Do not use markdown or bullet points.`;

    if (selectedTopic) {
      systemPrompt += `\nContext: The user is currently viewing a lesson on the topic: ${selectedTopic}.`;
    }

    const response = await fetch('https://api.groq.com/openai/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${apiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: 'llama-3.1-8b-instant',
        messages: [
          { role: 'system', content: systemPrompt },
          ...messages
        ],
        temperature: 0.5,
        max_tokens: 220,
      }),
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.error?.message || "Error from Groq API");
    }

    return NextResponse.json({ reply: data.choices[0].message.content });
  } catch (error: any) {
    console.error('Chat Route Error:', error);
    return NextResponse.json({ error: 'Failed to generate response' }, { status: 500 });
  }
}
