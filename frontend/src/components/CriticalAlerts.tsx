"use client";
import { RiskWard } from "@/types/risk";

export default function CriticalAlert({wards}: {wards: RiskWard[];}) {
  if (wards.length === 0) return null;

  return (
    <div className="mb-4 rounded-md border border-red-600 bg-red-100 px-4 py-3 text-red-900">
      <h2 className="font-bold text-lg">
        🚨 Critical Alert
      </h2>

      <p className="mt-1">
        {wards.length} ward(s) are in critical condition.
      </p>

      <ul className="mt-2 list-disc list-inside text-sm">
        {wards.map((w) => (
          <li key={w.ward}>
            Ward {w.ward} — Avg Fill:{" "}
            <b>{w.avg_fill_level.toFixed(1)}%</b>, Bins ≥80%:{" "}
            <b>{w.pct_bins_above_80.toFixed(0)}%</b>
          </li>
        ))}
      </ul>
    </div>
  );
}
