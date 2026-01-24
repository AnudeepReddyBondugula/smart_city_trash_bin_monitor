"use client";

import { useEffect, useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { apiFetch } from "@/lib/api";
import { WardHistory } from "@/types/ward";

interface Props {
  wardId: number;
  hours: number;
}

export default function WardHistoryChart({ wardId, hours }: Props) {
  const [data, setData] = useState<WardHistory[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);

    apiFetch(`/wards/${wardId}/history?hours=${hours}`)
      .then(setData)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [wardId, hours]);

  if (loading) return <p>Loading ward history…</p>;
  if (error) return <p style={{ color: "red" }}>Error: {error}</p>;
  if (data.length === 0) return <p>No history data available.</p>;

  return (
    <div style={{ width: "100%", height: 300 }}>
      <ResponsiveContainer>
        <LineChart data={data}>
          <XAxis
            dataKey="window_end"
            tickFormatter={(v) => new Date(v).toLocaleTimeString()}
          />
          <YAxis domain={[0, 100]} />
          <Tooltip
            labelFormatter={(v) => new Date(v as string).toLocaleString()}
          />
          <Line
            type="monotone"
            dataKey="avg_fill_level"
            stroke="#2563eb"
            strokeWidth={2}
            dot={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
