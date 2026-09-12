"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import type { WebSocketMessage } from "@/types";

interface UseWebSocketOptions {
  onMessage?: (message: WebSocketMessage) => void;
  onOpen?: () => void;
  onClose?: () => void;
  onError?: (error: Event) => void;
}

interface UseWebSocketReturn {
  isConnected: boolean;
  lastMessage: WebSocketMessage | null;
  connect: (url: string) => void;
  disconnect: () => void;
  send: (data: string) => void;
}

export function useWebSocket(options?: UseWebSocketOptions): UseWebSocketReturn {
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const optionsRef = useRef(options);
  optionsRef.current = options;

  const connect = useCallback((url: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    const ws = new WebSocket(url);

    ws.onopen = () => {
      setIsConnected(true);
      optionsRef.current?.onOpen?.();
    };

    ws.onclose = () => {
      setIsConnected(false);
      optionsRef.current?.onClose?.();
    };

    ws.onerror = (error) => {
      optionsRef.current?.onError?.(error);
    };

    ws.onmessage = (event) => {
      try {
        const message: WebSocketMessage = JSON.parse(event.data);
        setLastMessage(message);
        optionsRef.current?.onMessage?.(message);
      } catch {
        console.error("Failed to parse WebSocket message");
      }
    };

    wsRef.current = ws;
  }, []);

  const disconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  }, []);

  const send = useCallback((data: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(data);
    }
  }, []);

  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  return {
    isConnected,
    lastMessage,
    connect,
    disconnect,
    send,
  };
}
