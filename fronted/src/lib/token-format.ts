// 作者：LHF。
// 注释维护时间：2026-10-20。
// 文件作用：以简短单位展示 token 数量。
/** 仅缩短显示：k 表示千、m 表示百万 tokens，不改变实际预算或存储数值。 */
export function formatTokenCount(value: number): string {
  // 作用：将 token 数量转换为千进制显示，异常数值显示未知。
  if (!Number.isFinite(value) || value < 0) return "—";
  if (value < 1000) return String(Math.round(value));
  const thousands = Number((value / 1000).toFixed(1));
  if (thousands < 1000) return `${thousands}k`;
  return `${Number((value / 1_000_000).toFixed(1))}m`;
}
