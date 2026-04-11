

import { NextResponse } from 'next/server';

export async function POST(request: Request) {
  try {
    const { message, dataContext } = await request.json();
    const apiKey = process.env.FEATHERLESS_API_KEY;

    if (!apiKey) {
      return NextResponse.json({ error: 'FEATHERLESS_API_KEY is missing. Please add it to your .env file.' }, { status: 500 });
    }

    const systemPrompt = `You are Priya, a Digital Twin Financial AI Assistant for an MSME. 
    Here is the user's financial data context:
    ${JSON.stringify(dataContext || {})}
    
    Answer the user's query clearly and concisely (strictly maximum 3 short sentences). Speak directly to the business owner in a conversational and supportive way. Give immediate, actionable insights based on their data if applicable. Do not use formatting like bolding or bullet points, as this text will simply be read aloud by TTS.`;

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
          { role: 'user', content: message }
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
    console.error('Twin Chat Route Error:', error);
    return NextResponse.json({ error: 'Failed to generate response' }, { status: 500 });
  }
}