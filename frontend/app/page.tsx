"use client";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { useApi } from "@/lib/api";
import { fmtDate, fmtSize } from "@/lib/format";
import type { Contract } from "@/lib/types";

const MAX = 20 * 1024 * 1024;

export default function Dashboard() {
  const { json } = useApi();
  const [items, setItems] = useState<Contract[] | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [over, setOver] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    try { setItems(await json<Contract[]>("/api/contracts")); setError(""); }
    catch (e) { setError((e as Error).message || "Could not load contracts."); setItems((x) => x ?? []); }
  }, [json]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (!items?.some((c) => c.status === "processing")) return;
    const t = setInterval(load, 3000);
    return () => clearInterval(t);
  }, [items, load]);

  async function upload(file: File | undefined) {
    if (!file) return;
    if (!/\.(pdf|docx|txt)$/i.test(file.name)) return setError("Choose a PDF, DOCX or TXT file.");
    if (file.size > MAX) return setError("The file is larger than 20 MB.");
    setBusy(true); setError("");
    try {
      const body = new FormData(); body.append("file", file);
      await json("/api/contracts", { method: "POST", body });
      await load();
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); if (input.current) input.current.value = ""; }
  }

  async function remove(c: Contract) {
    if (!confirm(`Delete "${c.filename}" and its review and chat?`)) return;
    try { await json(`/api/contracts/${c.id}`, { method: "DELETE" }); await load(); }
    catch (e) { setError((e as Error).message); }
  }

  async function retry(c: Contract) {
    try { await json(`/api/contracts/${c.id}/review`, { method: "POST" }); await load(); }
    catch (e) { setError((e as Error).message); }
  }

  return (
    <main>
      <h1>Your contracts</h1>
      <p className="muted">Upload a contract and check it against the review checklist.</p>
      <div className={`drop ${over ? "over" : ""}`}
        onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)}
        onDrop={(e) => { e.preventDefault(); setOver(false); upload(e.dataTransfer.files[0]); }}>
        <input ref={input} type="file" accept=".pdf,.docx,.txt" hidden onChange={(e) => upload(e.target.files?.[0])} />
        <button className="btn primary" disabled={busy} onClick={() => input.current?.click()}>
          {busy ? "Uploading…" : "Upload contract"}
        </button>
        <div className="muted" style={{ marginTop: 8 }}>or drop a PDF, DOCX or TXT file here (up to 20 MB)</div>
      </div>
      {error && <div className="err" role="alert">{error}</div>}
      <div className="list">
        {items === null && <><div className="skeleton" /><div className="skeleton" /></>}
        {items?.length === 0 && <div className="empty">No contracts yet. Upload one to get started.</div>}
        {items?.map((c) => (
          <div className="row" key={c.id}>
            <div>
              <Link className="name" href={`/contracts/${c.id}`}>{c.filename}</Link>
              <div className="muted">{fmtSize(c.size_bytes)} · {fmtDate(c.created_at)}</div>
              {c.status === "failed" && c.error && <div className="err">{c.error}</div>}
            </div>
            <span className={`badge ${c.status}`}>{c.status}</span>
            {c.status === "failed" ? <button className="btn" onClick={() => retry(c)}>Retry</button> : <span />}
            <button className="btn danger" onClick={() => remove(c)}>Delete</button>
          </div>
        ))}
      </div>
    </main>
  );
}
