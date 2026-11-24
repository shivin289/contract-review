export const fmtSize = (b: number) =>
  b < 1024 ? `${b} B` : b < 1048576 ? `${(b / 1024).toFixed(0)} KB` : `${(b / 1048576).toFixed(1)} MB`;
export const fmtDate = (s: string) =>
  new Date(s).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
export const where = (section: string | null, page: number | null) =>
  [section, page ? `page ${page}` : null].filter(Boolean).join(", ");
