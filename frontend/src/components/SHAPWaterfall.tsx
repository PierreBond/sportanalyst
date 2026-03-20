"use client";

import { useEffect, useState } from "react";
import type { SHAPExplanation } from "@/types";

interface SHAPWaterfallProps {
  explanation: SHAPExplanation;
  maxItems?: number;
}

export function SHAPWaterfall({ explanation, maxItems = 5 }: SHAPWaterfallProps) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">
          Prediction Drivers
        </h3>
        <div className="animate-pulse">
          <div className="h-4 bg-gray-200 rounded w-full mb-2"></div>
          <div className="h-4 bg-gray-200 rounded w-3/4 mb-2"></div>
          <div className="h-4 bg-gray-200 rounded w-1/2"></div>
        </div>
      </div>
    );
  }

  const positiveDrivers = explanation.positive_drivers.slice(0, maxItems);
  const negativeDrivers = explanation.negative_drivers.slice(0, maxItems);

  const maxImpact = Math.max(
    ...positiveDrivers.map((d) => d.impact),
    ...negativeDrivers.map((d) => Math.abs(d.impact))
  );

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">
        Prediction Drivers (SHAP)
      </h3>

      {positiveDrivers.length > 0 && (
        <div className="mb-6">
          <h4 className="text-sm font-medium text-green-600 mb-3 flex items-center">
            <svg
              className="w-4 h-4 mr-1"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M5 10l7-7m0 0l7 7m-7-7v18"
              />
            </svg>
            Positive Factors
          </h4>
          <div className="space-y-2">
            {positiveDrivers.map((driver, index) => (
              <div key={index} className="relative">
                <div className="flex justify-between items-center mb-1">
                  <span className="text-sm text-gray-700 truncate pr-2">
                    {driver.label}
                  </span>
                  <span className="text-sm font-semibold text-green-600 whitespace-nowrap">
                    +{(driver.impact * 100).toFixed(1)}%
                  </span>
                </div>
                <div className="w-full bg-gray-100 rounded-full h-2">
                  <div
                    className="bg-green-500 h-2 rounded-full transition-all duration-500"
                    style={{
                      width: `${(driver.impact / maxImpact) * 100}%`,
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {negativeDrivers.length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-red-600 mb-3 flex items-center">
            <svg
              className="w-4 h-4 mr-1"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M19 14l-7 7m0 0l-7-7m7 7V3"
              />
            </svg>
            Negative Factors
          </h4>
          <div className="space-y-2">
            {negativeDrivers.map((driver, index) => (
              <div key={index} className="relative">
                <div className="flex justify-between items-center mb-1">
                  <span className="text-sm text-gray-700 truncate pr-2">
                    {driver.label}
                  </span>
                  <span className="text-sm font-semibold text-red-600 whitespace-nowrap">
                    {(driver.impact * 100).toFixed(1)}%
                  </span>
                </div>
                <div className="w-full bg-gray-100 rounded-full h-2">
                  <div
                    className="bg-red-500 h-2 rounded-full transition-all duration-500"
                    style={{
                      width: `${(Math.abs(driver.impact) / maxImpact) * 100}%`,
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {positiveDrivers.length === 0 && negativeDrivers.length === 0 && (
        <p className="text-gray-500 text-sm">No drivers available</p>
      )}
    </div>
  );
}
