import { useEffect, useRef, useState } from "react";
import React from "react";

type Msg = { role: "user" | "assistant" | "system"; text: string; sources?: string[] };

type ProposedAction = { tool: string; arguments: Record<string, unknown>; rationale: string };

type ChatResponse = {
  session_id: string;
  status: "completed" | "awaiting_confirmation";
  answer?: string;
  context?: { source?: string }[];
  proposed_action?: ProposedAction;
  tool_result?: { tool: string; output: unknown; error?: string | null };
};

const sessionId = crypto.randomUUID();

export default function App() {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState<ProposedAction | null>(null);
  const [argsDraft, setArgsDraft] = useState<string>("{}");
  const [health, setHealth] = useState<string>("…");
  const [toolCount, setToolCount] = useState<string>("");
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetch("/api/health")
      .then((r) => r.json())
      .then((h) => setHealth(`backend ok · opensearch ${h.opensearch}`))
      .catch(() => setHealth("backend unreachable"));
    fetch("/api/tools")
      .then((r) => r.json())
      .then((d) => {
        const tools = d.tools ?? [];
        const mcp = tools.filter((t: { source: string }) => t.source.startsWith("mcp")).length;
        setToolCount(`${tools.length} tools (${mcp} via MCP)`);
      })
      .catch(() => setToolCount(""));
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, pending]);

  function handleResponse(data: ChatResponse) {
    if (data.status === "awaiting_confirmation" && data.proposed_action) {
      setPending(data.proposed_action);
      setArgsDraft(JSON.stringify(data.proposed_action.arguments ?? {}, null, 2));
      setMessages((m) => [
        ...m,
        {
          role: "system",
          text: `Agent wants to run tool "${data.proposed_action.tool}". Reason: ${data.proposed_action.rationale}`,
        },
      ]);
      return;
    }
    setPending(null);
    const sources = (data.context ?? []).map((d) => d.source).filter(Boolean) as string[];
    const tr = data.tool_result;
    const trText = tr ? `\n(tool ${tr.tool} → ${JSON.stringify(tr.output)})` : "";
    setMessages((m) => [
      ...m,
      { role: "assistant", text: (data.answer ?? "") + trText, sources },
    ]);
  }

  async function send() {
    const text = input.trim();
    if (!text || busy || pending) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", text }]);
    setBusy(true);
    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, message: text }),
      });
      if (!res.ok) throw new Error(await res.text());
      handleResponse(await res.json());
    } catch (e) {
      setMessages((m) => [...m, { role: "assistant", text: `Error: ${e}` }]);
    } finally {
      setBusy(false);
    }
  }

  async function confirm(approved: boolean) {
    if (!pending) return;
    setBusy(true);
    let argsOverride: Record<string, unknown> | undefined;
    if (approved) {
      try {
        argsOverride = JSON.parse(argsDraft);
      } catch {
        setMessages((m) => [...m, { role: "system", text: "Arguments must be valid JSON." }]);
        setBusy(false);
        return;
      }
    }
    try {
      const res = await fetch("/api/confirm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          approved,
          arguments: approved ? argsOverride : undefined,
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      handleResponse(await res.json());
    } catch (e) {
      setMessages((m) => [...m, { role: "assistant", text: `Error: ${e}` }]);
    } finally {
      setBusy(false);
    }
  }

  const roleColor = (r: Msg["role"]) =>
    r === "user" ? "#2563eb" : r === "assistant" ? "#16a34a" : "#a16207";

  return (
    <div style={{ fontFamily: "system-ui", maxWidth: 760, margin: "0 auto", padding: 24 }}>
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <h1 style={{ margin: 0 }}>AI Agent Chatbot</h1>
        <small style={{ color: "#666" }}>
          {health}
          {toolCount ? ` · ${toolCount}` : ""}
        </small>
      </header>
      <p style={{ color: "#666" }}>Phase 4 — retrieval + planning + confirmation + MCP tools.</p>

      <div
        style={{
          border: "1px solid #ddd",
          borderRadius: 8,
          padding: 12,
          height: 460,
          overflowY: "auto",
          background: "#fafafa",
        }}
      >
        {messages.length === 0 && <p style={{ color: "#999" }}>Ask something to begin…</p>}
        {messages.map((m, i) => (
          <div key={i} style={{ margin: "10px 0" }}>
            <div style={{ fontWeight: 600, color: roleColor(m.role) }}>
              {m.role === "user" ? "You" : m.role === "assistant" ? "Assistant" : "System"}
            </div>
            <div style={{ whiteSpace: "pre-wrap" }}>{m.text}</div>
            {m.sources && m.sources.length > 0 && (
              <div style={{ marginTop: 4, fontSize: 12, color: "#666" }}>
                sources: {m.sources.join(", ")}
              </div>
            )}
          </div>
        ))}
        <div ref={endRef} />
      </div>

      {pending && (
        <div
          style={{
            border: "1px solid #f59e0b",
            background: "#fffbeb",
            borderRadius: 8,
            padding: 12,
            marginTop: 12,
          }}
        >
          <div style={{ fontWeight: 700 }}>Confirm tool execution</div>
          <div>
            <b>Tool:</b> {pending.tool}
          </div>
          <div style={{ fontSize: 13, color: "#555", margin: "4px 0" }}>{pending.rationale}</div>
          <label style={{ fontSize: 12 }}>Arguments (JSON, editable):</label>
          <textarea
            value={argsDraft}
            onChange={(e) => setArgsDraft(e.target.value)}
            rows={4}
            style={{ width: "100%", fontFamily: "ui-monospace, monospace", marginTop: 4 }}
          />
          <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
            <button
              onClick={() => confirm(true)}
              disabled={busy}
              style={{ padding: "8px 14px", background: "#16a34a", color: "#fff", border: 0, borderRadius: 6 }}
            >
              Approve & Run
            </button>
            <button
              onClick={() => confirm(false)}
              disabled={busy}
              style={{ padding: "8px 14px", background: "#dc2626", color: "#fff", border: 0, borderRadius: 6 }}
            >
              Decline
            </button>
          </div>
        </div>
      )}

      <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
        <input
          style={{ flex: 1, padding: 10, borderRadius: 6, border: "1px solid #ccc" }}
          value={input}
          placeholder={pending ? "Resolve the pending confirmation first…" : "Ask a question…"}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          disabled={busy || !!pending}
        />
        <button
          onClick={send}
          disabled={busy || !input.trim() || !!pending}
          style={{ padding: "10px 16px", borderRadius: 6, border: 0, background: "#111", color: "#fff" }}
        >
          {busy ? "…" : "Send"}
        </button>
      </div>
    </div>
  );
}
