"use client";
import { useState } from "react";
import { where } from "@/lib/format";
import type { Focus, Review } from "@/lib/types";

export default function Findings({ reviews, onJump }: { reviews: Review[]; onJump: (f: Focus) => void }) {
  const [open, setOpen] = useState<string | null>(null);
  return (
    <div className="panel">
      {reviews.map((r) => (
        <article className="finding" key={r.item_key}>
          <h3>{r.label}<span className={`badge ${r.status.replace(" ", "-")}`}>{r.status}</span></h3>
          <p>{r.summary}</p>
          {r.status === "not found" && <p className="where">Not found in the contract.</p>}
          {r.quote && (
            <>
              <button className="quote" aria-expanded={open === r.item_key}
                onClick={() => setOpen(open === r.item_key ? null : r.item_key)}>“{r.quote}”</button>
              <div className="where">{where(r.section_label, r.page_start)}</div>
              {open === r.item_key && (
                <>
                  <div className="clause">{r.clause_text}</div>
                  {r.char_start != null && r.char_end != null && (
                    <button className="link" onClick={() => onJump({ start: r.char_start!, end: r.char_end! })}>
                      Show in contract
                    </button>
                  )}
                </>
              )}
            </>
          )}
        </article>
      ))}
    </div>
  );
}
