import { render, screen } from "@testing-library/react";
import { PredictionCard } from "../PredictionCard";
import type { PredictionResponse } from "@/types";

describe("PredictionCard", () => {
  const mockPrediction: PredictionResponse = {
    match_id: "test-match-123",
    home_team: "Manchester City",
    away_team: "Arsenal",
    league: "Premier League",
    scheduled_at: "2026-03-15T15:00:00Z",
    model: "xgboost_match_outcome",
    model_version: "v2.1",
    probabilities: {
      home_win: 0.55,
      draw: 0.25,
      away_win: 0.20,
    },
    predicted_score: {
      home: 2.1,
      away: 1.2,
    },
    calibrated: true,
    brier_score_trailing_100: 0.187,
    value_bets: [],
    shap_explanation: {
      positive_drivers: [],
      negative_drivers: [],
    },
    generated_at: "2026-03-15T12:00:00Z",
  };

  it("renders match teams", () => {
    render(<PredictionCard prediction={mockPrediction} />);

    expect(screen.getByText("Manchester City")).toBeInTheDocument();
    expect(screen.getByText("Arsenal")).toBeInTheDocument();
  });

  it("displays correct probability percentages", () => {
    render(<PredictionCard prediction={mockPrediction} />);

    expect(screen.getByText("55%")).toBeInTheDocument();
    expect(screen.getByText("25%")).toBeInTheDocument();
    expect(screen.getByText("20%")).toBeInTheDocument();
  });

  it("shows predicted score", () => {
    render(<PredictionCard prediction={mockPrediction} />);

    expect(screen.getByText("Predicted: 2.1 - 1.2")).toBeInTheDocument();
  });

  it("displays calibrated badge when calibrated", () => {
    render(<PredictionCard prediction={mockPrediction} />);

    expect(screen.getByText("Calibrated")).toBeInTheDocument();
  });

  it("links to match detail page", () => {
    render(<PredictionCard prediction={mockPrediction} />);

    const link = screen.getByRole("link", { name: /manchester city vs arsenal/i });
    expect(link).toHaveAttribute("href", "/matches/test-match-123");
  });

  it("highlights the winning outcome", () => {
    render(<PredictionCard prediction={mockPrediction} />);

    const homeOutcome = screen.getByText("Home").parentElement;
    expect(homeOutcome).toHaveClass("bg-blue-600");
  });
});
