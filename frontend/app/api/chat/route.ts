import { NextResponse } from 'next/server';

export async function POST(request: Request) {
  try {
    const { messages, context } = await request.json();
    const apiKey = process.env.FEATHERLESS_API_KEY;

    if (!apiKey) {
      return NextResponse.json({ error: 'FEATHERLESS_API_KEY is missing.' }, { status: 500 });
    }

    const { language = "English", selectedTopic } = context || {};

    let systemPrompt = `You are the FinTwin Application Assistant. The user prefers the language: ${language}. Answer ONLY in this language using extremely simple, minimalistic, and straightforward terms.

CRITICAL INSTRUCTION: You MUST ONLY answer questions related to the Finance Domain, Digital Twin Use Cases, FinTwin Application and its feature set. 
FinTwin is a Cognitive Credit Engine that creates Digital Twins for MSMEs and Individuals to track financial stability, predict risk scores in real-time, detect anomalies/fraud, and model various loan scenarios. 
If the user asks about ANYTHING else (e.g. general knowledge, casual chat, math), you must politely decline and state that you can only explain financial terms. Do not over-explain. Keep responses to a maximum of 1 to 2 short sentences.
You can answer the genuine fintech related basic doubts for learning purpose. Do not add any type of note or anything other than the response itself, and put no kind of markdown  in the response.`;

    if (selectedTopic) {
      systemPrompt += `\nContext: The user is currently viewing a lesson on the topic: ${selectedTopic}.`;
    }

    const response = await fetch('https://api.featherless.ai/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${apiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: 'deepseek-ai/DeepSeek-V3-0324',
        messages: [
          { role: 'system', content: systemPrompt },
          ...messages
        ],
        temperature: 0.7,
      }),
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.error?.message || "Error from Featherless API");
    }

    return NextResponse.json({ reply: data.choices[0].message.content });
  } catch (error: any) {
    console.error('Chat Route Error:', error);
    return NextResponse.json({ error: 'Failed to generate response' }, { status: 500 });
  }
}
