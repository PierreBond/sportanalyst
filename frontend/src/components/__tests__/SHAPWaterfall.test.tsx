import { render, screen } from "@testing-library/react";
import { SHAPWaterfall } from "../SHAPWaterfall";
import type { SHAPExplanation } from "@/types";

describe("SHAPWaterfall", () => {
  const mockExplanation: SHAPExplanation = {
    positive_drivers: [
      { feature: "momentum_xg_slope_5", impact: 0.082, impact_pct: 8.2, label: "Strong offensive form" },
      { feature: "is_home", impact: 0.061, impact_pct: 6.1, label: "Home advantage" },
    ],
    negative_drivers: [
      { feature: "star_player_acwr", impact: -0.045, impact_pct: 4.5, label: "Key player fatigue risk" },
      { feature: "team_sentiment_twitter_24h", impact: -0.021, impact_pct: 2.1, label: "Negative fan sentiment" },
    ],
  };

  it("renders positive and negative drivers", () => {
    render(<SHAPWaterfall explanation={mockExplanation} />);

    expect(screen.getByText("Prediction Drivers (SHAP)")).toBeInTheDocument();
    expect(screen.getByText("Positive Factors")).toBeInTheDocument();
    expect(screen.getByText("Negative Factors")).toBeInTheDocument();
  });

  it("displays correct impact values for positive drivers", () => {
    render(<SHAPWaterfall explanation={mockExplanation} />);

    expect(screen.getByText("+8.2%")).toBeInTheDocument();
    expect(screen.getByText("+6.1%")).toBeInTheDocument();
  });

  it("displays correct impact values for negative drivers", () => {
    render(<SHAPWaterfall explanation={mockExplanation} />);

    expect(screen.getByText("-4.5%")).toBeInTheDocument();
    expect(screen.getByText("-2.1%")).toBeInTheDocument();
  });

  it("limits items when maxItems is specified", () => {
    const explanationWithManyDrivers: SHAPExplanation = {
      positive_drivers: Array(10).fill({ feature: "test", impact: 0.05, impact_pct: 5, label: "Test" }),
      negative_drivers: Array(10).fill({ feature: "test", impact: -0.05, impact_pct: 5, label: "Test" }),
    };

    render(<SHAPWaterfall explanation={explanationWithManyDrivers} maxItems={3} />);

    const positiveItems = screen.getAllByText("Test");
    expect(positiveItems.length).toBeLessThanOrEqual(6);
  });
});
