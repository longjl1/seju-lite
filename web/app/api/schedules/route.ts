import { NextResponse } from "next/server";

export async function GET() {
  const baseUrl = process.env.SEJU_API_BASE_URL?.trim() || "http://127.0.0.1:8000";
  const apiKey = process.env.SEJU_API_KEY?.trim();

  try {
    const response = await fetch(`${baseUrl}/schedules`, {
      method: "GET",
      headers: {
        ...(apiKey ? { Authorization: `Bearer ${apiKey}` } : {})
      },
      cache: "no-store"
    });

    const text = await response.text();
    if (!response.ok) {
      return NextResponse.json(
        { error: text || "Failed to fetch schedules." },
        { status: response.status }
      );
    }

    const data = text ? JSON.parse(text) : [];
    return NextResponse.json(data);
  } catch {
    return NextResponse.json(
      { error: "Unable to reach the seju-lite schedules API." },
      { status: 502 }
    );
  }
}
