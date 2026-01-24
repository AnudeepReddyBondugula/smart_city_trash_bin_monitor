"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { WardLatest } from "@/types/ward";

interface Props {
  selectedWard: number;
  onSelectWard: (ward: number) => void;
}

export default function WardLatestTable({ selectedWard, onSelectWard }: Props) {
  const [data, setData] = useState<WardLatest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch("/wards/latest")
      .then(setData)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p>Loading latest ward data…</p>;
  if (error) return <p style={{ color: "red" }}>Error: {error}</p>;
  if (data.length === 0) return <p>No ward data available.</p>;

  return (
    <table width="100%" cellPadding={8} style={{ borderCollapse: "collapse" }}>
      <thead style={{ background: "#f1f5f9" }}>
        <tr>
          <th align="left">Ward</th>
          <th align="left">Avg Fill Level (%)</th>
          <th align="left">Window End</th>
          <th align="left">Latitude</th>
          <th align="left">Longitude</th>
        </tr>
      </thead>
      <tbody>
        {data.map((row) => {
          // 1. Calculate Alert Color logic
          let alertBg = "transparent";
          if (row.avg_fill_level >= 80) {
            alertBg = "#fee2e2";
          } else if (row.avg_fill_level >= 60) {
            alertBg = "#fef9c3";
          }

          // 2. Override with Selection Color if active
          const isSelected = row.ward === selectedWard;
          const finalBg = isSelected ? "#e0e7ff" : alertBg;

          return (
            <tr
              key={row.ward}
              onClick={() => onSelectWard(row.ward)}
              style={{
                cursor: "pointer",
                background: finalBg,
                transition: "background 0.2s ease",
                borderBottom: "1px solid #e2e8f0"
              }}
            >
              <td style={{ fontWeight: isSelected ? "bold" : "normal" }}>
                {row.ward}
              </td>
              <td style={{ 
                color: row.avg_fill_level >= 80 ? "#dc2626" : "inherit",
                fontWeight: row.avg_fill_level >= 60 ? "bold" : "normal"
              }}>
                {row.avg_fill_level.toFixed(1)}%
              </td>
              <td>{new Date(row.window_end).toLocaleString()}</td>
              <td>{row.latitude.toFixed(4)}</td>
              <td>{row.longitude.toFixed(4)}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}