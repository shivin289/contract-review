"use client";
import { useEffect, useRef, useState } from "react";
import { useApi } from "@/lib/api";
import { where } from "@/lib/format";
import type { Citation, Focus, Message } from "@/lib/types";

export default function Chat({ contractId, disabled, onJump }: {
  contractId: string; disabled: boolean; onJump: (f: Focus) => void;
}) {
  const { call, json } = useApi();
  const [msgs, setMsgs] = useState<Message[] | null>(null);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [shown, setShown] = useState<string | null>(null);
  const end = useRef<HTMLDivElement>(null);

  useEffect(() => {
    json<Message[]>(`/api/contracts/${contractId}/messages`).then(setMsgs).catch(() => setMsgs([]));
  }, [json, contractId]);
  useEffect(() => { end.current?.scrollIntoView({ block: "end" }); }, [msgs]);

  async function send() {
    const q = text.trim();
    if (!q || busy || disabled) return;
    setText(""); setError(""); setBusy(true);
    setMsgs((m) => [...(m ?? []), { role: "user", content: q, citations: [] }, { role: "assistant", content: "", citations: [] }]);
    const patch = (fn: (m: Message) => Message) =>
      setMsgs((all) => all!.map((m, i) => (i === all!.length - 1 ? fn(m) : m)));
    try {
      const res = await call(`/api/contracts/${contractId}/chat`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message: q }),
      });
      if (!res.ok || !res.body) {
        let d = "Could not send the message."; try { d = (await res.json()).detail ?? d; } catch {}
        throw new Error(d);
      }
      const reader = res.body.getReader(); const dec = new TextDecoder(); let buf = "";
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const events = buf.split("\n\n"); buf = events.pop() ?? "";
        for (const ev of events) {
          if (!ev.startsWith("data: ")) continue;
          const d = JSON.parse(ev.slice(6));
          if (d.token) patch((m) => ({ ...m, content: m.content + d.token }));
          if (d.done) patch((m) => ({ ...m, content: d.answer, citations: d.citations }));
          if (d.error) throw new Error(d.error);
        }
      }
    } catch (e) {
      setError((e as Error).message);
      setMsgs((all) => (all![all!.length - 1].content ? all : all!.slice(0, -1)));
    } finally { setBusy(false); }
  }

  const cite = (c: Citation, key: string) => (
    <div key={key} className={c.verified ? "cite" : "cite bad"}>
      {c.verified ? (
        <>
          <button className="link" onClick={() => setShown(shown === key ? null : key)}>
            “{c.quote.length > 70 ? c.quote.slice(0, 70) + "…" : c.quote}”
          </button>{" "}<span className="where">{where(c.section_label, c.page)}</span>
          {shown === key && (
            <>
              <div className="clause">{c.clause_text}</div>
              {c.char_start != null && c.char_end != null &&
                <button className="link" onClick={() => onJump({ start: c.char_start!, end: c.char_end! })}>Show in contract</button>}
            </>
          )}
        </>
      ) : <>Quote not found in the contract: “{c.quote}”</>}
    </div>
  );

  return (
    <div className="chat">
      <div className="msgs" aria-live="polite">
        {msgs === null && <div className="skeleton" />}
        {msgs?.length === 0 && <div className="empty">Ask a question about this contract. Answers come only from its text.</div>}
        {msgs?.map((m, i) => (
          <div key={m.id ?? i} className={`msg ${m.role}`}>
            {m.content || (busy && i === msgs.length - 1 ? "…" : "")}
            {m.citations?.length > 0 && <div className="cites">{m.citations.map((c, j) => cite(c, `${i}-${j}`))}</div>}
          </div>
        ))}
        <div ref={end} />
      </div>
      {error && <div className="err" style={{ padding: "0 16px" }} role="alert">{error}</div>}
      <div className="ask">
        <input value={text} placeholder={disabled ? "Available once the review finishes" : "Ask about this contract"}
          disabled={disabled || busy} maxLength={2000} aria-label="Question"
          onChange={(e) => setText(e.target.value)} onKeyDown={(e) => e.key === "Enter" && send()} />
        <button className="btn primary" disabled={disabled || busy || !text.trim()} onClick={send}>Ask</button>
      </div>
    </div>
  );
}
