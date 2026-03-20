"use client";

import { useEffect, useState } from "react";
import type { LineMovement } from "@/types";

interface LineMovementChartProps {
  movements: LineMovement[];
  height?: number;
}

export function LineMovementChart({
  movements,
  height = 300,
}: LineMovementChartProps) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">
          Line Movement
        </h3>
        <div className="animate-pulse">
          <div className="h-64 bg-gray-200 rounded"></div>
        </div>
      </div>
    );
  }

  if (movements.length === 0) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">
          Line Movement
        </h3>
        <div
          className="flex items-center justify-center text-gray-500"
          style={{ height }}
        >
          No line movement data available
        </div>
      </div>
    );
  }

  const minSpread = Math.min(...movements.map((m) => m.spread));
  const maxSpread = Math.max(...movements.map((m) => m.spread));
  const minTotal = Math.min(...movements.map((m) => m.total));
  const maxTotal = Math.max(...movements.map((m) => m.total));

  const padding = 40;
  const chartWidth = 100;
  const chartHeight = 100;

  const scaleX = (index: number) =>
    padding + (index / (movements.length - 1)) * (chartWidth - 2 * padding);
  const scaleY = (
    value: number,
    min: number,
    max: number
  ) =>
    padding +
    ((max - value) / (max - min + 0.1)) * (chartHeight - 2 * padding);

  const createPath = (
    data: number[],
    min: number,
    max: number
  ) => {
    return data
      .map((value, index) => {
        const x = scaleX(index);
        const y = scaleY(value, min, max);
        return `${index === 0 ? "M" : "L"} ${x} ${y}`;
      })
      .join(" ");
  };

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">
        Line Movement
      </h3>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-4 text-sm">
          <div className="flex items-center">
            <div className="w-3 h-3 rounded-full bg-blue-500 mr-2"></div>
            <span className="text-gray-600">Spread</span>
          </div>
          <div className="flex items-center">
            <div className="w-3 h-3 rounded-full bg-green-500 mr-2"></div>
            <span className="text-gray-600">Total</span>
          </div>
        </div>
        <div className="text-sm text-gray-500">
          {movements.length} data points
        </div>
      </div>

      <svg
        viewBox={`0 0 ${chartWidth} ${chartHeight}`}
        className="w-full"
        style={{ height }}
        preserveAspectRatio="xMidYMid meet"
      >
        <defs>
          <linearGradient id="spreadGradient" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.3} />
            <stop offset="100%" stopColor="#3b82f6" stopOpacity={0.05} />
          </linearGradient>
          <linearGradient id="totalGradient" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor="#22c55e" stopOpacity={0.3} />
            <stop offset="100%" stopColor="#22c55e" stopOpacity={0.05} />
          </linearGradient>
        </defs>

        <g>
          {[0, 0.25, 0.5, 0.75, 1].map((ratio) => (
            <line
              key={ratio}
              x1={padding}
              y1={padding + ratio * (chartHeight - 2 * padding)}
              x2={chartWidth - padding}
              y2={padding + ratio * (chartHeight - 2 * padding)}
              stroke="#e5e7eb"
              strokeDasharray="2,2"
            />
          ))}
        </g>

        <path
          d={createPath(movements.map((m) => m.spread), minSpread, maxSpread)}
          fill="none"
          stroke="#3b82f6"
          strokeWidth={2}
          strokeLinecap="round"
          strokeLinejoin="round"
        />

        <path
          d={createPath(movements.map((m) => m.total), minTotal, maxTotal)}
          fill="none"
          stroke="#22c55e"
          strokeWidth={2}
          strokeLinecap="round"
          strokeLinejoin="round"
        />

        {movements.map((m, index) => (
          <circle
            key={index}
            cx={scaleX(index)}
            cy={scaleY(m.spread, minSpread, maxSpread)}
            r={2}
            fill="#3b82f6"
          />
        ))}
        {movements.map((m, index) => (
          <circle
            key={`total-${index}`}
            cx={scaleX(index)}
            cy={scaleY(m.total, minTotal, maxTotal)}
            r={2}
            fill="#22c55e"
          />
        ))}

        <text
          x={chartWidth - padding}
          y={scaleY(movements[movements.length - 1].spread, minSpread, maxSpread) - 5}
          fontSize={3}
          fill="#3b82f6"
          textAnchor="end"
        >
          {movements[movements.length - 1].spread.toFixed(1)}
        </text>
        <text
          x={chartWidth - padding}
          y={scaleY(movements[movements.length - 1].total, minTotal, maxTotal) - 5}
          fontSize={3}
          fill="#22c55e"
          textAnchor="end"
        >
          {movements[movements.length - 1].total.toFixed(1)}
        </text>

        <text
          x={padding}
          y={chartHeight - 10}
          fontSize={3}
          fill="#6b7280"
          textAnchor="start"
        >
          {movements[0].timestamp.slice(11, 16)}
        </text>
        <text
          x={chartWidth - padding}
          y={chartHeight - 10}
          fontSize={3}
          fill="#6b7280"
          textAnchor="end"
        >
          {movements[movements.length - 1].timestamp.slice(11, 16)}
        </text>
      </svg>

      <div className="mt-4 grid grid-cols-4 gap-4 text-sm">
        <div>
          <div className="text-gray-500">Opening Spread</div>
          <div className="font-semibold">{movements[0].spread.toFixed(1)}</div>
        </div>
        <div>
          <div className="text-gray-500">Current Spread</div>
          <div className="font-semibold">
            {movements[movements.length - 1].spread.toFixed(1)}
          </div>
        </div>
        <div>
          <div className="text-gray-500">Opening Total</div>
          <div className="font-semibold">{movements[0].total.toFixed(1)}</div>
        </div>
        <div>
          <div className="text-gray-500">Current Total</div>
          <div className="font-semibold">
            {movements[movements.length - 1].total.toFixed(1)}
          </div>
        </div>
      </div>
    </div>
  );
}
