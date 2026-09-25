import { getWebSocketUrl } from "@/lib/api";

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
