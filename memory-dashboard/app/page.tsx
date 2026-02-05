"use client";

import { useEffect, useState } from "react";
import { KpiCard } from "@/components/kpi-card";
import { CategoryChart } from "@/components/category-chart";
import { UsageChart } from "@/components/usage-chart";

interface DashboardStats {
  totalProjects: number;
  totalEvents: number;
  totalInjections: number;
  totalCitations: number;
  effectivenessRate: number;
  categoryBreakdown: { category: string; count: number; cited: number }[];
  scoreDistribution: { bucket: string; count: number }[];
}

export default function Home() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [lastSync, setLastSync] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchStats = async () => {
    try {
      const res = await fetch("/api/stats");
      if (!res.ok) throw new Error("Failed to fetch stats");
      const data = await res.json();
      setStats(data);
      setError(null);
    } catch (err) {
      setError(String(err));
    }
  };

  const syncData = async () => {
    setSyncing(true);
    try {
      const res = await fetch("/api/sync", { method: "POST" });
      const data = await res.json();
      if (data.success) {
        setLastSync(data.lastSync);
        await fetchStats();
      } else {
        setError(data.error || "Sync failed");
      }
    } catch (err) {
      setError(String(err));
    }
    setSyncing(false);
  };

  useEffect(() => {
    // Check last sync time and auto-sync if needed
    const init = async () => {
      const res = await fetch("/api/sync");
      const data = await res.json();
      setLastSync(data.lastSync);
      if (!data.lastSync) {
        setSyncing(true);
        const syncRes = await fetch("/api/sync", { method: "POST" });
        const syncData = await syncRes.json();
        if (syncData.success) {
          setLastSync(syncData.lastSync);
        }
        setSyncing(false);
      }
      fetchStats();
    };
    init();
  }, []);

  return (
    <div className="space-y-8">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
            Memory Health
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Cross-project memory system telemetry
          </p>
        </div>
        <div className="flex items-center gap-4">
          {lastSync && (
            <span className="text-sm text-gray-500 dark:text-gray-400">
              Last sync: {new Date(lastSync).toLocaleString()}
            </span>
          )}
          <button
            onClick={syncData}
            disabled={syncing}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white rounded-md text-sm font-medium transition-colors"
          >
            {syncing ? "Syncing..." : "Sync Now"}
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
          <p className="text-red-800 dark:text-red-200">{error}</p>
        </div>
      )}

      {stats ? (
        <>
          {/* KPI Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <KpiCard
              title="Projects"
              value={stats.totalProjects}
              subtitle="with memories"
            />
            <KpiCard
              title="Memories"
              value={stats.totalEvents}
              subtitle="total events"
            />
            <KpiCard
              title="Injections"
              value={stats.totalInjections.toLocaleString()}
              subtitle="times surfaced"
            />
            <KpiCard
              title="Effectiveness"
              value={`${stats.effectivenessRate}%`}
              subtitle="cited as helpful"
              trend={
                stats.effectivenessRate > 30
                  ? "up"
                  : stats.effectivenessRate > 15
                  ? "neutral"
                  : "down"
              }
            />
          </div>

          {/* Charts */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <CategoryChart data={stats.categoryBreakdown} />
            <UsageChart data={stats.scoreDistribution} />
          </div>

          {/* Quick Stats */}
          <div className="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-800 p-6">
            <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-4">
              Injection Funnel
            </h3>
            <div className="flex items-center justify-between">
              <div className="flex-1">
                <div className="flex items-center">
                  <div className="flex-1 bg-gray-200 dark:bg-gray-700 rounded-full h-3">
                    <div
                      className="bg-blue-600 h-3 rounded-full"
                      style={{ width: "100%" }}
                    />
                  </div>
                  <span className="ml-4 text-sm text-gray-600 dark:text-gray-400 w-24">
                    {stats.totalEvents} events
                  </span>
                </div>
              </div>
              <span className="mx-4 text-gray-400">→</span>
              <div className="flex-1">
                <div className="flex items-center">
                  <div className="flex-1 bg-gray-200 dark:bg-gray-700 rounded-full h-3">
                    <div
                      className="bg-green-600 h-3 rounded-full"
                      style={{
                        width: `${
                          stats.totalEvents > 0
                            ? Math.min(
                                100,
                                (stats.totalInjections / stats.totalEvents) * 10
                              )
                            : 0
                        }%`,
                      }}
                    />
                  </div>
                  <span className="ml-4 text-sm text-gray-600 dark:text-gray-400 w-24">
                    {stats.totalInjections} injected
                  </span>
                </div>
              </div>
              <span className="mx-4 text-gray-400">→</span>
              <div className="flex-1">
                <div className="flex items-center">
                  <div className="flex-1 bg-gray-200 dark:bg-gray-700 rounded-full h-3">
                    <div
                      className="bg-amber-500 h-3 rounded-full"
                      style={{
                        width: `${stats.effectivenessRate}%`,
                      }}
                    />
                  </div>
                  <span className="ml-4 text-sm text-gray-600 dark:text-gray-400 w-24">
                    {stats.totalCitations} cited
                  </span>
                </div>
              </div>
            </div>
          </div>
        </>
      ) : (
        <div className="flex justify-center items-center h-64">
          <div className="text-gray-500 dark:text-gray-400">
            {syncing ? "Syncing memory data..." : "Loading..."}
          </div>
        </div>
      )}
    </div>
  );
}
