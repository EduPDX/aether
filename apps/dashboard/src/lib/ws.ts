/** Shared WebSocket client with topic subscriptions and auto-reconnect. */

export interface WsMessage {
  topic: string;
  payload: Record<string, unknown>;
  ts: string;
  seq: number;
}

type Listener = (msg: WsMessage) => void;

let socket: WebSocket | null = null;
let reconnectTimer: number | undefined;
const listeners = new Map<string, Set<Listener>>();

function url(): string {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${location.host}/ws`;
}

function connect() {
  if (socket && socket.readyState !== WebSocket.CLOSED) return;
  socket = new WebSocket(url());

  socket.onopen = () => {
    for (const topic of listeners.keys()) {
      socket?.send(JSON.stringify({ op: "subscribe", topic }));
    }
  };
  socket.onmessage = (ev) => {
    const msg: WsMessage = JSON.parse(ev.data);
    for (const [topic, set] of listeners) {
      if (msg.topic.startsWith(topic)) for (const fn of set) fn(msg);
    }
  };
  socket.onclose = () => {
    if (listeners.size > 0) {
      clearTimeout(reconnectTimer);
      reconnectTimer = window.setTimeout(connect, 2000);
    }
  };
}

/** Subscribe to a topic prefix; returns an unsubscribe function. */
export function subscribeTopic(topic: string, fn: Listener): () => void {
  let set = listeners.get(topic);
  if (!set) {
    set = new Set();
    listeners.set(topic, set);
    connect();
    if (socket?.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ op: "subscribe", topic }));
    }
  }
  set.add(fn);

  return () => {
    const s = listeners.get(topic);
    s?.delete(fn);
    if (s && s.size === 0) {
      listeners.delete(topic);
      if (socket?.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ op: "unsubscribe", topic }));
      }
    }
  };
}
