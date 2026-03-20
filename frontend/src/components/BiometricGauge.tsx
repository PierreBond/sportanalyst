"use client";

import { useEffect, useState } from "react";

interface BiometricGaugeProps {
  label: string;
  value: number;
  min?: number;
  max?: number;
  unit?: string;
  thresholds?: {
    low: number;
    high: number;
  };
}

export function BiometricGauge({
  label,
  value,
  min = 0,
  max = 100,
  unit = "",
  thresholds = { low: 30, high: 70 },
}: BiometricGaugeProps) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    return (
      <div className="bg-white rounded-lg shadow p-4">
        <div className="animate-pulse">
          <div className="h-4 bg-gray-200 rounded w-1/2 mb-4"></div>
          <div className="h-24 bg-gray-200 rounded-full"></div>
        </div>
      </div>
    );
  }

  const percentage = ((value - min) / (max - min)) * 100;
  const clampedPercentage = Math.max(0, Math.min(100, percentage));

  const getColor = () => {
    if (value < thresholds.low) return "#ef4444";
    if (value > thresholds.high) return "#f59e0b";
    return "#22c55e";
  };

  const getStatus = () => {
    if (value < thresholds.low) return "Low";
    if (value > thresholds.high) return "High";
    return "Normal";
  };

  const radius = 45;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (clampedPercentage / 100) * circumference;

  return (
    <div className="bg-white rounded-lg shadow p-4">
      <div className="flex justify-between items-center mb-2">
        <h4 className="text-sm font-medium text-gray-700">{label}</h4>
        <span
          className={`text-xs px-2 py-1 rounded-full ${
            value < thresholds.low
              ? "bg-red-100 text-red-700"
              : value > thresholds.high
              ? "bg-yellow-100 text-yellow-700"
              : "bg-green-100 text-green-700"
          }`}
        >
          {getStatus()}
        </span>
      </div>

      <div className="relative flex items-center justify-center">
        <svg className="w-28 h-28 transform -rotate-90">
          <circle
            cx="56"
            cy="56"
            r={radius}
            stroke="#e5e7eb"
            strokeWidth="10"
            fill="none"
          />
          <circle
            cx="56"
            cy="56"
            r={radius}
            stroke={getColor()}
            strokeWidth="10"
            fill="none"
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            strokeLinecap="round"
            className="transition-all duration-500"
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-2xl font-bold" style={{ color: getColor() }}>
            {value.toFixed(1)}
          </span>
          <span className="text-xs text-gray-500">{unit}</span>
        </div>
      </div>

      <div className="flex justify-between text-xs text-gray-400 mt-2">
        <span>{min}</span>
        <span>{max}</span>
      </div>
    </div>
  );
}
