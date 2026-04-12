import { NextResponse } from "next/server";

export const runtime = "nodejs";

export async function POST(request: Request) {
  try {
    const formData = await request.formData();
    const audio = formData.get("audio");
    const userId = String(formData.get("userId") || "").trim();
    const dataContextRaw = String(formData.get("dataContext") || "").trim();

    if (!(audio instanceof File)) {
      return NextResponse.json({ error: "Audio file is required." }, { status: 400 });
    }

    if (!userId) {
      return NextResponse.json({ error: "User ID is required." }, { status: 400 });
    }

    const apiKey = process.env.GROQ_API_KEY;
    if (!apiKey) {
      return NextResponse.json(
        { error: "GROQ_API_KEY is missing. Please add it to frontend env." },
        { status: 500 },
      );
    }

    let dataContext: any = {};
    if (dataContextRaw) {
      try {
        dataContext = JSON.parse(dataContextRaw);
      } catch {
        dataContext = {};
      }
    }

    const sttBody = new FormData();
    sttBody.append("file", audio, audio.name || `voice-${Date.now()}.webm`);
    sttBody.append("model", "whisper-large-v3-turbo");
    sttBody.append("language", "en");

    const transcriptionResponse = await fetch(
      "https://api.groq.com/openai/v1/audio/transcriptions",
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${apiKey}`,
        },
        body: sttBody,
      },
    );

    const transcriptionPayload = await transcriptionResponse.json().catch(() => ({}));
    if (!transcriptionResponse.ok) {
      return NextResponse.json(
        { error: transcriptionPayload?.error?.message || "Whisper transcription failed." },
        { status: transcriptionResponse.status || 502 },
      );
    }

    const transcript = String(transcriptionPayload?.text || "").trim();
    if (!transcript) {
      return NextResponse.json(
        { error: "Could not detect speech in the recording." },
        { status: 422 },
      );
    }

    const origin = new URL(request.url).origin;
    const twinResponse = await fetch(`${origin}/api/twin-chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: transcript,
        userId,
        dataContext,
      }),
      cache: "no-store",
    });

    const twinPayload = await twinResponse.json().catch(() => ({}));
    if (!twinResponse.ok) {
      return NextResponse.json(
        {
          transcript,
          error: twinPayload?.error || "Failed to generate assistant response.",
        },
        { status: twinResponse.status || 502 },
      );
    }

    return NextResponse.json({
      transcript,
      reply: String(twinPayload?.reply || "").trim(),
    });
  } catch (error: any) {
    return NextResponse.json(
      { error: error?.message || "Voice pipeline failed." },
      { status: 500 },
    );
  }
}
