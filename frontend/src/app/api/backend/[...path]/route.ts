import { NextRequest, NextResponse } from "next/server";

const BACKEND_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8014";
const BACKEND_API_KEY = process.env.BACKEND_API_KEY || process.env.API_KEY;
const PROXY_TIMEOUT_MS = 10_000;

async function proxy(request: NextRequest, path: string[]): Promise<NextResponse> {
  const target = new URL(`${BACKEND_BASE.replace(/\/$/, "")}/${path.join("/")}`);
  request.nextUrl.searchParams.forEach((value, key) => {
    target.searchParams.set(key, value);
  });

  const headers = new Headers(request.headers);
  headers.delete("host");
  headers.delete("content-length");

  // Always prefer trusted server-side key over any client-provided key.
  if (BACKEND_API_KEY) {
    headers.set("x-api-key", BACKEND_API_KEY);
  }

  const init: RequestInit = {
    method: request.method,
    headers,
    body: request.method === "GET" || request.method === "HEAD" ? undefined : await request.text(),
  };

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), PROXY_TIMEOUT_MS);

  try {
    const upstream = await fetch(target.toString(), {
      ...init,
      signal: controller.signal,
    });

    if (upstream.status === 401) {
      let upstreamDetail = "Unauthorized";
      try {
        const payload = await upstream.json();
        if (payload?.detail && typeof payload.detail === "string") {
          upstreamDetail = payload.detail;
        }
      } catch {
        // Keep generic detail when upstream body isn't JSON.
      }

      return NextResponse.json(
        {
          error: "Backend authentication failed",
          detail: `${upstreamDetail}. Configure BACKEND_API_KEY in frontend/.env.local to match backend API_KEY, then restart Next.js dev server.`,
          backend: target.origin,
          path: `/${path.join("/")}`,
        },
        { status: 401 }
      );
    }

    const body = await upstream.arrayBuffer();

    return new NextResponse(body, {
      status: upstream.status,
      headers: upstream.headers,
    });
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : "Unknown proxy error";
    const isTimeout = errorMessage.toLowerCase().includes("aborted");

    return NextResponse.json(
      {
        error: "Upstream backend unavailable",
        detail: isTimeout
          ? `Timed out after ${PROXY_TIMEOUT_MS}ms calling ${target.origin}`
          : `Could not reach backend at ${target.origin}`,
        backend: target.origin,
        path: `/${path.join("/")}`,
      },
      { status: 503 }
    );
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> }
): Promise<NextResponse> {
  const { path } = await context.params;
  return proxy(request, path);
}

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> }
): Promise<NextResponse> {
  const { path } = await context.params;
  return proxy(request, path);
}

export async function PUT(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> }
): Promise<NextResponse> {
  const { path } = await context.params;
  return proxy(request, path);
}

export async function DELETE(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> }
): Promise<NextResponse> {
  const { path } = await context.params;
  return proxy(request, path);
}