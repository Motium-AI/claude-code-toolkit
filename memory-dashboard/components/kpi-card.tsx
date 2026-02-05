"use client";

interface KpiCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  trend?: "up" | "down" | "neutral";
}

export function KpiCard({ title, value, subtitle, trend }: KpiCardProps) {
  const trendColors = {
    up: "text-green-600 dark:text-green-400",
    down: "text-red-600 dark:text-red-400",
    neutral: "text-gray-600 dark:text-gray-400",
  };

  return (
    <div className="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-800 p-6">
      <p className="text-sm font-medium text-gray-500 dark:text-gray-400">
        {title}
      </p>
      <p className="mt-2 text-3xl font-semibold text-gray-900 dark:text-gray-100">
        {value}
      </p>
      {subtitle && (
        <p className={`mt-1 text-sm ${trend ? trendColors[trend] : "text-gray-500 dark:text-gray-400"}`}>
          {subtitle}
        </p>
      )}
    </div>
  );
}
