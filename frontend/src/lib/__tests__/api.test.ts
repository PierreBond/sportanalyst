import { getReportPDF, getWebSocketUrl } from "@/lib/api";

describe("getWebSocketUrl", () => {
  it("derives the ws url from the page hostname and backend's published port", () => {
    // jsdom location is http://localhost/
    expect(getWebSocketUrl("match-1")).toBe("ws://localhost:8005/ws/live/match-1");
  });

  it("honors NEXT_PUBLIC_WS_URL override", () => {
    const original = process.env.NEXT_PUBLIC_WS_URL;
    process.env.NEXT_PUBLIC_WS_URL = "wss://api.example.com/ws-base";
    try {
      expect(getWebSocketUrl("match-1")).toBe("wss://api.example.com/ws-base/ws/live/match-1");
    } finally {
      if (original === undefined) {
        delete process.env.NEXT_PUBLIC_WS_URL;
      } else {
        process.env.NEXT_PUBLIC_WS_URL = original;
      }
    }
  });
});

describe("getReportPDF", () => {
  const originalFetch = global.fetch;

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("returns the blob when the backend answers with a PDF", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      headers: new Headers({ "content-type": "application/pdf" }),
      blob: async () => new Blob(["%PDF-"], { type: "application/pdf" }),
    }) as unknown as typeof fetch;

    const blob = await getReportPDF("match-1");
    expect(blob.type).toBe("application/pdf");
  });

  it("throws instead of saving JSON as a .pdf", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      headers: new Headers({ "content-type": "application/json" }),
      blob: async () => new Blob(["{}"], { type: "application/json" }),
    }) as unknown as typeof fetch;

    await expect(getReportPDF("match-1")).rejects.toThrow(/application\/json/);
  });
});
