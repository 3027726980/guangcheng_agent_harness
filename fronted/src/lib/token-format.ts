/** Compact display only: k = 1,000 tokens; m = 1,000,000 tokens. */
export function formatTokenCount(value: number): string {
  if (!Number.isFinite(value) || value < 0) return "—";
  if (value < 1000) return String(Math.round(value));
  const thousands = Number((value / 1000).toFixed(1));
  if (thousands < 1000) return `${thousands}k`;
  return `${Number((value / 1_000_000).toFixed(1))}m`;
}
