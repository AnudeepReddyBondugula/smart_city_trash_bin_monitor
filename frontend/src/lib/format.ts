export function riskColor(pct: number) {
  if (pct >= 80) return "red"
  if (pct >= 60) return "orange"
  return "green"
}
