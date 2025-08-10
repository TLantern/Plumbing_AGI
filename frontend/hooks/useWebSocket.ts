import { useEffect, useRef, useState } from 'react';

interface Options<T> {
  onMessage?: (data: T) => void;
  onOpen?: () => void;
  onError?: (err: Event) => void;
  enabled?: boolean;
}

export function useWebSocket<T = any>(url: string | null, opts: Options<T> = {}) {
  const { onMessage, onOpen, onError, enabled = true } = opts;
  const wsRef = useRef<WebSocket | null>(null);
  // Keep latest handlers in refs so the socket doesn't reconnect on each render
  const handlersRef = useRef<{ onMessage?: Options<T>['onMessage']; onOpen?: Options<T>['onOpen']; onError?: Options<T>['onError'] }>({ onMessage, onOpen, onError });
  const [connected, setConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Update handler refs when callbacks change without triggering reconnection
  useEffect(() => {
    handlersRef.current.onMessage = onMessage;
    handlersRef.current.onOpen = onOpen;
    handlersRef.current.onError = onError;
  }, [onMessage, onOpen, onError]);

  useEffect(() => {
    if (!url || !enabled) return;

    let stopped = false;
    let retry = 0;

    const connect = () => {
      if (stopped) return;
      try {
        const ws = new WebSocket(url);
        wsRef.current = ws;
        ws.onopen = () => {
          setConnected(true);
          setError(null);
          retry = 0;
          handlersRef.current.onOpen?.();
        };
        ws.onmessage = (ev) => {
          try {
            const data = JSON.parse(ev.data);
            setLastMessage(data);
            handlersRef.current.onMessage?.(data);
          } catch (_e) {
            // ignore
          }
        };
        ws.onerror = (ev) => {
          setError('WebSocket error');
          handlersRef.current.onError?.(ev);
        };
        ws.onclose = () => {
          setConnected(false);
          if (!stopped) {
            retry += 1;
            const backoff = Math.min(10000, 500 * 2 ** retry);
            setTimeout(connect, backoff);
          }
        };
      } catch (e) {
        setError('WebSocket failed to connect');
      }
    };

    connect();
    return () => {
      stopped = true;
      wsRef.current?.close();
    };
  }, [url, enabled]);

  const sendJson = (data: any) => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return false;
    try {
      ws.send(JSON.stringify(data));
      return true;
    } catch {
      return false;
    }
  };

  return { connected, lastMessage, error, sendJson };
} 