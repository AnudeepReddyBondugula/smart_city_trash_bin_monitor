"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid
} from "recharts";



export default function WardRiskHistory() {
  const { wardId } = useParams();
  const [data, setData] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {

    fetch(`http://localhost:8000/wards/${wardId}/risk/history?hours=24`, {
      credentials: "include",
    })
      .then((res) => res.json())
      .then((json) => {
        // Sort data by time so the chart line flows correctly
        const sortedData = json.sort((a: any, b: any) => 
            new Date(a.window_end).getTime() - new Date(b.window_end).getTime()
        );
        setData(sortedData);
      })
      .catch((err) => console.error("History fetch error:", err))
      .finally(() => setLoading(false));
  }, [wardId]);


  if (loading) return <div className="p-6">Loading history...</div>;

  // console.log("Ward Risk History Data:", {data});
  return (
    <div className="p-6">
      {/* 1. Chart Section */}
      <section>
        <h1 className="text-xl font-bold mb-4">
          📈 Ward {wardId} — Risk Trend (24h)
        </h1>
          <ResponsiveContainer width="98%" height={300}>
            <LineChart data={data}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis 
                dataKey="window_end" 
                tickFormatter={(str) => new Date(str).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                fontSize={12}
              />
              <YAxis fontSize={12} unit="%" />
              <Tooltip 
                labelFormatter={(value) => new Date(value).toLocaleString()}
                contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
              />
              <Line
                type="monotone"
                dataKey="pct_bins_above_80"
                name="Risk Index"
                stroke="#dc5c0c"
                strokeWidth={2}
                dot={{ r: 4 }}
                activeDot={{ r: 6 }}
              />
            </LineChart>
          </ResponsiveContainer>
      </section>


      <br />
      {/* 2. Data Table Section */}
      <h1 className="text-xl font-bold mb-4">
        📊 Ward {wardId} — Fill Level History (24h)
      </h1>
      <div className="overflow-x-auto">
        <table className="w-full text-sm border-collapse mx-auto">
          <thead className="bg-slate-100">
            <tr>
              <th className="p-3 border text-center">Avg Fill (%)</th>
              <th className="p-3 border text-center">Max Fill (%)</th>
              <th className="p-3 border text-center">Min Fill (%)</th>
              <th className="p-3 border text-center">Bins {'>'} 80%</th>
              <th className="p-3 border text-center">Total Bins</th>
              <th className="p-3 border text-center">Risk Index (%)</th>
              <th className="p-3 border text-center">Window End</th>
            </tr>
          </thead>
          <tbody>
            {data.map((row, idx) => (
              <tr key={idx} className="hover:bg-slate-50 even:bg-slate-50/50">
                <td className="p-3 border text-center">{row.avg_fill_level.toFixed(1)}</td>
                <td className="p-3 border text-center">{row.max_fill_level.toFixed(1)}</td>
                <td className="p-3 border text-center">{row.min_fill_level.toFixed(1)}</td>
                <td className="p-3 border text-center font-semibold">{row.bins_above_80}</td>
                <td className="p-3 border text-center">{row.total_bins}</td>
                <td className="p-3 border text-center text-red-600 font-bold">{row.pct_bins_above_80.toFixed(1)}%</td>
                <td className="p-3 border text-center whitespace-nowrap">
                  {new Date(row.window_end).toLocaleString()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

