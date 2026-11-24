"use client";
import { useEffect, useRef } from "react";
import type { Focus } from "@/lib/types";

export default function Viewer({ text, focus }: { text: string | null; focus: Focus }) {
  const mark = useRef<HTMLElement>(null);
  useEffect(() => { mark.current?.scrollIntoView({ block: "center", behavior: "smooth" }); }, [focus, text]);
  if (text === null) return <div className="skeleton" />;
  if (!text) return <div className="empty">No text available.</div>;
  if (!focus) return <pre className="doc">{text}</pre>;
  return (
    <pre className="doc">
      {text.slice(0, focus.start)}<mark ref={mark}>{text.slice(focus.start, focus.end)}</mark>{text.slice(focus.end)}
    </pre>
  );
}
