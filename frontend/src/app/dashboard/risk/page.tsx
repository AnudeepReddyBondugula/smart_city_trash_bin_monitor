"use client";

import { useEffect, useState } from "react";
import RiskTable from "@/components/RiskTable";
import CriticalAlert from "@/components/CriticalAlerts";
import { fetchLatestWardRisk } from "@/lib/api";
import { WardRiskLatest } from "@/types/risk";

const THRESHOLD = 80;

export default function RiskDashboardPage() {
  const [data, setData] = useState<WardRiskLatest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function loadData() {
    try {
      const result = await fetchLatestWardRisk(24);
      setData(result);
      setError("");
    } catch (err) {
      console.error("Risk fetch error", err);
      setError("Failed to load risk data");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    // initial fetch
    loadData();

    // poll every 30s for live updates
    const interval = setInterval(loadData, 30_000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return <div className="p-6">Loading risk data...</div>;
  }

  if (error) {
    return <div className="p-6 text-red-500">{error}</div>;
  }

  if (!data || data.length === 0) {
    return <div className="p-6">✅ System healthy — no wards at risk</div>;
  }

  // 🔎 Identify critical wards based on threshold
  const criticalWards = data.filter(
    (w) =>
      w.avg_fill_level >= THRESHOLD ||
      w.pct_bins_above_80 >= THRESHOLD
  );

  return (
    <div className="p-6 space-y-4">
      {/* 🔴 ALERT BANNER */}
      <CriticalAlert wards={criticalWards} />

      <h1 className="text-2xl font-bold">🚨 Ward Risk Overview</h1>
      <RiskTable data={data} />
    </div>
  );
}
