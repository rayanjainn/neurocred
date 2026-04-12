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

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const to = String(body?.to || "").trim();
    const userId = String(body?.userId || "").trim();
    const userName = String(body?.userName || "").trim();

    if (!to) {
      return NextResponse.json(
        { error: "Phone number is required" },
        { status: 400 },
      );
    }

    const backends = resolveBackendCandidates();
    let lastNetworkError: string | null = null;

    for (const backend of backends) {
      try {
        const response = await fetch(`${backend}/voice/call/start`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ to, userId, userName }),
          cache: "no-store",
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
        lastNetworkError = error?.message || "Network error while contacting backend";
      }
    }

    return NextResponse.json(
      { error: lastNetworkError || "Could not reach backend voice API" },
      { status: 502 },
    );
  } catch (error: any) {
    return NextResponse.json(
      { error: error?.message || "Failed to start voice call" },
      { status: 500 },
    );
  }
}
