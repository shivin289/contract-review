export type Contract = {
  id: string; filename: string; size_bytes: number; status: "processing" | "reviewed" | "failed";
  error: string | null; created_at: string;
};
export type Review = {
  item_key: string; label: string; status: "found" | "not found" | "unclear"; summary: string;
  quote: string | null; section_label: string | null; page_start: number | null;
  clause_text: string | null; char_start: number | null; char_end: number | null;
};
export type Detail = { contract: Contract; reviews: Review[]; total_items: number };
export type Citation = {
  quote: string; verified: boolean; section_label: string | null; page: number | null;
  clause_text: string | null; char_start: number | null; char_end: number | null;
};
export type Message = { id?: number; role: "user" | "assistant"; content: string; citations: Citation[] };
export type Focus = { start: number; end: number } | null;
