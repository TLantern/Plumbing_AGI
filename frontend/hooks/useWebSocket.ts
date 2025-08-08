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
  const [connected, setConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);

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
          onOpen?.();
        };
        ws.onmessage = (ev) => {
          try {
            const data = JSON.parse(ev.data);
            setLastMessage(data);
            onMessage?.(data);
          } catch (_e) {
            // ignore
          }
        };
        ws.onerror = (ev) => {
          setError('WebSocket error');
          onError?.(ev);
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
  }, [url, enabled, onMessage, onOpen, onError]);

  return { connected, lastMessage, error };
} 