"use client"

import Link from "next/link"
import { WardRiskLatest } from "@/types/risk"

interface Props {
  data: WardRiskLatest[]
}

export default function RiskTable({ data }: Props) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full border border-gray-700 text-sm">
        <thead className="bg-gray-800 text-white">
          <tr>
            <th className="p-2">Ward</th>
            <th className="p-2">Avg %</th>
            <th className="p-2">Max %</th>
            <th className="p-2">Bins ≥ 80%</th>
            <th className="p-2">% Risky</th>
            <th className="p-2">Updated</th>
            <th className="p-2">Action</th>
          </tr>
        </thead>

        <tbody>
          {data.map((row) => (
            <tr key={row.ward} className="border-t border-gray-700 text-center">
              <td className="p-2 font-semibold">{row.ward}</td>
              <td className="p-2">{row.avg_fill_level.toFixed(1)}</td>
              <td className="p-2">{row.max_fill_level}</td>
              <td className="p-2">{row.bins_above_80}</td>
              <td
                className={`p-2 font-bold ${
                  row.pct_bins_above_80 >= 80
                    ? "text-red-500"
                    : row.pct_bins_above_80 >= 60
                    ? "text-yellow-500"
                    : "text-green-500"
                }`}
              >
                {row.pct_bins_above_80.toFixed(1)}%
              </td>
              <td className="p-2">
                {new Date(row.window_end).toLocaleTimeString()}
              </td>
              <td className="p-2">
                <Link
                  href={`/dashboard/ward/${row.ward}`}
                  className="text-blue-400 hover:underline"
                >
                  View
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
