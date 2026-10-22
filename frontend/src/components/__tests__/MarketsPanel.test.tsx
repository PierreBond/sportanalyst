import { render, screen } from "@testing-library/react";
import { MarketsPanel } from "../MarketsPanel";
import type { MarketsResponse } from "@/types";

describe("MarketsPanel", () => {
  const mockMarkets: MarketsResponse = {
    match_id: "test-match-123",
    xg: { home: 1.537, away: 1.064, total: 2.601 },
    totals: [
      { line: 0.5, p_over: 0.9258 },
      { line: 1.5, p_over: 0.7328 },
      { line: 2.5, p_over: 0.4818 },
      { line: 3.5, p_over: 0.2642 },
    ],
    btts: 0.514,
    correct_scores: [
      { score: "1-1", prob: 0.1213 },
      { score: "1-0", prob: 0.1141 },
      { score: "2-1", prob: 0.0933 },
      { score: "2-0", prob: 0.0877 },
      { score: "0-1", prob: 0.0789 },
    ],
    outcome_probs_from_goals: { home_win: 0.4822, draw: 0.2551, away_win: 0.2626 },
    model_version: "v3.3_draw_features",
    xg_type: "goal_model",
  };

  it("renders xG values", () => {
    render(<MarketsPanel markets={mockMarkets} />);

    expect(screen.getByText("1.54")).toBeInTheDocument();
    expect(screen.getByText("1.06")).toBeInTheDocument();
    expect(screen.getByText("2.60")).toBeInTheDocument();
  });

  it("renders totals and BTTS percentages", () => {
    render(<MarketsPanel markets={mockMarkets} />);

    expect(screen.getByText("Over 2.5 goals")).toBeInTheDocument();
    expect(screen.getByText("48.2%")).toBeInTheDocument();
    expect(screen.getByText("Both teams to score")).toBeInTheDocument();
    expect(screen.getByText("51.4%")).toBeInTheDocument();
  });

  it("renders most likely correct scores", () => {
    render(<MarketsPanel markets={mockMarkets} />);

    expect(screen.getByText("1-1")).toBeInTheDocument();
    expect(screen.getByText("12.1%")).toBeInTheDocument();
  });

  it("labels the xG type honestly", () => {
    render(<MarketsPanel markets={mockMarkets} />);

    expect(screen.getByText(/xG type: goal_model/i)).toBeInTheDocument();
  });
});
