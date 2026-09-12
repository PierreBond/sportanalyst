import { renderHook, act, waitFor } from "@testing-library/react";
import { useWebSocket } from "../ws";

describe("useWebSocket", () => {
  let originalWebSocket: typeof WebSocket;
  let originalWindowWebSocket: typeof WebSocket;
  let lastSocket: {
    readyState: number;
    onopen: ((event: Event) => void) | null;
    onclose: ((event: CloseEvent) => void) | null;
    onerror: ((event: Event) => void) | null;
    onmessage: ((event: MessageEvent) => void) | null;
    send: jest.Mock;
    close: jest.Mock;
    addEventListener: jest.Mock;
    removeEventListener: jest.Mock;
  } | null;

  beforeEach(() => {
    jest.useFakeTimers();
    originalWebSocket = global.WebSocket;
    originalWindowWebSocket = window.WebSocket;

    const wsMock = jest.fn().mockImplementation(() => {
      lastSocket = {
        readyState: 1,
        onopen: null as ((event: Event) => void) | null,
        onclose: null as ((event: CloseEvent) => void) | null,
        onerror: null as ((event: Event) => void) | null,
        onmessage: null as ((event: MessageEvent) => void) | null,
        send: jest.fn(),
        close: jest.fn(),
        addEventListener: jest.fn(),
        removeEventListener: jest.fn(),
      };

      return lastSocket;
    }) as unknown as typeof WebSocket;

    (wsMock as unknown as { OPEN: number }).OPEN = 1;
    global.WebSocket = wsMock;
    window.WebSocket = wsMock;
  });

  afterEach(() => {
    jest.useRealTimers();
    global.WebSocket = originalWebSocket;
    window.WebSocket = originalWindowWebSocket;
  });

  it("initializes with disconnected state", () => {
    const { result } = renderHook(() => useWebSocket());

    expect(result.current.isConnected).toBe(false);
    expect(result.current.lastMessage).toBeNull();
  });

  it("updates lastMessage when message is received", async () => {
    const onMessage = jest.fn();
    const { result } = renderHook(() => useWebSocket({ onMessage }));
    const message = {
      type: "prediction_update",
      match_id: "test-123",
      minute: 42,
      trigger: "periodic",
      probabilities: {
        home_win: 0.5,
        draw: 0.3,
        away_win: 0.2,
      },
      timestamp: "2026-03-23T10:00:00Z",
    };

    act(() => {
      result.current.connect("ws://localhost:8080/ws/live/test-123");
      lastSocket?.onmessage?.({ data: JSON.stringify(message) } as MessageEvent);
    });

    await waitFor(() => {
      expect(result.current.lastMessage).toEqual(message);
      expect(onMessage).toHaveBeenCalledWith(message);
    });
  });
});
