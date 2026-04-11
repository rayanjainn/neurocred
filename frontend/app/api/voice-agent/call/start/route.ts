import { NextResponse } from "next/server";

function resolveBackendBase(): string {
  const raw =
    process.env.BACKEND_API_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    "http://localhost:8001";

  const value = raw.trim();
  if (!value || value.startsWith("/")) {
    return "http://localhost:8001";
  }
  return value.replace(/\/$/, "");
}

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const to = String(body?.to || "").trim();
    const userId = String(body?.userId || "").trim();

    if (!to) {
      return NextResponse.json(
        { error: "Phone number is required" },
        { status: 400 },
      );
    }

    const backend = resolveBackendBase();
    const response = await fetch(`${backend}/voice/call/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ to, userId }),
    });

    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      return NextResponse.json(
        { error: payload?.detail || payload?.error || "Failed to start call" },
        { status: response.status },
      );
    }

    return NextResponse.json(payload);
  } catch (error: any) {
    return NextResponse.json(
      { error: error?.message || "Failed to start voice call" },
      { status: 500 },
    );
  }
}
