"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import Chat from "@/components/Chat";
import Findings from "@/components/Findings";
import Viewer from "@/components/Viewer";
import { ApiError, useApi } from "@/lib/api";
import type { Detail, Focus } from "@/lib/types";

export default function ContractPage() {
  const { id } = useParams<{ id: string }>();
  const { json } = useApi();
  const [detail, setDetail] = useState<Detail | null>(null);
  const [error, setError] = useState("");
  const [tab, setTab] = useState<"chat" | "text">("chat");
  const [text, setText] = useState<string | null>(null);
  const [focus, setFocus] = useState<Focus>(null);

  const load = useCallback(async () => {
    try { setDetail(await json<Detail>(`/api/contracts/${id}`)); setError(""); }
    catch (e) { setError(e instanceof ApiError && e.status === 404 ? "Contract not found." : (e as Error).message); }
  }, [json, id]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (detail?.contract.status !== "processing") return;
    const t = setInterval(load, 2500);
    return () => clearInterval(t);
  }, [detail?.contract.status, load]);
  useEffect(() => {
    if (tab === "text" && text === null && detail && detail.contract.status !== "processing")
      json<{ text: string }>(`/api/contracts/${id}/text`).then((d) => setText(d.text)).catch(() => setText(""));
  }, [tab, text, detail, json, id]);

  const jump = (f: Focus) => { setFocus(f); setTab("text"); };

  if (error) return <main><Link href="/">← All contracts</Link><div className="err" role="alert">{error}</div></main>;
  if (!detail) return <main><div className="skeleton" /><div className="skeleton" /></main>;

  const { contract, reviews, total_items } = detail;
  const processing = contract.status === "processing";

  async function retry() {
    try { await json(`/api/contracts/${id}/review`, { method: "POST" }); await load(); }
    catch (e) { setError((e as Error).message); }
  }

  return (
    <main>
      <Link href="/">← All contracts</Link>
      <h1 style={{ marginTop: 8 }}>{contract.filename} <span className={`badge ${contract.status}`}>{contract.status}</span></h1>
      {processing && (
        <div role="status">
          <span className="muted">Reviewing the contract… {reviews.length} of {total_items} checks done</span>
          <div className="bar"><i style={{ width: `${(reviews.length / total_items) * 100}%` }} /></div>
        </div>
      )}
      {contract.status === "failed" && (
        <div className="err" role="alert">{contract.error} <button className="btn" onClick={retry}>Retry</button></div>
      )}
      <div className="grid">
        <section aria-label="Checklist findings">
          {reviews.length === 0 && !processing
            ? <div className="panel empty">No findings yet.</div>
            : <Findings reviews={reviews} onJump={jump} />}
        </section>
        <aside className="panel side">
          <div className="tabs" role="tablist">
            <button role="tab" aria-selected={tab === "chat"} onClick={() => setTab("chat")}>Chat</button>
            <button role="tab" aria-selected={tab === "text"} onClick={() => setTab("text")}>Contract text</button>
          </div>
          {tab === "chat"
            ? <Chat contractId={id} disabled={processing} onJump={jump} />
            : <Viewer text={processing ? "" : text} focus={focus} />}
        </aside>
      </div>
    </main>
  );
}
