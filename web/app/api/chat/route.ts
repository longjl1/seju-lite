import { NextRequest, NextResponse } from "next/server";

type ChatPayload = {
  message: string;
  conversation_id: string;
  user_id?: string;
  metadata?: Record<string, unknown>;
};

export async function POST(request: NextRequest) {
  let payload: ChatPayload;

  try {
    payload = (await request.json()) as ChatPayload;
  } catch {
    return NextResponse.json({ error: "Invalid JSON payload." }, { status: 400 });
  }

  const baseUrl =
    process.env.SEJU_API_BASE_URL?.trim() || "http://127.0.0.1:8000";
  const apiKey = process.env.SEJU_API_KEY?.trim();

  try {
    const response = await fetch(`${baseUrl}/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(apiKey ? { Authorization: `Bearer ${apiKey}` } : {})
      },
      body: JSON.stringify({
        user_id: "web-user",
        metadata: {},
        ...payload
      }),
      cache: "no-store"
    });

    const text = await response.text();

    if (!response.ok) {
      return NextResponse.json(
        { error: text || "Failed to reach seju-lite backend." },
        { status: response.status }
      );
    }

    const data = text ? JSON.parse(text) : {};
    return NextResponse.json(data);
  } catch {
    return NextResponse.json(
      {
        error:
          "Unable to reach the seju-lite API. Start `uv run seju-lite api --config config.json --host 127.0.0.1 --port 8000` first."
      },
      { status: 502 }
    );
  }
}
