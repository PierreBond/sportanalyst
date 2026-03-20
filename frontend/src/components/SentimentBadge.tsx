"use client";

import { useEffect, useState } from "react";

interface SentimentBadgeProps {
  score: number;
  volume?: number;
  size?: "sm" | "md" | "lg";
  showVolume?: boolean;
}

export function SentimentBadge({
  score,
  volume,
  size = "md",
  showVolume = true,
}: SentimentBadgeProps) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    return (
      <div className="animate-pulse">
        <div className="h-8 bg-gray-200 rounded-full"></div>
      </div>
    );
  }

  const getSentiment = () => {
    if (score >= 0.6) return { label: "Very Positive", color: "#22c55e" };
    if (score >= 0.2) return { label: "Positive", color: "#84cc16" };
    if (score >= -0.2) return { label: "Neutral", color: "#6b7280" };
    if (score >= -0.6) return { label: "Negative", color: "#f97316" };
    return { label: "Very Negative", color: "#ef4444" };
  };

  const sentiment = getSentiment();

  const sizeClasses = {
    sm: "px-2 py-1 text-xs",
    md: "px-3 py-1.5 text-sm",
    lg: "px-4 py-2 text-base",
  };

  const iconSizeClasses = {
    sm: "w-3 h-3",
    md: "w-4 h-4",
    lg: "w-5 h-5",
  };

  const volumeDisplay = volume !== undefined ? (
    <span className="ml-1 opacity-75">({volume.toLocaleString()})</span>
  ) : null;

  return (
    <div className="inline-flex flex-col">
      <div
        className={`inline-flex items-center rounded-full font-medium ${sizeClasses[size]}`}
        style={{
          backgroundColor: `${sentiment.color}20`,
          color: sentiment.color,
        }}
      >
        {score >= 0 ? (
          <svg
            className={`${iconSizeClasses[size]} mr-1`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M14 10h4.764a2 2 0 011.789 2.894l-3.5 7A2 2 0 0115.263 21h-4.017c-.163 0-.326-.02-.485-.06L7 20m7-10V5a2 2 0 00-2-2h-.095c-.5 0-.905.405-.905.905 0 .714-.211 1.412-.608 2.006L7 11v9m7-10h-2M7 20H5a2 2 0 01-2-2v-6a2 2 0 012-2h2.5"
            />
          </svg>
        ) : (
          <svg
            className={`${iconSizeClasses[size]} mr-1`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M10 14H5.236a2 2 0 01-1.789-2.894l3.5-7A2 2 0 018.736 3h4.018a2 2 0 01.485.06l3.76.94m-7 10v5a2 2 0 002 2h.096c.5 0 .905-.405.905-.904 0-.715.211-1.413.608-2.008L17 13V4m-7 10h2m5-10h2a2 2 0 012 2v6a2 2 0 01-2 2h-2.5"
            />
          </svg>
        )}
        <span>
          {sentiment.label}
          {showVolume && volumeDisplay}
        </span>
      </div>

      <div className="mt-1 flex items-center space-x-1">
        <div className="w-20 h-1.5 bg-gray-200 rounded-full overflow-hidden">
          <div
            className="h-full rounded-full transition-all duration-300"
            style={{
              width: `${Math.abs(score) * 50}%`,
              marginLeft: score < 0 ? "50%" : "0",
              backgroundColor: sentiment.color,
              transform: "scaleX(1)",
              transformOrigin: score < 0 ? "right" : "left",
            }}
          />
        </div>
        <span className="text-xs text-gray-500">
          {(score * 100).toFixed(0)}%
        </span>
      </div>
    </div>
  );
}
